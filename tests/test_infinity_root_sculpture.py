from __future__ import annotations

import json

import numpy as np
import pytest

from adaptivecad.geometry.infinity_root import (
    FractionalGaugeSpec,
    make_exact_lift_tower,
    make_infinity_root_book,
)
from adaptivecad.geometry.infinity_root_sculpture import (
    InfinityRootSculptureSpec,
    infinity_root_sculpture_mtl,
    infinity_root_sculpture_obj,
    infinity_root_sculpture_stl,
    make_infinity_root_sculpture,
)


def _sample_sculpture() -> dict:
    x = tuple(float(value) for value in np.geomspace(0.55, 1.8, 41))
    tower = make_exact_lift_tower(x, depth=2, residue=1.0, basepoint=1.0)
    gauge = FractionalGaugeSpec.power_mean(0.0)
    book = make_infinity_root_book(
        tower,
        fractional_pages=((0.5, gauge), (1.5, gauge)),
        radius=28.0,
        page_gap=4.5,
        radial_gain=0.25,
    )
    return make_infinity_root_sculpture(book)


def test_printable_sculpture_preserves_page_semantics() -> None:
    sculpture = _sample_sculpture()
    page_parts = [
        part
        for part in sculpture["parts"]
        if part["role"] in {"canonical_integer_page", "fractional_gauge_page"}
    ]

    assert sculpture["family"] == "infinity_root:book_sculpture"
    assert sculpture["units"] == "mm"
    assert sculpture["native_topology"] == "quad_only_closed_component_shells"
    assert [part["height"] for part in page_parts] == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert [part["canonical"] for part in page_parts] == [True, False, True, False, True]
    assert page_parts[1]["gauge"]["abel_equation_verified"] is False
    assert page_parts[0]["page_thickness_mm"] > page_parts[1]["page_thickness_mm"]
    assert page_parts[0]["band_width_mm"] > page_parts[1]["band_width_mm"]
    json.dumps(sculpture)


def test_sculpture_native_mesh_is_quad_only_and_each_component_is_closed() -> None:
    sculpture = _sample_sculpture()
    audit = sculpture["printability_audit"]
    vertices = np.asarray(sculpture["vertices"], dtype=float)

    assert sculpture["quads"]
    assert all(len(face) == 4 for face in sculpture["quads"])
    assert audit["native_faces_all_quads"] is True
    assert audit["all_component_shells_closed_edge_manifold"] is True
    assert audit["degenerate_quad_count"] == 0
    assert audit["flat_base_at_z_zero"] is True
    assert float(np.min(vertices[:, 2])) == pytest.approx(0.0, abs=1e-12)
    assert sculpture["bounds_mm"]["dimensions"][0] >= 124.0
    assert sculpture["bounds_mm"]["dimensions"][1] >= 70.0


def test_quad_obj_and_two_channel_stl_exports() -> None:
    sculpture = _sample_sculpture()
    obj = infinity_root_sculpture_obj(sculpture, material_filename="book.mtl")
    face_lines = [line for line in obj.splitlines() if line.startswith("f ")]

    assert "mtllib book.mtl" in obj
    assert "usemtl canonical_blue" in obj
    assert "usemtl gauge_gold" in obj
    assert len(face_lines) == len(sculpture["quads"])
    assert all(len(line.split()) == 5 for line in face_lines)
    assert "newmtl canonical_blue" in infinity_root_sculpture_mtl()
    assert "newmtl gauge_gold" in infinity_root_sculpture_mtl()

    full_stl = infinity_root_sculpture_stl(sculpture)
    blue_stl = infinity_root_sculpture_stl(sculpture, print_channels=("blue",))
    gold_stl = infinity_root_sculpture_stl(sculpture, print_channels=("gold",))
    full_facets = full_stl.count("facet normal")
    assert full_facets == 2 * len(sculpture["quads"])
    assert 0 < blue_stl.count("facet normal") < full_facets
    assert 0 < gold_stl.count("facet normal") < full_facets


def test_sculpture_rejects_wrong_source_and_unsafe_tilt() -> None:
    with pytest.raises(ValueError, match="expected an infinity_root:book"):
        make_infinity_root_sculpture({"family": "box"})
    with pytest.raises(ValueError, match="between 55 and 85"):
        InfinityRootSculptureSpec(tilt_degrees=45.0)
