import importlib


def test_use_gpu_default():
    settings = importlib.import_module('adaptivecad.settings')
    assert hasattr(settings, 'USE_GPU')
    assert settings.USE_GPU is False
