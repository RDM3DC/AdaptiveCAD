import json
import adsk.core
from adaptivecad.ai.openai_bridge import call_openai
from adaptivecad.ai.translator import build_geometry
from adaptivecad.ui.slider_factory import build_sliders

_handlers = {}


def on_create(args: adsk.core.CommandCreatedEventArgs):
    cmd = args.command
    inputs = cmd.commandInputs
    inputs.addStringValueInput("promptBox", "Prompt / Equation", "", "")
    cmd.isAutoExecute = False
    _handlers['execute'] = cmd.execute.add(on_execute)
    _handlers['input'] = cmd.inputChanged.add(on_input_changed)


def on_execute(args: adsk.core.CommandEventArgs):
    inputs = args.command.commandInputs
    prompt = inputs.itemById("promptBox").value
    spec = call_openai(prompt)
    args.command.attributes.add("spec_json", json.dumps(spec))
    _handlers['sliders'] = build_sliders(inputs, spec)


def on_input_changed(args: adsk.core.InputChangedEventArgs):
    attrib = args.command.attributes.itemByName("spec_json")
    if not attrib:
        return
    spec = json.loads(attrib.value)
    sliders = _handlers.get('sliders', {})
    changed = False
    for slider_id, (path, _val) in sliders.items():
        if args.input.id == slider_id:
            ptr = spec
            for elem in path[:-1]:
                ptr = ptr[elem]
            ptr[path[-1]] = args.input.valueOne
            changed = True
    if changed:
        geom = build_geometry(spec)
        # In real Fusion add-in you'd send to Fusion layer
        _handlers['last_geom'] = geom


def register_command(**kwargs):
    pass
