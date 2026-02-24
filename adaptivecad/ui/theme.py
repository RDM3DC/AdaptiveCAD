"""
AdaptiveCAD Unified Theme System

Provides consistent styling across all UI components with support for
light/dark themes and user customization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

# Store theme preference
_current_theme: Optional["Theme"] = None


class ThemeMode(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


@dataclass
class ColorPalette:
    """Color definitions for a theme."""
    # Primary colors
    primary: str = "#2563eb"  # Blue accent
    primary_hover: str = "#3b82f6"
    primary_pressed: str = "#1d4ed8"
    
    # Background colors
    bg_window: str = "#0f1419"
    bg_panel: str = "#1a1f26"
    bg_input: str = "#0d1117"
    bg_hover: str = "#21262d"
    bg_selected: str = "#1f3a5f"
    
    # Border colors
    border: str = "#30363d"
    border_focused: str = "#58a6ff"
    
    # Text colors
    text_primary: str = "#e6edf3"
    text_secondary: str = "#8b949e"
    text_muted: str = "#6e7681"
    text_link: str = "#58a6ff"
    
    # Status colors
    success: str = "#3fb950"
    warning: str = "#d29922"
    error: str = "#f85149"
    info: str = "#58a6ff"
    
    # Viewport colors
    viewport_bg: str = "#0d1117"
    grid_major: str = "#30363d"
    grid_minor: str = "#21262d"


@dataclass
class Spacing:
    """Spacing and sizing constants."""
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    
    border_radius: int = 6
    border_radius_sm: int = 4
    border_radius_lg: int = 8


@dataclass
class Typography:
    """Font settings."""
    family: str = "Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif"
    family_mono: str = "Consolas, 'Courier New', monospace"
    size_xs: int = 10
    size_sm: int = 11
    size_md: int = 12
    size_lg: int = 14
    size_xl: int = 16
    size_title: int = 18


@dataclass
class Theme:
    """Complete theme definition."""
    name: str
    mode: ThemeMode
    colors: ColorPalette = field(default_factory=ColorPalette)
    spacing: Spacing = field(default_factory=Spacing)
    typography: Typography = field(default_factory=Typography)
    
    def get_stylesheet(self) -> str:
        """Generate the complete Qt stylesheet for this theme."""
        c = self.colors
        s = self.spacing
        t = self.typography
        
        return f"""
/* =====================================================
   AdaptiveCAD Theme: {self.name}
   ===================================================== */

/* Global Application Styles */
QMainWindow, QWidget {{
    background-color: {c.bg_window};
    color: {c.text_primary};
    font-family: {t.family};
    font-size: {t.size_md}px;
}}

/* Menu Bar */
QMenuBar {{
    background-color: {c.bg_panel};
    color: {c.text_primary};
    border-bottom: 1px solid {c.border};
    padding: 2px 0;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: {s.sm}px {s.md}px;
    border-radius: {s.border_radius_sm}px;
}}

QMenuBar::item:selected {{
    background-color: {c.bg_hover};
}}

QMenuBar::item:pressed {{
    background-color: {c.bg_selected};
}}

/* Menus */
QMenu {{
    background-color: {c.bg_panel};
    border: 1px solid {c.border};
    border-radius: {s.border_radius}px;
    padding: {s.xs}px 0;
}}

QMenu::item {{
    padding: {s.sm}px {s.lg}px;
    margin: 0 {s.xs}px;
    border-radius: {s.border_radius_sm}px;
}}

QMenu::item:selected {{
    background-color: {c.bg_hover};
}}

QMenu::item:disabled {{
    color: {c.text_muted};
}}

QMenu::separator {{
    height: 1px;
    background-color: {c.border};
    margin: {s.xs}px {s.sm}px;
}}

QMenu::indicator {{
    width: 16px;
    height: 16px;
    margin-left: {s.sm}px;
}}

/* Toolbars */
QToolBar {{
    background-color: {c.bg_panel};
    border: none;
    border-bottom: 1px solid {c.border};
    spacing: {s.xs}px;
    padding: {s.xs}px;
}}

QToolBar::separator {{
    width: 1px;
    background-color: {c.border};
    margin: {s.xs}px {s.sm}px;
}}

QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: {s.border_radius}px;
    padding: {s.sm}px;
    min-width: 28px;
    min-height: 28px;
}}

