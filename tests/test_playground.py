import importlib
import pytest


def test_playground_import():
    mod = importlib.import_module("adaptivecad.gui.playground")
    # Expect main import to succeed even without GUI deps
    assert hasattr(mod, "MainWindow")


def test_view_mode_methods_present():
    mod = importlib.import_module("adaptivecad.gui.playground")
    if not getattr(mod, "HAS_GUI", False):
        pytest.skip("GUI not available")
    mw = mod.MainWindow()
    # Methods should exist when GUI is available
    assert hasattr(mw, "add_view_mode_toolbar")
    assert hasattr(mw, "set_view_mode")


def test_playground_missing_deps(monkeypatch):
    import builtins

    calls = []

    def fake_import(name, *args, **kwargs):
        if name.startswith("PySide6") or name.startswith("OCC"):
            raise ImportError("mocked missing")
        return real_import(name, *args, **kwargs)

    real_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fake_import)

    mod = importlib.import_module("adaptivecad.gui.playground")
    with pytest.raises(RuntimeError):
        mod._require_gui_modules()
