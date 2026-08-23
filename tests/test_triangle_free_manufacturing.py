from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from adaptivecad.geometry.infinity_root import FractionalGaugeSpec, make_exact_lift_tower
from adaptivecad.manufacturing import (
    AdditivePlanSettings,
    AdditivePostSettings,
    CubicBezier2D,
    InfinityRootLoftSource,
    ManufacturingJob,
    SubtractivePlanSettings,
    SubtractivePostSettings,
    audit_job,
    audit_triangle_free_job,
    plan_additive_loft,
    plan_subtractive_waterlines,
    postprocess_additive_gcode,
    postprocess_subtractive_gcode,
    scale_invariance_gate,
)
from demo.triangle_free_infinity_root_manufacturing import _write_bundle


class TriangleFreeManufacturingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        x = tuple(float(value) for value in np.geomspace(0.55, 1.8, 17))
        tower = make_exact_lift_tower(x, depth=2, residue=1.0, basepoint=1.0)
        gauge = FractionalGaugeSpec.power_mean(0.0)
        cls.source = InfinityRootLoftSource.from_tower(
            tower,
            fractional_pages=((0.5, gauge), (1.5, gauge)),
            radius_mm=24.0,
            page_gap_mm=3.0,
            radial_gain=0.24,
            band_width_mm=5.0,
        )

    def test_bezier_flattening_is_controller_only_line_motion(self) -> None:
        curve = CubicBezier2D((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0))
        points = curve.flatten(0.01)
        self.assertEqual(points[0], curve.start)
        self.assertEqual(points[-1], curve.end)
        self.assertGreater(len(points), 3)
        self.assertGreater(curve.length(), 1.0)

    def test_declared_pages_and_physical_loft_are_distinguished(self) -> None:
        declared = self.source.path_at(
            1.5,
            radial_offset_mm=0.0,
            role="test_declared",
        )
        between = self.source.path_at(
            0.75,
            radial_offset_mm=0.0,
            role="test_between",
        )
        self.assertEqual(declared.metadata["section_status"], "declared_root_page")
        self.assertEqual(declared.metadata["page"]["status"], "gauge_view")
        self.assertEqual(between.metadata["section_status"], "fabrication_loft_interpolation")
        self.assertIn("not an additional fractional", between.metadata["claim_boundary"])

    def test_local_normal_offset_is_curve_native_and_tolerance_validated(self) -> None:
        offset = self.source.normal_offset_path_at(
            1.5,
            boundary_radial_offset_mm=self.source.half_band_width,
            normal_offset_mm=-1.0,
            fit_tolerance_mm=0.02,
            role="test_normal_offset",
            clockwise=False,
        )
        self.assertEqual(offset.orientation, "counterclockwise")
        self.assertTrue(all(isinstance(segment, CubicBezier2D) for segment in offset.segments))
        self.assertLessEqual(
            offset.metadata["normal_offset_max_validation_error_mm"],
            offset.metadata["normal_offset_fit_tolerance_mm"],
        )
        self.assertIn("local_normal", offset.metadata["normal_offset_method"])

    def test_additive_job_roundtrip_and_triangle_free_audit(self) -> None:
        job = plan_additive_loft(
            self.source,
            AdditivePlanSettings(
                layer_height_mm=1.0,
                perimeter_count=1,
                infill_density=0.20,
            ),
        )
        audit = audit_triangle_free_job(job)
        self.assertTrue(audit["authoritative_ir_triangle_free"])
        self.assertFalse(audit["triangle_mesh_input"])
        self.assertEqual(audit["curve_kind_counts"]["line"], 0)
        self.assertEqual(audit["curve_kind_counts"]["circular_arc"], 0)
        self.assertGreater(audit["curve_kind_counts"]["cubic_bezier"], 0)
        restored = ManufacturingJob.from_dict(json.loads(json.dumps(job.to_dict())))
        self.assertEqual(restored.source_id, job.source_id)
        self.assertEqual(len(restored.layers), len(job.layers))

    def test_infinity_root_job_passes_strict_contract_and_scale_gate(self) -> None:
        job = plan_additive_loft(
            self.source,
            AdditivePlanSettings(
                layer_height_mm=2.0,
                perimeter_count=1,
                infill_density=0.0,
            ),
        )
        serialized = job.to_dict()
        report = audit_job(serialized, name="Infinity Root additive")
        self.assertTrue(report["passed"], report["errors"])
        gate = scale_invariance_gate(
            serialized,
            factors=(0.001, 1000.0),
            name="Infinity Root additive",
        )
        self.assertTrue(gate["passed"])

    def test_printer_native_and_linearized_backends_share_one_job(self) -> None:
        job = plan_additive_loft(
            self.source,
            AdditivePlanSettings(
                layer_height_mm=2.0,
                perimeter_count=1,
                infill_density=0.0,
            ),
        )
        native, native_audit = postprocess_additive_gcode(
            job,
            AdditivePostSettings(curve_mode="native"),
        )
        linear, linear_audit = postprocess_additive_gcode(
            job,
            AdditivePostSettings(curve_mode="linearized", chord_tolerance_mm=0.05),
        )
        self.assertIn("\nG5 ", native)
        self.assertNotIn("\nG5 ", linear)
        self.assertTrue(native_audit["native_bezier_motion_present"])
        self.assertTrue(linear_audit["controller_linearization_used"])
        self.assertEqual(native_audit["job_id"], linear_audit["job_id"])

    def test_same_source_drives_printer_and_cnc_jobs(self) -> None:
        additive = plan_additive_loft(
            self.source,
            AdditivePlanSettings(layer_height_mm=2.0, perimeter_count=1, infill_density=0.0),
        )
        subtractive = plan_subtractive_waterlines(
            self.source,
            SubtractivePlanSettings(step_down_mm=2.0, tool_diameter_mm=2.0),
        )
        self.assertEqual(additive.source_id, subtractive.source_id)
        self.assertEqual(additive.source_id, self.source.source_id)
        subtractive_audit = audit_triangle_free_job(subtractive)
        self.assertTrue(subtractive_audit["authoritative_ir_triangle_free"])
        self.assertGreater(subtractive_audit["curve_kind_counts"]["cubic_bezier"], 0)
        for layer in subtractive.layers:
            for path in layer.paths:
                self.assertIn("along_local_normal", path.metadata["tool_center_compensation"])
                self.assertLessEqual(
                    path.metadata["normal_offset_max_validation_error_mm"],
                    path.metadata["normal_offset_fit_tolerance_mm"],
                )

    def test_cnc_native_and_linearized_backends(self) -> None:
        job = plan_subtractive_waterlines(
            self.source,
            SubtractivePlanSettings(step_down_mm=3.0, tool_diameter_mm=2.0),
        )
        native, native_audit = postprocess_subtractive_gcode(
            job,
            SubtractivePostSettings(curve_mode="native"),
        )
        linear, linear_audit = postprocess_subtractive_gcode(
            job,
            SubtractivePostSettings(curve_mode="linearized", chord_tolerance_mm=0.03),
        )
        self.assertIn("\nG5 ", native)
        self.assertNotIn("\nG5 ", linear)
        self.assertIn("VERIFY STOCK", native)
        self.assertTrue(native_audit["native_bezier_motion_present"])
        self.assertTrue(linear_audit["controller_linearization_used"])

    def test_benchmark_bundle_is_atomic_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.txt"
            second = root / "second.txt"
            bundle = root / "benchmark.zip"
            first.write_text("first\n", encoding="utf-8")
            second.write_text("second\n", encoding="utf-8")

            _write_bundle(bundle, (first, second))

            self.assertFalse(bundle.with_name(f"{bundle.name}.part").exists())
            self.assertTrue(zipfile.is_zipfile(bundle))
            with zipfile.ZipFile(bundle, "r") as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(
                    set(archive.namelist()),
                    {"first.txt", "second.txt", "SHA256SUMS.txt"},
                )


if __name__ == "__main__":
    unittest.main()
