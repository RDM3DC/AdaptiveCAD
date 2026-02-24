"""
AdaptiveCAD UI Components

This module provides enhanced UI components for the AdaptiveCAD application.
"""

from .enhanced_window import (
    CoordinateDisplay,
    EnhancedStatusBar,
    MenuBuilder,
    SelectionInfo,
    ToolbarBuilder,
    ViewModeWidget,
    ViewPresetsWidget,
    setup_enhanced_menus,
    setup_main_toolbar,
)
from .onboarding import (
    FeatureSpotlight,
    OnboardingWizard,
    SampleProjectDialog,
    TooltipBubble,
    show_onboarding,
    show_sample_projects,
)
from .properties_panel import (
    BoolPropertyEditor,
    ColorPropertyEditor,
    ComboPropertyEditor,
    FloatPropertyEditor,
    IntPropertyEditor,
    PropertiesPanel,
    PropertyChange,
    PropertyEditor,
    PropertySection,
    StringPropertyEditor,
    UndoStack,
    Vec3PropertyEditor,
)
from .quick_access import (
    QuickAccessButton,
    QuickAccessDock,
    QuickAccessSeparator,
    QuickAccessToolbar,
    QuickAction,
)
from .shape_dialog import (
    SHAPE_DEFINITIONS,
    ShapeCategory,
    ShapeCreationDialog,
    ShapeDefinition,
    ShapeParameter,
    register_shape,
    show_shape_dialog,
)
from .theme import (
    DARK_THEME,
    LIGHT_THEME,
    MIDNIGHT_THEME,
    OCEAN_THEME,
    THEMES,
    ColorPalette,
    Spacing,
    Theme,
    ThemeMode,
    Typography,
    apply_theme,
    get_current_theme,
    get_theme,
    list_themes,
    set_current_theme,
)

__all__ = [
    # Theme
    "Theme",
    "ThemeMode",
    "ColorPalette",
    "Spacing",
    "Typography",
    "DARK_THEME",
    "LIGHT_THEME",
    "MIDNIGHT_THEME",
    "OCEAN_THEME",
    "THEMES",
    "get_theme",
    "get_current_theme",
    "set_current_theme",
    "apply_theme",
    "list_themes",
    # Enhanced Window
    "ViewModeWidget",
    "ViewPresetsWidget",
    "CoordinateDisplay",
    "SelectionInfo",
    "EnhancedStatusBar",
    "MenuBuilder",
    "ToolbarBuilder",
    "setup_enhanced_menus",
    "setup_main_toolbar",
    # Shape Dialog
    "ShapeCategory",
    "ShapeParameter",
    "ShapeDefinition",
    "SHAPE_DEFINITIONS",
    "register_shape",
    "ShapeCreationDialog",
    "show_shape_dialog",
    # Properties Panel
    "PropertyChange",
    "UndoStack",
    "PropertyEditor",
    "FloatPropertyEditor",
    "IntPropertyEditor",
    "StringPropertyEditor",
    "BoolPropertyEditor",
    "ColorPropertyEditor",
    "Vec3PropertyEditor",
    "ComboPropertyEditor",
    "PropertySection",
    "PropertiesPanel",
    # Quick Access
    "QuickAction",
    "QuickAccessButton",
    "QuickAccessSeparator",
    "QuickAccessToolbar",
    "QuickAccessDock",
    # Onboarding
    "OnboardingWizard",
    "SampleProjectDialog",
    "FeatureSpotlight",
    "TooltipBubble",
    "show_onboarding",
    "show_sample_projects",
]
