"""
AdaptiveCAD Onboarding & Tutorial System

Provides interactive onboarding, feature highlights, tooltips,
and sample project templates for new users.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

# Qt6 enum compatibility
try:
    _WA_TransparentForMouseEvents = Qt.WidgetAttribute.WA_TransparentForMouseEvents
    _WA_TranslucentBackground = Qt.WidgetAttribute.WA_TranslucentBackground
    _Tool = Qt.WindowType.Tool
    _FramelessWindowHint = Qt.WindowType.FramelessWindowHint
    _AlignRight = Qt.AlignmentFlag.AlignRight
    _PointingHandCursor = Qt.CursorShape.PointingHandCursor
    _InOutQuad = QEasingCurve.Type.InOutQuad
    _Antialiasing = QPainter.RenderHint.Antialiasing
    _CompositionMode_Clear = QPainter.CompositionMode.CompositionMode_Clear
    _CompositionMode_SourceOver = QPainter.CompositionMode.CompositionMode_SourceOver
    _Accepted = QDialog.DialogCode.Accepted
except AttributeError:
    _WA_TransparentForMouseEvents = Qt.WA_TransparentForMouseEvents
    _WA_TranslucentBackground = Qt.WA_TranslucentBackground
    _Tool = Qt.Tool
    _FramelessWindowHint = Qt.FramelessWindowHint
    _AlignRight = Qt.AlignRight
    _PointingHandCursor = Qt.PointingHandCursor
    _InOutQuad = QEasingCurve.InOutQuad
    _Antialiasing = QPainter.Antialiasing
    _CompositionMode_Clear = QPainter.CompositionMode_Clear
    _CompositionMode_SourceOver = QPainter.CompositionMode_SourceOver
    _Accepted = QDialog.Accepted


# Onboarding steps
ONBOARDING_STEPS = [
    {
        "id": "welcome",
        "title": "Welcome to AdaptiveCAD!",
        "content": """
<h2>Welcome to AdaptiveCAD</h2>
<p>AdaptiveCAD is a modern, curvature-first CAD system based on the 
<b>Adaptive Pi Geometry (π<sub>a</sub>)</b> principles.</p>

<p>This quick tour will show you the basics:</p>
<ul>
<li>Creating shapes</li>
<li>Transforming objects</li>
<li>Using the viewport</li>
<li>Working with the analytic SDF renderer</li>
</ul>

<p>Click <b>Next</b> to begin, or <b>Skip</b> to start exploring on your own.</p>
""",
        "highlight": None,
    },
    {
        "id": "viewport",
        "title": "The Viewport",
        "content": """
<h3>The 3D Viewport</h3>
<p>The main area shows your 3D workspace. You can:</p>
<ul>
<li><b>Rotate:</b> Middle mouse button or Alt + Left mouse</li>
<li><b>Pan:</b> Shift + Middle mouse or right mouse</li>
<li><b>Zoom:</b> Scroll wheel</li>
<li><b>Fit All:</b> Press <kbd>F</kbd></li>
</ul>

<p>Use the <b>ViewCube</b> in the corner for quick view presets.</p>
""",
        "highlight": "viewport",
    },
    {
        "id": "toolbars",
        "title": "Toolbars",
        "content": """
<h3>Toolbars & Menus</h3>
<p>The toolbar provides quick access to common operations:</p>
<ul>
<li><b>File operations:</b> New, Open, Save</li>
<li><b>Edit operations:</b> Undo, Redo</li>
<li><b>View modes:</b> Switch between Mesh and SDF modes</li>
<li><b>Create tools:</b> Box, Cylinder, Sphere, etc.</li>
</ul>

<p>All features are also available in the <b>menu bar</b> with keyboard shortcuts.</p>
""",
        "highlight": "toolbar",
    },
    {
        "id": "creating_shapes",
        "title": "Creating Shapes",
        "content": """
<h3>Creating Shapes</h3>
<p>Create shapes using:</p>
<ul>
<li><b>Create menu:</b> Access all available shapes</li>
<li><b>Keyboard shortcuts:</b>
    <ul>
    <li><kbd>B</kbd> - Box</li>
    <li><kbd>C</kbd> - Cylinder</li>
    <li><kbd>S</kbd> - Sphere</li>
    <li><kbd>T</kbd> - Torus</li>
    </ul>
</li>
<li><b>Shape Dialog:</b> Use Create → Shape... for advanced options with preview</li>
</ul>
""",
        "highlight": "create_menu",
    },
    {
        "id": "transforming",
        "title": "Transforming Objects",
        "content": """