QToolButton:hover {{
    background-color: {c.bg_hover};
    border-color: {c.border};
}}

QToolButton:pressed {{
    background-color: {c.bg_selected};
}}

QToolButton:checked {{
    background-color: {c.primary};
    border-color: {c.primary};
}}

/* Dock Widgets */
QDockWidget {{
    titlebar-close-icon: url(none);
    titlebar-normal-icon: url(none);
    font-weight: bold;
}}

QDockWidget::title {{
    background-color: {c.bg_panel};
    padding: {s.sm}px {s.md}px;
    border-bottom: 1px solid {c.border};
    text-align: left;
}}

QDockWidget::close-button, QDockWidget::float-button {{
    background-color: transparent;
    border: none;
    padding: 2px;
}}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
    background-color: {c.bg_hover};
    border-radius: {s.border_radius_sm}px;
}}

/* Scroll Areas */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: {c.bg_window};
    width: 12px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {c.border};
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {c.text_muted};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: {c.bg_window};
    height: 12px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {c.border};
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {c.text_muted};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* Input Fields */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c.bg_input};
    border: 1px solid {c.border};
    border-radius: {s.border_radius}px;
    padding: {s.sm}px {s.md}px;
    color: {c.text_primary};
    selection-background-color: {c.bg_selected};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c.border_focused};
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {c.bg_panel};
    color: {c.text_muted};
}}

/* Spin Boxes */
QSpinBox, QDoubleSpinBox {{
    background-color: {c.bg_input};
    border: 1px solid {c.border};
    border-radius: {s.border_radius}px;
    padding: {s.sm}px {s.md}px;
    color: {c.text_primary};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {c.border_focused};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid {c.border};
    border-top-right-radius: {s.border_radius}px;
    background-color: {c.bg_panel};
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid {c.border};
    border-bottom-right-radius: {s.border_radius}px;
    background-color: {c.bg_panel};
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {c.bg_hover};
}}

/* Combo Boxes */
QComboBox {{
    background-color: {c.bg_input};
    border: 1px solid {c.border};
    border-radius: {s.border_radius}px;
    padding: {s.sm}px {s.md}px;
    padding-right: 24px;
    color: {c.text_primary};
    min-height: 20px;
}}

QComboBox:focus {{
    border-color: {c.border_focused};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {c.border};
    border-top-right-radius: {s.border_radius}px;
    border-bottom-right-radius: {s.border_radius}px;
    background-color: {c.bg_panel};
}}

QComboBox::down-arrow {{
    width: 12px;
    height: 12px;
}}

QComboBox QAbstractItemView {{
    background-color: {c.bg_panel};
    border: 1px solid {c.border};
    border-radius: {s.border_radius}px;
    selection-background-color: {c.bg_hover};
    outline: none;
}}

/* Buttons */
QPushButton {{
    background-color: {c.bg_panel};
    border: 1px solid {c.border};
    border-radius: {s.border_radius}px;
    padding: {s.sm}px {s.lg}px;
    color: {c.text_primary};
    min-width: 60px;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: {c.bg_hover};
    border-color: {c.border};
}}

QPushButton:pressed {{
    background-color: {c.bg_selected};
}}

QPushButton:disabled {{
    background-color: {c.bg_panel};
    color: {c.text_muted};
    border-color: {c.border};
}}

/* Primary Buttons */
QPushButton[primary="true"], QPushButton#primaryButton {{
    background-color: {c.primary};
    border-color: {c.primary};
    color: white;
}}

QPushButton[primary="true"]:hover, QPushButton#primaryButton:hover {{
    background-color: {c.primary_hover};
    border-color: {c.primary_hover};
}}

QPushButton[primary="true"]:pressed, QPushButton#primaryButton:pressed {{
    background-color: {c.primary_pressed};
    border-color: {c.primary_pressed};
}}

/* Checkboxes and Radio Buttons */
QCheckBox, QRadioButton {{
    spacing: {s.sm}px;
    color: {c.text_primary};
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c.border};
    background-color: {c.bg_input};
}}

QCheckBox::indicator {{
    border-radius: {s.border_radius_sm}px;
}}

QRadioButton::indicator {{
    border-radius: 8px;
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {c.primary};
    border-color: {c.primary};
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {c.border_focused};
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 6px;
    background-color: {c.bg_input};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    width: 16px;
    height: 16px;
    margin: -5px 0;
    background-color: {c.primary};
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {c.primary_hover};
}}

