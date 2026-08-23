from __future__ import annotations

import json
import math

import numpy as np
import pytest

from adaptivecad.geometry.infinity_root import (
    CanonicalRootTower,
    FractionalGaugeSpec,
    LevelStatus,
    RootJetSamples,
    compare_fractional_gauge_curvature,
    infinity_root_book_obj,
    make_exact_lift_tower,
    make_infinity_root_book,
    make_infinity_root_profile,
    profile_curvature_metrics,
    root_operator_samples,
    tower_from_profile_samples,
)


def sample_grid(count: int = 301) -> tuple[float, ...]:
    return tuple(float(value) for value in np.geomspace(0.5, 2.0, count))


def test_normalized_lift_tower_matches_depth_two_model() -> None:
    x = sample_grid()
    tower = make_exact_lift_tower(x, depth=2, residue=2.0, basepoint=1.0)

    assert tower.depth == 2
    assert tower.source.startswith("root_jet_decode:")
    assert np.allclose(tower.levels[2], 2.0, atol=0.0, rtol=0.0)
    assert np.allclose(tower.levels[1], np.asarray(x) ** 2, atol=2e-13, rtol=2e-13)

    expected_level_zero = np.exp((np.asarray(x) ** 2 - 1.0) / 2.0)
    assert np.allclose(tower.levels[0], expected_level_zero, atol=3e-5, rtol=3e-5)
    assert tower.value_at(0, 1.0) == pytest.approx(1.0, abs=2e-14)
    assert tower.value_at(1, 1.0) == pytest.approx(1.0, abs=2e-14)

    estimated_root = root_operator_samples(x, tower.levels[0])
    assert np.allclose(estimated_root[2:-2], tower.levels[1][2:-2], atol=3e-4, rtol=3e-4)


def test_root_jet_serialization_and_basepoint_transport_preserve_tower() -> None:
    x = sample_grid(201)
    terminal = tuple(1.1 + 0.05 * math.log(value) ** 2 for value in x)
    jet = RootJetSamples(
        x=x,
        basepoint=1.0,
        constants=(2.5, 1.2),
        terminal=terminal,
        provenance="unit_test",
    )

    restored = RootJetSamples.from_dict(json.loads(json.dumps(jet.to_dict())))
    assert restored == jet

    original_tower = jet.decode()
    transported = jet.transport(1.25)
    transported_tower = transported.decode()
    for original, moved in zip(original_tower.levels, transported_tower.levels):
        assert np.allclose(original, moved, atol=2e-13, rtol=2e-13)
    assert transported.basepoint == 1.25
    assert transported.constants != jet.constants


def test_tower_dictionary_roundtrip() -> None:
    tower = make_exact_lift_tower(sample_grid(101), depth=3, residue=1.0)
    restored = CanonicalRootTower.from_dict(json.loads(json.dumps(tower.to_dict())))
    assert restored == tower


def test_sampled_profile_estimator_uses_logarithmic_derivative() -> None:
    x = sample_grid(151)
    values = tuple(value**3 for value in x)
    tower = tower_from_profile_samples(x, values, depth=1, basepoint=1.0)

    assert tower.depth == 1
    assert tower.source == "finite_difference_log_grid_estimate"
    assert np.allclose(tower.levels[1], 3.0, atol=2e-12, rtol=2e-12)

    with pytest.raises(ValueError, match="not positive"):
        tower_from_profile_samples(x, tuple(value**-1 for value in x), depth=1)


def test_fractional_height_requires_and_records_explicit_gauge() -> None:
    tower = make_exact_lift_tower(sample_grid(121), depth=2, residue=2.0)

    with pytest.raises(ValueError, match="requires an explicit"):
        tower.level_at(0.5)
    with pytest.raises(ValueError, match="omit gauge"):
        tower.level_at(1.0, gauge=FractionalGaugeSpec.power_mean(0.0))

    log_gauge = FractionalGaugeSpec.power_mean(0.0)
    arithmetic_gauge = FractionalGaugeSpec.power_mean(1.0)
    log_view = tower.level_at(0.5, gauge=log_gauge)
    arithmetic_view = tower.level_at(0.5, gauge=arithmetic_gauge)

    assert log_view.status is LevelStatus.GAUGE_VIEW
    assert not log_view.is_canonical
    assert log_view.gauge == log_gauge
    assert not np.allclose(log_view.values, arithmetic_view.values)
    assert log_view.to_dict()["gauge"]["abel_equation_verified"] is False
    assert log_view.to_dict()["gauge"]["mathematical_status"] == "local_visualization_gauge"

    canonical = tower.level_at(1.0)
    assert canonical.status is LevelStatus.CANONICAL_INTEGER
    assert canonical.gauge is None


