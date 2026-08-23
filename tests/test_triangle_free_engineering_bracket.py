from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
import zipfile
from pathlib import Path

from adaptivecad.manufacturing import (
    AdditivePostSettings,
    CircularArc2D,
    EngineeringBracketSource,
    ManufacturingJob,
    SubtractivePostSettings,
    audit_job,
    plan_engineering_bracket_additive,
    plan_engineering_bracket_subtractive,
    postprocess_additive_gcode,
    postprocess_subtractive_gcode,
    scale_invariance_gate,
    validate_shared_source,
)
from demo.triangle_free_engineering_bracket import generate


class TriangleFreeEngineeringBracketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = EngineeringBracketSource.default()
        cls.additive = plan_engineering_bracket_additive(cls.source)
        cls.subtractive = plan_engineering_bracket_subtractive(cls.source)
        cls.additive_dict = cls.additive.to_dict()
        cls.subtractive_dict = cls.subtractive.to_dict()

    def test_source_is_stable_analytic_regularized_difference(self) -> None:
        source = self.source.to_dict()
        self.assertEqual(
            self.source.source_id,
            "engineering-bracket-f37fc49df0bc7c2b74ee",
        )
        self.assertFalse(source["mesh_created"])
        self.assertEqual(source["construction"]["kind"], "regularized_difference")
        self.assertEqual(len(source["construction"]["subtract"]), 5)
        self.assertEqual(source["topology"]["filleted_corner_count"], 8)
        self.assertAlmostEqual(
            source["analytic_properties"]["net_volume_mm3"],
            35501.69911184308,
            places=9,
        )

    def test_additive_job_is_native_curve_ir_and_passes_contract(self) -> None:
        report = audit_job(self.additive_dict, name="engineering bracket additive")
        self.assertTrue(report["passed"], report["errors"][:10])
        self.assertEqual(report["statistics"]["layer_count"], 40)
        self.assertEqual(report["statistics"]["path_count"], 6616)
        self.assertEqual(report["statistics"]["segment_count"], 8696)
        self.assertEqual(
            report["statistics"]["segment_kind_counts"],
            {"circular_arc": 1920, "line": 6776},
        )
        restored = ManufacturingJob.from_dict(self.additive_dict)
        self.assertEqual(restored.source_id, self.source.source_id)
        self.assertEqual(len(restored.layers), 40)

    def test_subtractive_job_is_native_curve_ir_and_passes_contract(self) -> None:
        report = audit_job(
            self.subtractive_dict,
            name="engineering bracket subtractive",
        )
        self.assertTrue(report["passed"], report["errors"][:10])
        self.assertEqual(report["statistics"]["layer_count"], 4)
        self.assertEqual(report["statistics"]["closed_path_count"], 24)
        self.assertEqual(report["statistics"]["segment_count"], 128)
        self.assertEqual(
            report["statistics"]["segment_kind_counts"],
            {"circular_arc": 96, "line": 32},
        )

    def test_both_processes_share_exact_source_provenance(self) -> None:
        report = validate_shared_source(
            [self.additive_dict, self.subtractive_dict]
        )
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["one_source_id"], self.source.source_id)

    def test_scale_gate_preserves_geometry_and_topology(self) -> None:
        for name, job in (
            ("additive", self.additive_dict),
            ("subtractive", self.subtractive_dict),
        ):
            with self.subTest(process=name):
                gate = scale_invariance_gate(
                    job,
                    factors=(0.001, 0.01, 1.0, 100.0, 1000.0),
                    name=f"engineering bracket {name}",
                )
                self.assertTrue(gate["passed"])
                self.assertTrue(
                    all(case["topology_signature_preserved"] for case in gate["cases"])
                )
                self.assertTrue(
                    all(case["source_id_preserved"] for case in gate["cases"])
                )

    def test_native_and_linearized_printer_posts_share_one_job(self) -> None:
        native, native_audit = postprocess_additive_gcode(
            self.additive,
            AdditivePostSettings(
                curve_mode="native",
                work_offset_x_mm=150.0,
                work_offset_y_mm=100.0,
                retraction_feed_mm_min=1800.0,
            ),
        )
        linear, linear_audit = postprocess_additive_gcode(
            self.additive,
            AdditivePostSettings(
                curve_mode="linearized",
                work_offset_x_mm=150.0,
                work_offset_y_mm=100.0,
                chord_tolerance_mm=self.additive.tolerance_mm,
                retraction_feed_mm_min=1800.0,
            ),
        )
        self.assertGreater(native_audit["motion_counts"]["G2"], 0)
        self.assertGreater(native_audit["motion_counts"]["G3"], 0)
        self.assertEqual(linear_audit["motion_counts"]["G2"], 0)
        self.assertEqual(linear_audit["motion_counts"]["G3"], 0)
        self.assertFalse(native_audit["controller_linearization_used"])
        self.assertTrue(linear_audit["controller_linearization_used"])
        self.assertEqual(native_audit["job_id"], linear_audit["job_id"])
        self.assertNotIn(" X-", native)
        self.assertNotIn(" Y-", native)
        self.assertIn("; retract", native)

    def test_native_and_linearized_cnc_posts_share_one_job(self) -> None:
        native, native_audit = postprocess_subtractive_gcode(
            self.subtractive,
            SubtractivePostSettings(curve_mode="native"),
        )
        linear, linear_audit = postprocess_subtractive_gcode(
            self.subtractive,
            SubtractivePostSettings(
                curve_mode="linearized",
                chord_tolerance_mm=self.subtractive.tolerance_mm,
            ),
        )
        self.assertGreater(native_audit["motion_counts"]["G2"], 0)
        self.assertGreater(native_audit["motion_counts"]["G3"], 0)
        self.assertEqual(linear_audit["motion_counts"]["G2"], 0)
        self.assertEqual(linear_audit["motion_counts"]["G3"], 0)
        self.assertIn("VERIFY STOCK", native)
        self.assertEqual(native_audit["job_id"], linear_audit["job_id"])

    def test_controller_arc_linearization_respects_sagitta_tolerance(self) -> None:
        arc = next(
            segment
            for layer in self.subtractive.layers
            for path in layer.paths
            for segment in path.segments
            if isinstance(segment, CircularArc2D)
        )
        tolerance = self.subtractive.tolerance_mm
        maximum_angle = 2.0 * math.acos(1.0 - tolerance / arc.radius)
        count = max(1, int(math.ceil(abs(arc.sweep_angle) / maximum_angle)))
        points = [arc.evaluate(index / count) for index in range(count + 1)]
        maximum_sagitta = 0.0
        for start, end in zip(points, points[1:]):
            chord = math.dist(start, end)
            sagitta = arc.radius - math.sqrt(
                max(0.0, arc.radius * arc.radius - (chord / 2.0) ** 2)
            )
            maximum_sagitta = max(maximum_sagitta, sagitta)
        self.assertLessEqual(maximum_sagitta, tolerance + 1.0e-12)

    def test_triangle_payload_and_source_mismatch_are_rejected(self) -> None:
        contaminated = copy.deepcopy(self.additive_dict)
        contaminated["triangles"] = [[0, 1, 2]]
        self.assertFalse(audit_job(contaminated)["passed"])

        mismatched = copy.deepcopy(self.subtractive_dict)
        mismatched["source_id"] = "different-source"
        self.assertFalse(audit_job(mismatched)["passed"])
        self.assertFalse(
            validate_shared_source([self.additive_dict, mismatched])["passed"]
        )

    def test_schema_matches_native_curve_ir_spelling(self) -> None:
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "adaptivecad_curve_ir.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        arc = schema["$defs"]["circular_arc"]
        self.assertEqual(
            set(arc["required"]),
            {"kind", "center", "radius", "start_angle", "sweep_angle"},
        )
        self.assertEqual(
            schema["$defs"]["layer"]["properties"]["kind"]["const"],
            "manufacturing_layer",
        )

    def test_demo_writes_valid_complete_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = generate(root)
            bundle = Path(summary["bundle"])
            self.assertTrue(summary["contract_gate_passed"])
            self.assertEqual(summary["source_id"], self.source.source_id)
            self.assertTrue(zipfile.is_zipfile(bundle))
            with zipfile.ZipFile(bundle, "r") as archive:
                self.assertIsNone(archive.testzip())
                names = set(archive.namelist())
            self.assertIn("SHA256SUMS.txt", names)
            self.assertIn("engineering_bracket_source.json", names)
            self.assertIn("engineering_bracket_additive_curve_job.json", names)
            self.assertIn("engineering_bracket_subtractive_curve_job.json", names)
            self.assertIn("engineering_bracket_printer_native_arcs.gcode", names)
            self.assertIn("engineering_bracket_cnc_native_arcs.nc", names)


if __name__ == "__main__":
    unittest.main()