QSlider::sub-page:horizontal {{
    background-color: {c.primary};
    border-radius: 3px;
}}

QSlider::groove:vertical {{
    width: 6px;
    background-color: {c.bg_input};
    border-radius: 3px;
}}

QSlider::handle:vertical {{
    width: 16px;
    height: 16px;
    margin: 0 -5px;
    background-color: {c.primary};
    border-radius: 8px;
}}

QSlider::handle:vertical:hover {{
    background-color: {c.primary_hover};
}}

QSlider::sub-page:vertical {{
    background-color: {c.primary};
    border-radius: 3px;
}}

/* Progress Bars */
QProgressBar {{
    background-color: {c.bg_input};
    border: 1px solid {c.border};
    border-radius: {s.border_radius}px;
    text-align: center;
    color: {c.text_primary};
    height: 20px;
}}

QProgressBar::chunk {{
    background-color: {c.primary};
    border-radius: {s.border_radius_sm}px;
}}

/* Tab Widget */
QTabWidget::pane {{
    border: 1px solid {c.border};
    border-radius: {s.border_radius}px;
    background-color: {c.bg_panel};
}}

QTabBar::tab {{
    background-color: {c.bg_window};
    border: 1px solid {c.border};
    border-bottom: none;
    padding: {s.sm}px {s.lg}px;
    margin-right: 2px;
    border-top-left-radius: {s.border_radius}px;
    border-top-right-radius: {s.border_radius}px;
}}

QTabBar::tab:selected {{
    background-color: {c.bg_panel};
    border-bottom: 1px solid {c.bg_panel};
}}

QTabBar::tab:hover:!selected {{
    background-color: {c.bg_hover};
}}

/* Group Boxes */
QGroupBox {{
    border: 1px solid {c.border};
    border-radius: {s.border_radius}px;
    margin-top: 12px;
    padding-top: {s.md}px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {s.md}px;
    padding: 0 {s.sm}px;
    color: {c.text_secondary};
}}

/* List and Tree Views */
QListView, QTreeView, QTableView {{
    background-color: {c.bg_input};
    border: 1px solid {c.border};
    border-radius: {s.border_radius}px;
    outline: none;
}}

QListView::item, QTreeView::item, QTableView::item {{
    padding: {s.sm}px;
    border-radius: {s.border_radius_sm}px;
}}

QListView::item:selected, QTreeView::item:selected, QTableView::item:selected {{
    background-color: {c.bg_selected};
}}

QListView::item:hover, QTreeView::item:hover, QTableView::item:hover {{
    background-color: {c.bg_hover};
}}

QHeaderView::section {{
    background-color: {c.bg_panel};
    border: none;
    border-right: 1px solid {c.border};
    border-bottom: 1px solid {c.border};
    padding: {s.sm}px {s.md}px;
    font-weight: bold;
}}

/* Status Bar */
QStatusBar {{
    background-color: {c.bg_panel};
    border-top: 1px solid {c.border};
    color: {c.text_secondary};
    padding: {s.xs}px;
}}

QStatusBar::item {{
    border: none;
}}

/* Tool Tips */
QToolTip {{
    background-color: {c.bg_panel};
    border: 1px solid {c.border};
    border-radius: {s.border_radius_sm}px;
    padding: {s.sm}px;
    color: {c.text_primary};
}}

/* Message Boxes and Dialogs */
QMessageBox, QDialog {{
    background-color: {c.bg_window};
}}

QMessageBox QPushButton {{
    min-width: 80px;
}}

/* Labels */
QLabel {{
    color: {c.text_primary};
}}

QLabel[heading="true"] {{
    font-size: {t.size_lg}px;
    font-weight: bold;
    color: {c.text_primary};
}}

QLabel[subheading="true"] {{
    font-size: {t.size_md}px;
    color: {c.text_secondary};
}}

QLabel[muted="true"] {{
    color: {c.text_muted};
}}

