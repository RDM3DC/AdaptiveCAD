import importlib
import sys
import types

import pytest


def test_slider_roundtrip(monkeypatch):
    # stub adsk modules before import
    adsk = types.ModuleType('adsk')

    class MockSlider:
        def __init__(self, id_, name, unit, min_val, max_val):
            self.id = id_
            self.valueOne = None
            self.delta = None
            self.min = min_val
            self.max = max_val

        def setSliderDelta(self, delta):
            self.delta = delta

    class MockCommandInputs:
        def __init__(self):
            self._inputs = []

        def addFloatSliderCommandInput(self, id_, name, unit, min_val, max_val):
            slider = MockSlider(id_, name, unit, min_val, max_val)
            self._inputs.append(slider)
            return slider

        def itemById(self, id_):
            for s in self._inputs:
                if s.id == id_:
                    return s
            return None

    class MockValueInput:
        @staticmethod
        def createByReal(val):
            return val

    adsk.core = types.SimpleNamespace(
        CommandInputs=MockCommandInputs,
        FloatSliderCommandInput=MockSlider,
        ValueInput=MockValueInput,
    )
    adsk.fusion = types.ModuleType('adsk.fusion')

    monkeypatch.setitem(sys.modules, 'adsk', adsk)
    monkeypatch.setitem(sys.modules, 'adsk.core', adsk.core)
    monkeypatch.setitem(sys.modules, 'adsk.fusion', adsk.fusion)

    slider_factory = importlib.import_module('adaptivecad.ui.slider_factory')

    spec = {
        'kind': 'solid',
        'primitive': 'cube',
        'parameters': {
            'edge': {'value': 10.0, 'min': 1.0, 'max': 20.0, 'step': 0.5}
        },
    }
    inputs = MockCommandInputs()
    mapping = slider_factory.build_sliders(inputs, spec)
    # simulate moving the slider
    slider = inputs.itemById('slider_edge')
    slider.valueOne = 15.0

    path = mapping['slider_edge'][0]
    ptr = spec
    for p in path[:-1]:
        ptr = ptr[p]
    ptr[path[-1]] = slider.valueOne

    assert spec['parameters']['edge'] == 15.0