<h3>Transforming Objects</h3>
<p>Select objects by clicking, then transform using:</p>
<ul>
<li><kbd>G</kbd> - <b>Move</b> (Grab)</li>
<li><kbd>R</kbd> - <b>Rotate</b></li>
<li><kbd>S</kbd> - <b>Scale</b> (when in transform mode)</li>
<li><kbd>Del</kbd> - <b>Delete</b></li>
</ul>

<p>Use the <b>Properties Panel</b> on the left for precise editing.</p>
""",
        "highlight": "transform_toolbar",
    },
    {
        "id": "analytic_mode",
        "title": "Analytic SDF Mode",
        "content": """
<h3>Analytic SDF Rendering</h3>
<p>AdaptiveCAD features a unique <b>Analytic SDF Renderer</b> that renders 
shapes mathematically without triangulation!</p>

<p>Benefits:</p>
<ul>
<li>Perfect curves at any zoom level</li>
<li>Real-time boolean operations</li>
<li>Mathematical surfaces (gyroid, mobius, etc.)</li>
</ul>

<p>Switch modes using the <b>Mode</b> buttons in the toolbar, or use 
<b>Settings → View → Analytic Viewport</b>.</p>
""",
        "highlight": "mode_selector",
    },
    {
        "id": "finish",
        "title": "You're Ready!",
        "content": """
<h3>You're All Set!</h3>
<p>You now know the basics of AdaptiveCAD. Here are some next steps:</p>

<ul>
<li>Try creating a project with multiple shapes</li>
<li>Experiment with boolean operations (Union, Cut)</li>
<li>Explore mathematical shapes in the Create → Mathematical menu</li>
<li>Check out the sample projects in File → Open Recent</li>
</ul>

<p>Need help? Press <kbd>?</kbd> or visit <b>Help → Documentation</b>.</p>

<p>Happy designing! 🚀</p>
""",
        "highlight": None,
    },
]


# Sample project templates
SAMPLE_PROJECTS = [
    {
        "id": "basic_shapes",
        "name": "Basic Shapes Demo",
        "description": "A simple project with basic primitive shapes",
        "thumbnail": "basic_shapes",
        "shapes": [
            {"type": "box", "params": {"width": 40, "height": 40, "depth": 40}, "position": (-50, 0, 0)},
            {"type": "cylinder", "params": {"radius": 20, "height": 60}, "position": (0, 0, 0)},
            {"type": "sphere", "params": {"radius": 25}, "position": (50, 0, 0)},
        ],
    },
    {
        "id": "boolean_demo",
        "name": "Boolean Operations",
        "description": "Demonstrates union, difference, and intersection",
        "thumbnail": "boolean",
        "shapes": [
            {"type": "box", "params": {"width": 50, "height": 50, "depth": 50}, "position": (0, 0, 0)},
            {"type": "sphere", "params": {"radius": 35}, "position": (0, 0, 0)},
        ],
    },
    {
        "id": "math_surfaces",
        "name": "Mathematical Surfaces",
        "description": "Showcase of mathematical surfaces and fractals",
        "thumbnail": "math",
        "shapes": [
            {"type": "mobius", "params": {"radius": 30, "width": 10}, "position": (-60, 0, 0)},
            {"type": "gyroid", "params": {"size": 40, "scale": 8}, "position": (0, 0, 0)},
            {"type": "torus", "params": {"major_radius": 25, "minor_radius": 8}, "position": (60, 0, 0)},
        ],
    },
    {
        "id": "pi_geometry",
        "name": "Pi Geometry Showcase",
        "description": "Shapes based on Adaptive Pi principles",
        "thumbnail": "pi",
        "shapes": [
            {"type": "superellipse", "params": {"a": 30, "b": 20, "n": 3}, "position": (-40, 0, 0)},
            {"type": "pi_shell", "params": {"radius": 25, "beta": 0.3}, "position": (40, 0, 0)},
        ],
    },
]


@dataclass
class TooltipHighlight:
    """Definition of a tooltip/highlight."""
    id: str
    widget_name: str
    title: str
    content: str
    position: str = "bottom"  # top, bottom, left, right
    arrow: bool = True
    pulse: bool = False


class HighlightOverlay(QWidget):
    """Overlay widget that highlights a target widget."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.target_rect: Optional[QRect] = None
        self.setAttribute(_WA_TransparentForMouseEvents)
        self.setAttribute(_WA_TranslucentBackground)
        
        # Animation
        self._opacity = 0.0
        self._animation = QPropertyAnimation(self, b"opacity")
        self._animation.setDuration(300)
        self._animation.setEasingCurve(_InOutQuad)
    
    def setTargetRect(self, rect: QRect):
        """Set the rectangle to highlight."""
        self.target_rect = rect
        self.update()
    
    def show_animated(self):
        """Show with fade-in animation."""
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.start()
        self.show()
    
    def hide_animated(self):
        """Hide with fade-out animation."""
        self._animation.setStartValue(1.0)
        self._animation.setEndValue(0.0)
        self._animation.finished.connect(self.hide)
        self._animation.start()
    
    def paintEvent(self, event):
        if not self.target_rect:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(_Antialiasing)
        
        # Draw semi-transparent overlay
        overlay_color = QColor(0, 0, 0, int(180 * self._opacity))
        painter.fillRect(self.rect(), overlay_color)
        
        # Cut out the target area
        painter.setCompositionMode(_CompositionMode_Clear)
        margin = 4
        cutout = self.target_rect.adjusted(-margin, -margin, margin, margin)
        path = QPainterPath()
        path.addRoundedRect(cutout, 8, 8)
        painter.fillPath(path, QColor(0, 0, 0, 0))
        
        # Draw highlight border
        painter.setCompositionMode(_CompositionMode_SourceOver)
        pen = QPen(QColor("#58a6ff"))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawRoundedRect(cutout, 8, 8)


