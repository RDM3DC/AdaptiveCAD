import importlib
import builtins
import pytest


def test_commands_import():
    mod = importlib.import_module("adaptivecad.commands")
    assert hasattr(mod, "Feature")
    assert hasattr(mod, "NewBoxCmd")
    assert hasattr(mod, "ExportAmaCmd")


def test_commands_missing_deps(monkeypatch):
    real_import = builtins.__import__

    def fake(name, *args, **kwargs):
        if name.startswith("PySide6") or name.startswith("OCC"):
            raise ImportError("mocked missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake)

    mod = importlib.import_module("adaptivecad.commands")
    with pytest.raises(RuntimeError):
        mod._require_command_modules()
