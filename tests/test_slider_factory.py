import importlib
import sys
import types

import pytest


def test_slider_roundtrip(monkeypatch):
    # 1. Setup mock environment
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
            
        def addTextBoxCommandInput(self, id_, name, value, rows, readOnly):
            return None
            
        def addButtonRowCommandInput(self, id_, name, isMultiSelect):
            return MockButtonRow(id_)

        def itemById(self, id_):
            for s in self._inputs:
                if s.id == id_:
                    return s
            return None

    class MockValueInput:
        @staticmethod
        def createByReal(val):
            return val

    class MockButtonRow:
        def __init__(self, id_):
            self.id = id_
            self.listItems = MockListItems()
            
    class MockListItems:
        def __init__(self):
            self.items = []
            
        def add(self, name, isChecked, imageId):
            item = {"name": name, "isChecked": isChecked, "imageId": imageId}
            self.items.append(item)
            return item

    adsk.core = types.SimpleNamespace(
        CommandInputs=MockCommandInputs,
        FloatSliderCommandInput=MockSlider,
        ValueInput=MockValueInput,
    )
    adsk.fusion = types.ModuleType('adsk.fusion')

    monkeypatch.setitem(sys.modules, 'adsk', adsk)
    monkeypatch.setitem(sys.modules, 'adsk.core', adsk.core)
    monkeypatch.setitem(sys.modules, 'adsk.fusion', adsk.fusion)

    slider_factory = importlib.import_module('adaptivecad.ui.slider_factory')    # 2. Create a fake spec that matches the design document example
    spec = {
        'kind': 'solid',
        'primitive': 'cube',
        'parameters': {
            'edge': {'value': 10.0, 'min': 1.0, 'max': 100.0, 'step': 0.5}
        },
    }
    
    # 3. Create a mock CommandInputs object and build sliders
    inputs = MockCommandInputs()
    mapping = slider_factory.build_sliders(inputs, spec)
    
    # 4. Verify the sliders were created correctly
    assert 'slider_edge' in mapping
    assert mapping['slider_edge'][0] == ['parameters', 'edge']
    assert mapping['slider_edge'][1] == 10.0
    
    # 5. Simulate moving the slider
    slider = inputs.itemById('slider_edge')
    assert slider is not None
    slider.valueOne = 15.0
    
    # 6. Update the spec based on slider movement (what happens in on_input_changed)
    path = mapping['slider_edge'][0]
    ptr = spec
    for p in path[:-1]:
        ptr = ptr[p]
    ptr[path[-1]] = slider.valueOne
    
    # 7. Verify the parameter was updated correctly
    assert spec['parameters']['edge'] == 15.0
    
    # 8. Simulate retrieving the value that would be passed to build_geometry
    # which happens when the slider is moved in the UI
    translated_value = spec['parameters']['edge']
    assert translated_value == 15.0
