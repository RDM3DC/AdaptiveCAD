import math

import numpy as np

from adaptivecad.aacore.sdf import KIND_PI_BLOOM, Prim, Scene, sd_pi_bloom
from adaptivecad.app.shape_creation import create_prim_from_definition


def test_sd_pi_bloom_is_signed_and_directional():
    radius = 1.0
    bloom = 0.32
    petals = 7.0
    crown = 0.24

    assert sd_pi_bloom(np.array([0.0, 0.0, 0.0]), radius, bloom, petals, crown) < 0.0
    assert sd_pi_bloom(np.array([3.0, 0.0, 0.0]), radius, bloom, petals, crown) > 0.0

    phi_peak = math.pi / (2.0 * petals)
    phi_valley = -math.pi / (2.0 * petals)
    p_peak = np.array([1.15 * math.cos(phi_peak), 1.15 * math.sin(phi_peak), 0.0])
    p_valley = np.array([1.15 * math.cos(phi_valley), 1.15 * math.sin(phi_valley), 0.0])

    assert sd_pi_bloom(p_peak, radius, bloom, petals, crown) < sd_pi_bloom(p_valley, radius, bloom, petals, crown)


def test_pi_bloom_packs_to_gpu_structs():
    scene = Scene()
    scene.add(Prim(KIND_PI_BLOOM, [0.9, 0.32, 7.0, 0.24], beta=0.04))
    gpu = scene.to_gpu_structs()

    assert int(gpu["count"]) == 1
    assert int(gpu["kind"][0]) == KIND_PI_BLOOM
    assert gpu["params"][0, 0] == np.float32(0.9)
    assert gpu["params"][0, 2] == np.float32(7.0)


def test_shape_creation_builds_pi_bloom_prim():
    prim = create_prim_from_definition(
        "pi_bloom",
        {
            "radius": 1.1,
            "bloom": 0.4,
            "petals": 9,
            "crown": 0.18,
            "pos_x": 1.0,
            "pos_y": -2.0,
            "pos_z": 0.5,
        },
    )

    assert prim is not None
    assert prim.kind == KIND_PI_BLOOM
    assert np.allclose(prim.params, np.array([1.1, 0.4, 9.0, 0.18]))
    assert np.allclose(prim.xform.M[:3, 3], np.array([1.0, -2.0, 0.5], dtype=np.float32))


def test_pi_bloom_near_poles_damps_phi_singularity():
    radius = 1.0
    probe_radius = 1.1
    theta = 0.02
    crown = 0.8
    values = []

    for phi in np.linspace(0.0, 2.0 * math.pi, 32, endpoint=False):
        p = np.array(
            [
                probe_radius * math.sin(theta) * math.cos(phi),
                probe_radius * math.sin(theta) * math.sin(phi),
                probe_radius * math.cos(theta),
            ],
            dtype=np.float64,
        )
        values.append(sd_pi_bloom(p, radius, bloom=0.95, petals=8.0, crown=crown))

    assert max(values) - min(values) < 0.2