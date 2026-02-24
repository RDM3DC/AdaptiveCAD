# AdaptiveCAD UI Improvements

This document describes the new UI components and improvements added to make AdaptiveCAD easier to use and more complete.

## Overview

The UI improvements focus on six key areas:

1. **Unified Theme System** - Consistent styling across all components
2. **Enhanced Menu & Toolbar Structure** - Better organization and discoverability
3. **Shape Creation Dialog** - Intuitive shape creation with live preview
4. **Properties Panel** - Advanced property editing with undo/redo
5. **Quick Access Toolbar** - Floating toolbar for common operations
6. **Onboarding System** - Interactive tutorials for new users

## New Components

### 1. Theme System (`adaptivecad/ui/theme.py`)

A comprehensive theming system with:

- **4 Built-in Themes**: Dark, Light, Midnight, Ocean
- **Full Qt Stylesheet**: Covers all standard widgets
- **Color Palette**: Consistent colors across the application
- **Typography Settings**: Font families and sizes
- **Spacing Constants**: Consistent spacing and border radii

```python
from adaptivecad.ui import apply_theme, list_themes

# Apply a theme
apply_theme(app, "dark")  # Options: dark, light, midnight, ocean

# Get available themes
themes = list_themes()  # ['dark', 'light', 'midnight', 'ocean']
```

### 2. Enhanced Window Components (`adaptivecad/ui/enhanced_window.py`)

New widgets for the main window:

- **ViewModeWidget**: Switch between Mesh (OCC) and SDF (Analytic) modes
- **ViewPresetsWidget**: Quick access to Top, Front, Right, ISO views
- **CoordinateDisplay**: Shows cursor X, Y, Z coordinates
- **SelectionInfo**: Displays current selection count and type
- **EnhancedStatusBar**: Combines all status information

Menu and toolbar builders:
- **MenuBuilder**: Helper for creating organized menus
- **ToolbarBuilder**: Helper for creating toolbars with widgets

```python
from adaptivecad.ui import setup_enhanced_menus, setup_main_toolbar, EnhancedStatusBar

# Set up menus
menu_builder = setup_enhanced_menus(main_window, callbacks)

# Set up toolbars
toolbar_builder = setup_main_toolbar(main_window, callbacks)

# Use enhanced status bar
status_bar = EnhancedStatusBar()
main_window.setStatusBar(status_bar)
status_bar.updateCoordinates(10.5, 20.3, 5.0)
status_bar.updateSelection(2, "object")
```

### 3. Shape Creation Dialog (`adaptivecad/ui/shape_dialog.py`)

A unified dialog for creating all shape types:

- **Categorized Shape List**: Basic, Advanced, Mathematical, Curves
- **Live 2D Preview**: Updates as parameters change
- **Parameter Sliders**: Easy value adjustment
- **Shape Definitions**: Extensible shape registry

```python
from adaptivecad.ui import ShapeCreationDialog, show_shape_dialog

# Show the dialog
result = show_shape_dialog(parent_widget)
if result:
    shape_id, params = result
    print(f"Create {shape_id} with {params}")

# Or use the dialog class directly
dialog = ShapeCreationDialog(parent)
dialog.shapeCreated.connect(lambda shape_id, params: create_shape(shape_id, params))
dialog.exec()
```

**Available Shapes:**

| Category | Shapes |
|----------|--------|
| Basic | Box, Cylinder, Sphere, Cone, Torus, Capsule |
| Advanced | Superellipse, Superquadric, Pi Shell, Helix, Ellipsoid |
| Mathematical | Möbius Strip, Klein Bottle, Gyroid, Mandelbulb, Menger Sponge |

### 4. Properties Panel (`adaptivecad/ui/properties_panel.py`)

Enhanced property editing:

- **Collapsible Sections**: Transform, Geometry, Appearance, Other
- **Type-Aware Editors**: Float, Int, String, Bool, Color, Vec3, Combo
- **Undo/Redo Stack**: Track and revert changes
- **Auto-categorization**: Properties grouped automatically

```python
from adaptivecad.ui import PropertiesPanel

# Create panel
panel = PropertiesPanel()

# Set object properties
panel.setObject(
    object_id="box_1",
    object_name="Box",
    properties={
        "position": (0, 0, 0),
        "width": 50.0,
        "height": 50.0,
        "depth": 50.0,
        "color": "#ff5500",
        "visible": True,
    }
)

# Handle property changes
panel.propertyChanged.connect(lambda obj_id, prop, val: update_object(obj_id, prop, val))
```

