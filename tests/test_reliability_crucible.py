import math
from pathlib import Path

import pytest

from adaptivecad.reliability_crucible import (
    benchmark_feature_scaling,
    generate_crucible_report,
    has_occ,
    run_boolean_nightmare_test,
    run_step_round_trip_test,
)


def test_performance_wall_supports_5000_features():
    samples = benchmark_feature_scaling(counts=(128, 1024, 5000), sample_count=2)

    assert [sample.feature_count for sample in samples] == [128, 1024, 5000]
    assert samples[-1].feature_count == 5000
    assert all(sample.sample_count == 2 for sample in samples)
    assert all(math.isfinite(sample.build_seconds) and sample.build_seconds >= 0.0 for sample in samples)
    assert all(math.isfinite(sample.eval_seconds) and sample.eval_seconds >= 0.0 for sample in samples)
    assert all(math.isfinite(sample.samples_per_second) and sample.samples_per_second > 0.0 for sample in samples)


def test_report_can_skip_occ_sections_explicitly():
    report = generate_crucible_report(include_occ=False, perf_counts=(32,), perf_samples=1)

    assert report["boolean_nightmare"]["skipped"] is True
    assert report["step_round_trip"]["skipped"] is True
    assert report["performance_wall"][0]["feature_count"] == 32


@pytest.mark.skipif(not has_occ(), reason="pythonocc-core not available")
def test_boolean_nightmare_validates_all_ops():
    results = run_boolean_nightmare_test()

    assert set(results) == {"union", "difference", "intersection"}
    for result in results.values():
        assert result.metrics.valid
        assert result.metrics.faces > 0
        assert result.metrics.edges > 0
        assert result.metrics.solids > 0


@pytest.mark.skipif(not has_occ(), reason="pythonocc-core not available")
def test_step_round_trip_preserves_validity(tmp_path: Path):
    result = run_step_round_trip_test(tmp_path / "adaptive_pi_round_trip.step")

    assert result.write_ok
    assert result.read_ok
    assert result.original.valid
    assert result.imported.valid
    assert result.imported.faces > 0
    assert result.relative_volume_delta < 0.05