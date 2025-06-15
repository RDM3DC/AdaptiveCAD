import math
from adaptivecad.params import ParamEnv
from adaptivecad.commands import Feature


def test_param_env_basic():
    env = ParamEnv()
    env.set('x', 10)
    env.set('theta', 45)
    assert env.eval('x + 5') == 15
    val = env.eval('sin(theta)')
    assert math.isclose(val, math.sin(45), rel_tol=1e-9)


def test_feature_eval_param():
    env = ParamEnv()
    env.set('x', 3)
    feat = Feature('Box', {'l': '2*x', 'w': 5}, shape=None)
    assert feat.eval_param('l', env) == 6
    assert feat.eval_param('w', env) == 5
