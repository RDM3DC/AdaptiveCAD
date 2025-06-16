import importlib
import pytest


def test_pi_a_viewer_import():
    mod = importlib.import_module("adaptivecad.gui.pi_a_viewer")
    assert hasattr(mod, "main")


def test_pi_a_viewer_missing_deps(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("PySide6"):
            raise ImportError("mocked missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    mod = importlib.import_module("adaptivecad.gui.pi_a_viewer")
    with pytest.raises(RuntimeError):
        mod.main()
