import numpy as np

from adaptivecad.game_engine import AdaptiveGameEngine, create_phase_bloom_demo_engine


def test_phase_bloom_demo_builds_scene():
    engine = create_phase_bloom_demo_engine()

    assert engine.player is not None
    assert engine.remaining_collectibles == 5
    assert len(engine.scene.prims) == 9


def test_player_moves_when_input_is_applied():
    engine = AdaptiveGameEngine()
    player = engine.spawn_player((0.0, 0.0, 0.0))
    start = player.position.copy()

    engine.input_state.forward = True
    for _ in range(30):
        engine.step(engine.fixed_dt)

    assert player.position[2] < start[2] - 0.2


def test_phase_pulse_excites_nearby_bloom():
    engine = AdaptiveGameEngine()
    engine.spawn_player((0.0, 0.0, 0.0))
    bloom = engine.spawn_collectible((1.25, 0.0, 0.0), orbit_speed=0.0, bob_amp=0.0, value=5)
    base_bloom = float(bloom.prim.params[1])

    engine.input_state.pulse = True
    engine.step(engine.fixed_dt)

    assert bloom.phase_bias > 0.0
    assert float(bloom.prim.params[1]) > base_bloom


def test_collecting_bloom_increases_score_and_removes_actor():
    engine = AdaptiveGameEngine()
    engine.spawn_player((0.0, 0.0, 0.0))
    bloom = engine.spawn_collectible((0.4, 0.0, 0.0), orbit_speed=0.0, bob_amp=0.0, value=9)

    engine.step(engine.fixed_dt)

    assert engine.score == 9
    assert engine.remaining_collectibles == 0
    assert bloom.entity_id not in engine.actors


def test_arena_edge_reflects_player_velocity():
    engine = AdaptiveGameEngine(arena_radius=2.0)
    player = engine.spawn_player((1.55, 0.0, 0.0))
    player.velocity = np.array([8.0, 0.0, 0.0], dtype=np.float64)

    engine.step(engine.fixed_dt)

    assert player.position[0] <= engine.arena_radius - player.radius + 1e-6
    assert player.velocity[0] < 0.0