### 5. Quick Access Toolbar (`adaptivecad/ui/quick_access.py`)

Floating toolbar for common operations:

- **Customizable Actions**: Add/remove/reorder buttons
- **Drag to Reorder**: Rearrange by dragging
- **Persistent Config**: Saves user preferences
- **Context Menu**: Right-click to customize

```python
from adaptivecad.ui import QuickAccessToolbar, QuickAccessDock

# Floating version
toolbar = QuickAccessToolbar(parent)
toolbar.setCallback("new", lambda: new_project())
toolbar.setCallback("save", lambda: save_project())
toolbar.actionTriggered.connect(lambda action_id: handle_action(action_id))
toolbar.show()

# Docked version
dock = QuickAccessDock()
dock.setCallback("box", lambda: create_box())
```

**Default Quick Actions:**
- File: New, Open, Save
- Edit: Undo, Redo
- Create: Box, Cylinder, Sphere, Torus
- Transform: Move, Rotate, Delete

### 6. Onboarding System (`adaptivecad/ui/onboarding.py`)

Interactive tutorials and help:

- **Onboarding Wizard**: Step-by-step introduction
- **Feature Spotlights**: Highlight new features
- **Sample Projects**: Pre-made project templates
- **Tooltip Bubbles**: Contextual help

```python
from adaptivecad.ui import show_onboarding, show_sample_projects, FeatureSpotlight

# Show onboarding wizard (only first time)
show_onboarding(main_window)

# Show sample projects dialog
project = show_sample_projects(main_window)
if project:
    load_sample_project(project)

# Feature spotlight
spotlight = FeatureSpotlight(main_window)
spotlight.show_feature(
    "analytic_mode",
    mode_button,
    "New: Analytic Mode",
    "Try the new SDF rendering mode for perfect curves!"
)
```

**Sample Projects:**
1. Basic Shapes Demo
2. Boolean Operations
3. Mathematical Surfaces
4. Pi Geometry Showcase

## Menu Structure

The new menu structure is organized for better discoverability:

```
File
├── New Project (Ctrl+N)
├── Open Project... (Ctrl+O)
├── Save (Ctrl+S)
├── Save As... (Ctrl+Shift+S)
├── Import ▶
│   ├── Import STL...
│   ├── Import STEP...
│   └── Import OBJ...
├── Export ▶
│   ├── Export STL... (Ctrl+E)
│   ├── Export STEP...
│   └── Export G-Code...
└── Exit (Ctrl+Q)

Edit
├── Undo (Ctrl+Z)
├── Redo (Ctrl+Y)
├── Cut (Ctrl+X)
├── Copy (Ctrl+C)
├── Paste (Ctrl+V)
├── Delete (Del)
├── Select All (Ctrl+A)
└── Deselect All (Esc)

View
├── Viewport ▶
│   ├── Mesh Mode (OCC)
│   └── SDF Mode (Analytic)
├── Top View (Numpad 7)
├── Front View (Numpad 1)
├── Right View (Numpad 3)
├── Isometric View (Numpad 0)
├── Fit All (F)
├── Zoom to Selection (.)
├── Show Grid ☑
├── Show Axes ☑
├── Show Wireframe ☐
└── Panels ▶
    ├── Properties ☑
    ├── Hierarchy ☐
    ├── Console ☐
    └── AI Copilot ☐

Create
├── Basic Shapes ▶
│   ├── Box (B)
│   ├── Cylinder (C)
│   ├── Sphere (S)
│   ├── Cone
│   ├── Torus (T)
│   └── Capsule
├── Advanced Shapes ▶
│   ├── Superellipse
│   ├── Superquadric
│   ├── Pi Curve Shell
│   ├── Helix
│   └── Ellipsoid
├── Mathematical ▶
│   ├── Möbius Strip
│   ├── Klein Bottle
│   ├── Gyroid
│   ├── Mandelbulb
│   └── Menger Sponge
└── Sketch ▶
    ├── New Sketch
    ├── Line
    ├── Rectangle
    ├── Circle
    └── Arc

Transform
├── Move (G)
├── Rotate (R)
├── Scale
├── Mirror X
├── Mirror Y
├── Mirror Z
└── Boolean ▶
    ├── Union
    ├── Difference
    └── Intersection

Tools
├── Measure
├── Analyze
├── Simulation ▶
│   ├── Vibration Analysis
│   ├── Heat Generation
│   └── Stress Analysis
├── Conversion ▶
│   ├── OCC → Analytic
│   └── Analytic → Mesh
├── Custom Tools...
└── Record Macro...

Settings
├── Theme ▶
│   ├── Dark
│   ├── Light
│   ├── Midnight
│   └── Ocean
├── Preferences...
└── Keyboard Shortcuts...

Help
├── Getting Started
├── Documentation
├── Keyboard Shortcuts (?)
├── Diagnostics...
├── Enable Debug Logs ☐
└── About AdaptiveCAD
```