class TooltipBubble(QWidget):
    """A tooltip bubble with content and optional arrow."""
    
    closed = Signal()
    nextClicked = Signal()
    prevClicked = Signal()
    
    def __init__(
        self,
        title: str,
        content: str,
        position: str = "bottom",
        show_nav: bool = True,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.position = position
        self.show_nav = show_nav
        
        self.setWindowFlags(_Tool | _FramelessWindowHint)
        self.setAttribute(_WA_TranslucentBackground)
        
        self._setup_ui(title, content)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
    
    def _setup_ui(self, title: str, content: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Container
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #1a1f26;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(16, 12, 16, 12)
        container_layout.setSpacing(8)
        
        # Title
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("color: #e6edf3; font-size: 14px;")
        container_layout.addWidget(title_label)
        
        # Content
        content_label = QTextBrowser()
        content_label.setHtml(content)
        content_label.setOpenExternalLinks(True)
        content_label.setStyleSheet("""
            QTextBrowser {
                background-color: transparent;
                border: none;
                color: #8b949e;
                font-size: 12px;
            }
        """)
        content_label.setMaximumHeight(200)
        container_layout.addWidget(content_label)
        
        # Navigation buttons
        if self.show_nav:
            nav_layout = QHBoxLayout()
            nav_layout.setSpacing(8)
            
            self.prev_btn = QPushButton("← Back")
            self.prev_btn.clicked.connect(self.prevClicked.emit)
            
            self.skip_btn = QPushButton("Skip")
            self.skip_btn.clicked.connect(self.closed.emit)
            
            self.next_btn = QPushButton("Next →")
            self.next_btn.setObjectName("primaryButton")
            self.next_btn.clicked.connect(self.nextClicked.emit)
            
            nav_layout.addWidget(self.prev_btn)
            nav_layout.addStretch()
            nav_layout.addWidget(self.skip_btn)
            nav_layout.addWidget(self.next_btn)
            
            container_layout.addLayout(nav_layout)
        else:
            close_btn = QPushButton("Got it!")
            close_btn.setObjectName("primaryButton")
            close_btn.clicked.connect(self.closed.emit)
            container_layout.addWidget(close_btn, alignment=_AlignRight)
        
        layout.addWidget(container)
    
    def setNavEnabled(self, prev_enabled: bool, next_enabled: bool):
        """Enable/disable navigation buttons."""
        if hasattr(self, 'prev_btn'):
            self.prev_btn.setEnabled(prev_enabled)
        if hasattr(self, 'next_btn'):
            self.next_btn.setEnabled(next_enabled)
    
    def setNextText(self, text: str):
        """Set the next button text."""
        if hasattr(self, 'next_btn'):
            self.next_btn.setText(text)


class OnboardingWizard(QDialog):
    """Full-screen onboarding wizard."""
    
    finished = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to AdaptiveCAD")
        self.setModal(True)
        self.resize(600, 500)
        
        self.current_step = 0
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked widget for steps
        self.stack = QStackedWidget()
        
        for step in ONBOARDING_STEPS:
            page = self._create_step_page(step)
            self.stack.addWidget(page)
        
        layout.addWidget(self.stack)
        
        # Navigation footer
        footer = QFrame()
        footer.setStyleSheet("background-color: #0f1419; border-top: 1px solid #30363d;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        
        # Progress dots
        self.progress_layout = QHBoxLayout()
        self.progress_layout.setSpacing(8)
        
        for i in range(len(ONBOARDING_STEPS)):
            dot = QLabel("●" if i == 0 else "○")
            dot.setStyleSheet("color: #58a6ff;" if i == 0 else "color: #6e7681;")
            self.progress_layout.addWidget(dot)
        
        footer_layout.addLayout(self.progress_layout)
        footer_layout.addStretch()
        
        # Navigation buttons
        self.prev_btn = QPushButton("← Back")
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._go_prev)
        
        self.skip_btn = QPushButton("Skip Tour")
        self.skip_btn.clicked.connect(self._skip)
        
        self.next_btn = QPushButton("Next →")
        self.next_btn.setObjectName("primaryButton")
        self.next_btn.clicked.connect(self._go_next)
        
        footer_layout.addWidget(self.prev_btn)
        footer_layout.addWidget(self.skip_btn)
        footer_layout.addWidget(self.next_btn)
        
        layout.addWidget(footer)
    
    def _create_step_page(self, step: dict) -> QWidget:
        """Create a page widget for an onboarding step."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        
        # Content
        content = QTextBrowser()
        content.setHtml(step["content"])
        content.setOpenExternalLinks(True)
        content.setStyleSheet("""
            QTextBrowser {
                background-color: transparent;
                border: none;
                color: #e6edf3;
                font-size: 14px;
            }
            QTextBrowser h2 {
                color: #58a6ff;
            }
            QTextBrowser h3 {
                color: #e6edf3;
            }
            QTextBrowser kbd {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 3px;
                padding: 2px 6px;
                font-family: monospace;
            }
        """)
        
        layout.addWidget(content)
        
        return page
    
    def _update_progress(self):
        """Update progress dots."""
        for i in range(self.progress_layout.count()):
            dot = self.progress_layout.itemAt(i).widget()
            if isinstance(dot, QLabel):
                dot.setText("●" if i <= self.current_step else "○")
                dot.setStyleSheet(
                    "color: #58a6ff;" if i <= self.current_step else "color: #6e7681;"
                )
        
        # Update buttons
        self.prev_btn.setEnabled(self.current_step > 0)
        
        is_last = self.current_step == len(ONBOARDING_STEPS) - 1
        self.next_btn.setText("Get Started!" if is_last else "Next →")
        self.skip_btn.setVisible(not is_last)
    
    def _go_next(self):
        """Go to next step."""
        if self.current_step < len(ONBOARDING_STEPS) - 1:
            self.current_step += 1
            self.stack.setCurrentIndex(self.current_step)
            self._update_progress()
        else:
            self._finish()
    
    def _go_prev(self):
        """Go to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self.stack.setCurrentIndex(self.current_step)
            self._update_progress()
    
    def _skip(self):
        """Skip the tour."""
        self._finish()
    
    def _finish(self):
        """Finish the onboarding."""
        self._save_completed()
        self.finished.emit()
        self.accept()
    
    def _save_completed(self):
        """Save that onboarding was completed."""
        prefs_path = Path.home() / ".adaptivecad" / "onboarding.json"
        prefs_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            prefs_path.write_text(json.dumps({"completed": True}), encoding="utf-8")
        except Exception as e:
            log.debug(f"Failed to save onboarding status: {e}")
    
    @staticmethod
    def should_show() -> bool:
        """Check if onboarding should be shown."""
        prefs_path = Path.home() / ".adaptivecad" / "onboarding.json"
        
        try:
            if prefs_path.exists():
                prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
                return not prefs.get("completed", False)
        except Exception:
            pass
        
        return True


class SampleProjectDialog(QDialog):
    """Dialog for selecting a sample project."""
    
    projectSelected = Signal(dict)  # project data
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Sample Projects")
        self.resize(600, 450)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("<h2>Sample Projects</h2><p>Get started with a sample project:</p>")
        header.setWordWrap(True)
        layout.addWidget(header)
        
        # Project grid
        grid = QGridLayout()
        grid.setSpacing(12)
        
        for i, project in enumerate(SAMPLE_PROJECTS):
            card = self._create_project_card(project)
            row, col = divmod(i, 2)
            grid.addWidget(card, row, col)
        
        layout.addLayout(grid)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_project_card(self, project: dict) -> QWidget:
        """Create a card widget for a project."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1a1f26;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
            QFrame:hover {
                border-color: #58a6ff;
                background-color: #21262d;
            }
        """)
        card.setCursor(_PointingHandCursor)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # Title
        title = QLabel(f"<b>{project['name']}</b>")
        title.setStyleSheet("color: #e6edf3; font-size: 14px;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel(project['description'])
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(desc)
        
        # Shape count
        count = len(project.get('shapes', []))
        info = QLabel(f"📦 {count} shapes")
        info.setStyleSheet("color: #6e7681; font-size: 11px;")
        layout.addWidget(info)
        
        # Make clickable
        card.mousePressEvent = lambda e, p=project: self._on_project_clicked(p)
        
        return card
    
    def _on_project_clicked(self, project: dict):
        """Handle project card click."""
        self.projectSelected.emit(project)
        self.accept()


class FeatureSpotlight:
    """Manages feature spotlights and tooltips."""
    
    def __init__(self, parent: QWidget):
        self.parent = parent
        self.overlay: Optional[HighlightOverlay] = None
        self.tooltip: Optional[TooltipBubble] = None
        self._shown_features: set = set()
        
        self._load_shown_features()
    
    def _load_shown_features(self):
        """Load which features have been shown."""
        prefs_path = Path.home() / ".adaptivecad" / "shown_features.json"
        
        try:
            if prefs_path.exists():
                data = json.loads(prefs_path.read_text(encoding="utf-8"))
                self._shown_features = set(data.get("shown", []))
        except Exception:
            pass
    
    def _save_shown_features(self):
        """Save which features have been shown."""
        prefs_path = Path.home() / ".adaptivecad" / "shown_features.json"
        prefs_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            prefs_path.write_text(
                json.dumps({"shown": list(self._shown_features)}),
                encoding="utf-8"
            )
        except Exception:
            pass
    
    def show_feature(
        self,
        feature_id: str,
        target_widget: QWidget,
        title: str,
        content: str,
        force: bool = False
    ):
        """Show a feature spotlight."""
        if not force and feature_id in self._shown_features:
            return
        
        # Create overlay
        self.overlay = HighlightOverlay(self.parent)
        self.overlay.resize(self.parent.size())
        
        # Calculate target rect in parent coordinates
        target_rect = QRect(
            target_widget.mapTo(self.parent, QPoint(0, 0)),
            target_widget.size()
        )
        self.overlay.setTargetRect(target_rect)
        
        # Create tooltip
        self.tooltip = TooltipBubble(title, content, show_nav=False)
        
        # Position tooltip
        tooltip_pos = self._calculate_tooltip_position(target_rect)
        self.tooltip.move(self.parent.mapToGlobal(tooltip_pos))
        
        # Connect close signal
        self.tooltip.closed.connect(lambda: self._close_spotlight(feature_id))
        
        # Show
        self.overlay.show_animated()
        self.tooltip.show()
    
    def _calculate_tooltip_position(self, target_rect: QRect) -> QPoint:
        """Calculate the best position for the tooltip."""
        # Default: below target
        x = target_rect.center().x() - 150  # Assume tooltip width ~300
        y = target_rect.bottom() + 16
        
        # Ensure within parent bounds
        x = max(16, min(x, self.parent.width() - 316))
        
        return QPoint(x, y)
    
    def _close_spotlight(self, feature_id: str):
        """Close the current spotlight."""
        self._shown_features.add(feature_id)
        self._save_shown_features()
        
        if self.overlay:
            self.overlay.hide_animated()
        
        if self.tooltip:
            self.tooltip.close()
            self.tooltip = None
    
    def reset_shown_features(self):
        """Reset all shown features."""
        self._shown_features.clear()
        self._save_shown_features()


def show_onboarding(parent: Optional[QWidget] = None) -> bool:
    """Show the onboarding wizard if needed."""
    if OnboardingWizard.should_show():
        wizard = OnboardingWizard(parent)
        wizard.exec()
        return True
    return False


def show_sample_projects(parent: Optional[QWidget] = None) -> Optional[dict]:
    """Show the sample projects dialog and return selected project."""
    dialog = SampleProjectDialog(parent)
    
    selected_project = None
    
    def on_selected(project):
        nonlocal selected_project
        selected_project = project
    
    dialog.projectSelected.connect(on_selected)
    
    if dialog.exec() == _Accepted:
        return selected_project
    
    return None
