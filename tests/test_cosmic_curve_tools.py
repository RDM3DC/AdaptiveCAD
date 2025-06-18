from adaptivecad.cosmic_curve_tools import (
    BizarreCurveFeature,
    CosmicSplineFeature,
    NDFieldExplorerFeature,
)


def test_bizarre_curve_feature_init():
    feat = BizarreCurveFeature(1.0, 1.0, 1.0, 0.1, 5)
    assert feat.name == "BizarreCurve"
    assert isinstance(feat.params, dict)


def test_cosmic_spline_feature_init():
    pts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)]
    feat = CosmicSplineFeature(pts, 2, 0.5)
    assert feat.params["degree"] == 2


def test_ndfield_explorer_feature_init():
    feat = NDFieldExplorerFeature(3, 4, "scalar_wave")
    assert feat.ndfield.grid_shape == (4, 4, 4)