## Keyboard Shortcuts

### File Operations
| Action | Shortcut |
|--------|----------|
| New Project | Ctrl+N |
| Open Project | Ctrl+O |
| Save | Ctrl+S |
| Save As | Ctrl+Shift+S |
| Export STL | Ctrl+E |
| Exit | Ctrl+Q |

### Edit Operations
| Action | Shortcut |
|--------|----------|
| Undo | Ctrl+Z |
| Redo | Ctrl+Y |
| Cut | Ctrl+X |
| Copy | Ctrl+C |
| Paste | Ctrl+V |
| Delete | Del |
| Select All | Ctrl+A |
| Deselect | Esc |

### View Operations
| Action | Shortcut |
|--------|----------|
| Top View | Numpad 7 |
| Front View | Numpad 1 |
| Right View | Numpad 3 |
| Isometric | Numpad 0 |
| Fit All | F |
| Zoom Selection | . |
| Help | ? |

### Create Operations
| Action | Shortcut |
|--------|----------|
| Box | B |
| Cylinder | C |
| Sphere | S |
| Torus | T |

### Transform Operations
| Action | Shortcut |
|--------|----------|
| Move | G |
| Rotate | R |

## Integration Guide

To integrate these UI improvements into the existing MainWindow:

```python
from adaptivecad.ui import (
    apply_theme,
    setup_enhanced_menus,
    setup_main_toolbar,
    EnhancedStatusBar,
    PropertiesPanel,
    QuickAccessDock,
    show_onboarding,
)

class MainWindow:
    def __init__(self):
        # Apply theme
        apply_theme(self.app, "dark")
        
        # Show onboarding for new users
        show_onboarding(self.win)
        
        # Setup enhanced status bar
        self.status_bar = EnhancedStatusBar()
        self.win.setStatusBar(self.status_bar)
        
        # Setup properties panel
        self.properties_panel = PropertiesPanel()
        self.properties_dock = QDockWidget("Properties", self.win)
        self.properties_dock.setWidget(self.properties_panel)
        self.win.addDockWidget(Qt.LeftDockWidgetArea, self.properties_dock)
        
        # Setup quick access
        self.quick_access = QuickAccessDock()
        self.quick_access_dock = QDockWidget("Quick Access", self.win)
        self.quick_access_dock.setWidget(self.quick_access)
        self.win.addDockWidget(Qt.RightDockWidgetArea, self.quick_access_dock)
        
        # Setup menus with callbacks
        callbacks = {
            "new": self._new_project,
            "open": self._open_project,
            "save": self._save_project,
            # ... more callbacks
        }
        self.menu_builder = setup_enhanced_menus(self.win, callbacks)
        self.toolbar_builder = setup_main_toolbar(self.win, callbacks)
        
        # Connect property changes
        self.properties_panel.propertyChanged.connect(self._on_property_changed)
        
        # Connect quick access
        self.quick_access.actionTriggered.connect(self._on_quick_action)
```

## Future Improvements

Planned enhancements:

1. **Custom Themes**: Allow users to create and save custom themes
2. **Toolbar Customization UI**: Drag-and-drop toolbar editor
3. **Keyboard Shortcut Editor**: Customize all shortcuts
4. **Plugin UI Extensions**: Allow plugins to add UI components
5. **Workspace Layouts**: Save and restore window layouts
6. **Recent Files**: Track and display recently opened files
7. **Auto-save**: Periodic automatic saving
8. **Command Palette**: VS Code-style command search (Ctrl+Shift+P)

## Contributing

To add new UI components:

1. Create the component in `adaptivecad/ui/`
2. Follow the existing patterns for signals/slots
3. Add exports to `adaptivecad/ui/__init__.py`
4. Update this documentation
5. Add tests if applicable