def test_profile_metadata_keeps_descriptor_separate_from_metric_kernel() -> None:
    tower = make_exact_lift_tower(sample_grid(91), depth=2, residue=1.0)
    canonical = make_infinity_root_profile(tower, height=1.0, radius=8.0)
    gauge_view = make_infinity_root_profile(
        tower,
        height=1.5,
        gauge=FractionalGaugeSpec.power_mean(0.0),
        radius=8.0,
    )

    assert canonical["family"] == "infinity_root:profile"
    assert canonical["metric"] == "inherit"
    assert canonical["infinity_root"]["role"] == "geometry_descriptor_not_metric_kernel"
    assert canonical["infinity_root"]["level"]["canonical"] is True
    assert canonical["infinity_root"]["level"]["gauge"] is None
    assert len(canonical["points"]) == 2 * len(tower.x) - 2
    assert (
        canonical["infinity_root"]["display_mapping"]["periodicization"]
        == "forward_then_reflected_without_duplicate_endpoints"
    )
    assert canonical["infinity_root"]["curvature"]["turning_number"] == pytest.approx(
        1.0, abs=2e-12
    )

    fractional_meta = gauge_view["infinity_root"]["level"]
    assert fractional_meta["canonical"] is False
    assert fractional_meta["status"] == "gauge_view"
    assert fractional_meta["gauge"]["gauge_id"] == "positive_power_mean@1"


def test_total_signed_page_curvature_survives_gauge_change() -> None:
    tower = make_exact_lift_tower(sample_grid(361), depth=2, residue=2.0)
    comparison = compare_fractional_gauge_curvature(
        tower,
        height=0.5,
        gauges=(
            FractionalGaugeSpec.power_mean(0.0),
            FractionalGaugeSpec.power_mean(1.0),
        ),
        radial_gain=0.55,
    )

    assert "signed_total_curvature" in comparison["invariant_within_tolerance"]
    assert "turning_number" in comparison["invariant_within_tolerance"]
    assert "perimeter" in comparison["gauge_dependent_within_test"]
    for row in comparison["rows"]:
        metrics = row["curvature"]
        assert metrics["signed_total_curvature"] == pytest.approx(2.0 * math.pi, abs=2e-12)
        assert metrics["turning_number"] == pytest.approx(1.0, abs=2e-12)


def test_circle_curvature_audit() -> None:
    angles = np.linspace(0.0, 2.0 * math.pi, 720, endpoint=False)
    points = [(3.0 * math.cos(angle), 3.0 * math.sin(angle)) for angle in angles]
    metrics = profile_curvature_metrics(points)
    assert metrics["perimeter"] == pytest.approx(6.0 * math.pi, rel=2e-5)
    assert metrics["signed_total_curvature"] == pytest.approx(2.0 * math.pi, abs=2e-12)
    assert metrics["rms_curvature"] == pytest.approx(1.0 / 3.0, rel=2e-5)


def test_infinity_book_is_quad_only_and_preserves_page_provenance() -> None:
    tower = make_exact_lift_tower(sample_grid(81), depth=2, residue=1.0)
    gauge = FractionalGaugeSpec.power_mean(0.0)
    book = make_infinity_root_book(
        tower,
        fractional_pages=((0.5, gauge), (1.5, gauge)),
        radius=12.0,
        page_gap=1.5,
    )

    assert book["family"] == "infinity_root:book"
    assert book["preview_topology"] == "quad_loft_no_triangles"
    assert book["contains_gauge_views"] is True
    assert "turning_number" in book["curvature_audit"]["survives_regular_closed_page_morph"]
    assert [page["height"] for page in book["pages"]] == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert [page["status"] for page in book["pages"]] == [
        "canonical_integer",
        "gauge_view",
        "canonical_integer",
        "gauge_view",
        "canonical_integer",
    ]
    points_per_page = 2 * len(tower.x) - 2
    assert len(book["vertices"]) == 5 * points_per_page
    assert len(book["quads"]) == 4 * points_per_page
    assert all(len(face) == 4 for face in book["quads"])
    json.dumps(book)

    obj = infinity_root_book_obj(book)
    face_lines = [line for line in obj.splitlines() if line.startswith("f ")]
    assert len(face_lines) == len(book["quads"])
    assert all(len(line.split()) == 5 for line in face_lines)


def test_book_rejects_fractional_page_without_a_real_fractional_height() -> None:
    tower = make_exact_lift_tower(sample_grid(51), depth=1, residue=1.0)
    with pytest.raises(ValueError, match="must not repeat an integer"):
        make_infinity_root_book(
            tower,
            fractional_pages=((1.0, FractionalGaugeSpec.power_mean()),),
        )