/* Splitters */
QSplitter::handle {{
    background-color: {c.border};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

QSplitter::handle:hover {{
    background-color: {c.primary};
}}

/* Custom Classes */
.SectionHeader {{
    font-size: {t.size_lg}px;
    font-weight: bold;
    color: {c.text_primary};
    padding: {s.md}px 0;
    border-bottom: 1px solid {c.border};
    margin-bottom: {s.md}px;
}}

.PropertyLabel {{
    color: {c.text_secondary};
    font-size: {t.size_sm}px;
}}

.PropertyValue {{
    color: {c.text_primary};
    font-weight: bold;
}}

.ToolCategory {{
    background-color: {c.bg_hover};
    border-radius: {s.border_radius}px;
    padding: {s.sm}px;
    margin: {s.xs}px 0;
}}
"""

    def get_colors(self) -> ColorPalette:
        """Get the color palette for this theme."""
        return self.colors
    
    def get_spacing(self) -> Spacing:
        """Get the spacing constants for this theme."""
        return self.spacing
    
    def get_typography(self) -> Typography:
        """Get the typography settings for this theme."""
        return self.typography


# Predefined themes
DARK_THEME = Theme(
    name="Dark",
    mode=ThemeMode.DARK,
    colors=ColorPalette()  # Uses dark defaults
)

LIGHT_THEME = Theme(
    name="Light",
    mode=ThemeMode.LIGHT,
    colors=ColorPalette(
        primary="#2563eb",
        primary_hover="#3b82f6",
        primary_pressed="#1d4ed8",
        bg_window="#f5f5f5",
        bg_panel="#ffffff",
        bg_input="#ffffff",
        bg_hover="#e8e8e8",
        bg_selected="#dbeafe",
        border="#d1d5db",
        border_focused="#2563eb",
        text_primary="#1f2937",
        text_secondary="#4b5563",
        text_muted="#9ca3af",
        text_link="#2563eb",
        success="#16a34a",
        warning="#ca8a04",
        error="#dc2626",
        info="#2563eb",
        viewport_bg="#f0f0f0",
        grid_major="#c0c0c0",
        grid_minor="#e0e0e0",
    )
)

MIDNIGHT_THEME = Theme(
    name="Midnight",
    mode=ThemeMode.DARK,
    colors=ColorPalette(
        primary="#8b5cf6",  # Purple accent
        primary_hover="#a78bfa",
        primary_pressed="#7c3aed",
        bg_window="#0a0a0f",
        bg_panel="#12121a",
        bg_input="#08080c",
        bg_hover="#1a1a25",
        bg_selected="#2d1f5e",
        border="#2a2a3a",
        border_focused="#8b5cf6",
        text_primary="#e4e4eb",
        text_secondary="#9898a8",
        text_muted="#5c5c6c",
        text_link="#a78bfa",
        success="#4ade80",
        warning="#facc15",
        error="#f87171",
        info="#8b5cf6",
        viewport_bg="#08080c",
        grid_major="#2a2a3a",
        grid_minor="#18181f",
    )
)

OCEAN_THEME = Theme(
    name="Ocean",
    mode=ThemeMode.DARK,
    colors=ColorPalette(
        primary="#06b6d4",  # Cyan accent
        primary_hover="#22d3ee",
        primary_pressed="#0891b2",
        bg_window="#0c1929",
        bg_panel="#122337",
        bg_input="#091520",
        bg_hover="#1a3049",
        bg_selected="#164e63",
        border="#1e3a5f",
        border_focused="#06b6d4",
        text_primary="#e0f2fe",
        text_secondary="#7dd3fc",
        text_muted="#38bdf8",
        text_link="#22d3ee",
        success="#34d399",
        warning="#fbbf24",
        error="#fb7185",
        info="#06b6d4",
        viewport_bg="#091520",
        grid_major="#1e3a5f",
        grid_minor="#122337",
    )
)

# Theme registry
THEMES: Dict[str, Theme] = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
    "midnight": MIDNIGHT_THEME,
    "ocean": OCEAN_THEME,
}


def get_theme(name: str = "dark") -> Theme:
    """Get a theme by name."""
    return THEMES.get(name.lower(), DARK_THEME)


def get_current_theme() -> Theme:
    """Get the currently active theme."""
    global _current_theme
    if _current_theme is None:
        _current_theme = DARK_THEME
    return _current_theme


def set_current_theme(theme: Theme) -> None:
    """Set the current theme."""
    global _current_theme
    _current_theme = theme


def apply_theme(app, theme_name: str = "dark") -> Theme:
    """Apply a theme to the entire application."""
    theme = get_theme(theme_name)
    set_current_theme(theme)
    app.setStyleSheet(theme.get_stylesheet())
    return theme


def list_themes() -> list[str]:
    """List all available theme names."""
    return list(THEMES.keys())
