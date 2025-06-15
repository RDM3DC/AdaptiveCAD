import json
import adsk.core
from adaptivecad.ai.openai_bridge import call_openai
from adaptivecad.ai.translator import build_geometry
from adaptivecad.ui.slider_factory import build_sliders

_handlers = {}


def on_create(args: adsk.core.CommandCreatedEventArgs):
    """Create the initial UI for the AI-Generate command dialog"""
    cmd = args.command
    cmd.setDialogTitle("AI-Generate")
    cmd.okButtonText = "OK"
    
    inputs = cmd.commandInputs
    inputs.addStringValueInput("promptBox", "Prompt / Equation", "", "")
    cmd.isAutoExecute = False
    
    # Connect command handlers
    _handlers['execute'] = cmd.execute.add(on_execute)
    _handlers['input'] = cmd.inputChanged.add(on_input_changed)
    _handlers['destroy'] = cmd.destroy.add(on_destroy)


def on_execute(args: adsk.core.CommandEventArgs):
    """Call OpenAI and create sliders from the response"""
    inputs = args.command.commandInputs
    prompt = inputs.itemById("promptBox").value
    spec = call_openai(prompt)
    args.command.attributes.add("spec_json", json.dumps(spec))
    
    # Create sliders for all numeric parameters
    _handlers['sliders'] = build_sliders(inputs, spec)
    
    # Add regenerate button and separator
    inputs.addTextBoxCommandInput("separator", "", "<hr>", 1, True)
    inputs.addButtonRowCommandInput("regenerateRow", "Actions", False)
    regenerateButton = inputs.itemById("regenerateRow").listItems.add("Regenerate", False, "")
    
    # Build the geometry
    geom = build_geometry(spec)
    geom.to_fusion(layer="AI-Generated")


def on_input_changed(args: adsk.core.InputChangedEventArgs):
    """Handle slider changes and rebuild geometry"""
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
        # Send to Fusion layer
        geom.to_fusion(layer="AI-Generated")


def on_destroy(args: adsk.core.CommandEventArgs):
    """Clean up resources when the command is done"""
    global _handlers
    # Clear all event handlers to prevent memory leaks
    for handler in _handlers.values():
        if hasattr(handler, 'remove'):
            handler.remove()
    _handlers = {}


def register_command(**kwargs):
    """Register the AI-Generate command with Fusion 360"""
    import adsk.fusion
    app = adsk.core.Application.get()
    ui = app.userInterface
    
    # Get the command definitions collection
    cmdDefs = ui.commandDefinitions
    
    # Create a command definition
    cmdDef = cmdDefs.addButtonDefinition(
        kwargs.get('id', 'aiGenerateCmd'),
        kwargs.get('name', 'AI-Generate'),
        kwargs.get('description', 'Create geometry from prompt/equation with live sliders'),
        ''  # Resource folder for icons
    )
    
    # Connect to the command created event
    onCommandCreated = kwargs.get('create_handler', on_create)
    _handlers['commandCreated'] = cmdDef.commandCreated.add(onCommandCreated)
    
    # Add the command to the AI menu
    workspacePanel = ui.allToolbarPanels.itemById('SolidCreatePanel')
    if not workspacePanel:
        workspacePanel = ui.allToolbarPanels.itemById('ToolsPanel')  # fallback
    
    workspacePanel.controls.addCommand(cmdDef)
    return cmdDef
