from adaptivecad import (
    Event,
    minkowski_interval,
    apply_boost,
    light_cone,
)


def test_interval_invariance():
    e = Event(2.0, 1.0, 0.0, 0.0)
    boosted = apply_boost(e, 0.5)
    assert abs(minkowski_interval(e) - minkowski_interval(boosted)) < 1e-6

def test_light_cone_counts():
    e = Event(0.0, 0.0, 0.0, 0.0)
    future, past = light_cone(e, 1.0, steps=10)
    assert len(future) == 10
    assert len(past) == 10
