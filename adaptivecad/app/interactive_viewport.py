"""AdaptiveCAD Interactive Viewport

Enhanced viewport with:
- Transform gizmos (move/rotate/scale handles)
- Selection highlighting with outlines
- Multi-selection support
- Keyboard shortcuts for tool modes
"""

from __future__ import annotations

import logging
from typing import List, Optional

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from adaptivecad.app.gizmos import (
    GizmoAxis,
    GizmoColors,
    GizmoController,
    GizmoMode,
    SelectionManager,
)

log = logging.getLogger(__name__)

# Qt6 enum compatibility
try:
    _LeftButton = Qt.MouseButton.LeftButton
    _MiddleButton = Qt.MouseButton.MiddleButton
    _RightButton = Qt.MouseButton.RightButton
    _NoModifier = Qt.KeyboardModifier.NoModifier
    _ShiftModifier = Qt.KeyboardModifier.ShiftModifier
    _ControlModifier = Qt.KeyboardModifier.ControlModifier
except AttributeError:
    _LeftButton = Qt.LeftButton
    _MiddleButton = Qt.MiddleButton
    _RightButton = Qt.RightButton
    _NoModifier = Qt.NoModifier
    _ShiftModifier = Qt.ShiftModifier
    _ControlModifier = Qt.ControlModifier


class InteractiveViewport(QWidget):
    """
    Enhanced viewport wrapper that adds gizmo interaction layer.
    
    Wraps the AnalyticViewport and adds:
    - Transform gizmo rendering
    - Interactive gizmo manipulation
    - Selection highlighting
    - Tool mode switching
    """
    
    # Signals
    selectionChanged = Signal(list)  # List of selected indices
    transformStarted = Signal()
    transformChanged = Signal(dict)  # Transform data
    transformEnded = Signal()
    toolModeChanged = Signal(str)  # Mode name
    
    def __init__(self, parent: Optional[QWidget] = None, scene=None):
        super().__init__(parent)
        
        self._scene = scene
        self._viewport = None
        
        # Gizmo system
        self.selection = SelectionManager(scene)
        self.gizmo = GizmoController(self.selection, scene)
        
        # Connect signals
        self.selection.selectionChanged.connect(self._on_selection_changed)
        self.gizmo.transformStarted.connect(self.transformStarted)
        self.gizmo.transformUpdated.connect(self.transformChanged)
        self.gizmo.transformEnded.connect(self.transformEnded)
        
        # Interaction state
        self._tool_mode = GizmoMode.NONE  # Default to select/camera mode
        self._is_gizmo_drag = False
        self._last_mouse_pos: Optional[QPointF] = None
        
        # Animation
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._on_animate)
        self._anim_timer.start(16)  # ~60fps
        self._time = 0.0
        
        # Setup UI
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the viewport widget."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create the analytic viewport
        try:
            from adaptivecad.gui.analytic_viewport import AnalyticViewport
            self._viewport = AnalyticViewport(self, aacore_scene=self._scene)
            layout.addWidget(self._viewport)
            
            # Override viewport mouse events
            self._viewport.mousePressEvent = self._viewport_mouse_press
            self._viewport.mouseMoveEvent = self._viewport_mouse_move
            self._viewport.mouseReleaseEvent = self._viewport_mouse_release
            self._viewport.keyPressEvent = self._viewport_key_press
            
        except Exception as e:
            log.error(f"Failed to create viewport: {e}")
            from PySide6.QtWidgets import QLabel
            placeholder = QLabel("Viewport failed to load")
            placeholder.setStyleSheet("color: #ff6b6b; font-size: 18px;")
            layout.addWidget(placeholder)
    
    @property
    def viewport(self):
        """Get the underlying AnalyticViewport."""
        return self._viewport
    
    @property
    def scene(self):
        """Get the scene."""
        return self._scene
    
    @scene.setter
    def scene(self, value):
        """Set the scene."""
        self._scene = value
        self.selection.set_scene(value)
        self.gizmo.set_scene(value)
        if self._viewport:
            self._viewport.scene = value
    
    def set_tool_mode(self, mode: GizmoMode):
        """Set the current tool mode."""
        self._tool_mode = mode
        self.gizmo.set_mode(mode)
        self.toolModeChanged.emit(mode.value)
        self.update()
    
    def get_tool_mode(self) -> GizmoMode:
        """Get the current tool mode."""
        return self._tool_mode
    
    def select_object(self, index: int, add: bool = False, toggle: bool = False):
        """Select an object by index."""
        if toggle:
            self.selection.toggle_selection(index)
        elif add:
            self.selection.select(index, add_to_selection=True)
        else:
            self.selection.select(index)
    
    def clear_selection(self):
        """Clear the current selection."""
        self.selection.clear_selection()
    
    def _on_selection_changed(self, indices: List[int]):
        """Handle selection changes."""
        # Update viewport highlight
        if self._viewport and indices:
            self._viewport.selected_index = indices[0]
        elif self._viewport:
            self._viewport.selected_index = -1
        
        self.selectionChanged.emit(indices)
        self.update()
    
    def _on_animate(self):
        """Animation timer callback."""
        self._time += 0.016  # ~60fps
    
    def _viewport_mouse_press(self, event: QMouseEvent):
        """Handle mouse press in viewport."""
        self._last_mouse_pos = event.position()
        
        # Check for gizmo hit first (if in transform mode)
        if self._tool_mode != GizmoMode.NONE and self.selection.has_selection:
            # TODO: Implement proper 3D gizmo hit testing
            # For now, start gizmo drag if clicking near selected object
            pass
        
        # Regular selection on left click without modifiers
        if event.button() == _LeftButton:
            mods = event.modifiers()
            
            # Let viewport do picking
            if self._viewport and hasattr(self._viewport, '_perform_pick'):
                try:
                    pos = event.position()
                    self._viewport._perform_pick(int(pos.x()), int(pos.y()))
                    picked_idx = self._viewport.selected_index
                    
                    # Handle selection based on modifiers
                    if mods & _ShiftModifier:
                        self.select_object(picked_idx, add=True)
                    elif mods & _ControlModifier:
                        self.select_object(picked_idx, toggle=True)
                    else:
                        self.select_object(picked_idx)
                    
                    # Start gizmo interaction if in transform mode
                    if self._tool_mode != GizmoMode.NONE and picked_idx >= 0:
                        self._start_gizmo_drag(event.position())
                        
                except Exception as e:
                    log.debug(f"Pick failed: {e}")
        
        # Forward to viewport for camera control
        if self._viewport and hasattr(self._viewport, '__class__'):
            # Call parent class method for camera control
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            QOpenGLWidget.mousePressEvent(self._viewport, event)
    
    def _viewport_mouse_move(self, event: QMouseEvent):
        """Handle mouse move in viewport."""
        current_pos = event.position()
        
        # Handle gizmo dragging
        if self._is_gizmo_drag and self._viewport:
            viewport_size = (self._viewport.width(), self._viewport.height())
            self.gizmo.update_drag(
                (int(current_pos.x()), int(current_pos.y())),
                viewport_size
            )
            self._viewport.update()
        
        # Update hover state
        elif self._viewport and hasattr(self._viewport, '_perform_pick'):
            # Could implement hover highlighting here
            pass
        
        self._last_mouse_pos = current_pos
        
        # Forward for camera control
        if self._viewport and hasattr(self._viewport, '__class__'):
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            QOpenGLWidget.mouseMoveEvent(self._viewport, event)
    
    def _viewport_mouse_release(self, event: QMouseEvent):
        """Handle mouse release in viewport."""
        if self._is_gizmo_drag:
            self._end_gizmo_drag()
        
        # Forward to viewport
        if self._viewport and hasattr(self._viewport, '__class__'):
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            QOpenGLWidget.mouseReleaseEvent(self._viewport, event)
    
    def _viewport_key_press(self, event: QKeyEvent):
        """Handle key press in viewport."""
        key = event.key()
        
        # Tool mode shortcuts
        if key == Qt.Key.Key_Q:
            self.set_tool_mode(GizmoMode.NONE)
        elif key == Qt.Key.Key_G:
            self.set_tool_mode(GizmoMode.MOVE)
        elif key == Qt.Key.Key_R:
            self.set_tool_mode(GizmoMode.ROTATE)
        elif key == Qt.Key.Key_S:
            self.set_tool_mode(GizmoMode.SCALE)
        elif key == Qt.Key.Key_Escape:
            if self._is_gizmo_drag:
                self._cancel_gizmo_drag()
            else:
                self.clear_selection()
        elif key == Qt.Key.Key_Delete:
            # Delete selected objects
            pass
        
        # Forward to viewport
        if self._viewport:
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            QOpenGLWidget.keyPressEvent(self._viewport, event)
    
    def _start_gizmo_drag(self, pos: QPointF):
        """Start a gizmo drag operation."""
        if not self.selection.has_selection:
            return
        
        self._is_gizmo_drag = True
        
        # Determine which axis based on screen position relative to gizmo
        # For now, default to free movement
        axis = GizmoAxis.ALL if self._tool_mode == GizmoMode.SCALE else GizmoAxis.VIEW
        
        if self._viewport:
            viewport_size = (self._viewport.width(), self._viewport.height())
            self.gizmo.begin_drag(axis, (int(pos.x()), int(pos.y())), viewport_size)
    
    def _end_gizmo_drag(self):
        """End the gizmo drag operation."""
        self._is_gizmo_drag = False
        self.gizmo.end_drag()
    
    def _cancel_gizmo_drag(self):
        """Cancel the gizmo drag and revert changes."""
        self._is_gizmo_drag = False
        # TODO: Implement revert
        self.gizmo.end_drag()
    
    def fit_all(self):
        """Fit all objects in view."""
        if self._viewport and hasattr(self._viewport, 'fit_all'):
            self._viewport.fit_all()


class GizmoOverlayWidget(QWidget):
    """
    Overlay widget that draws 2D gizmo handles on top of the viewport.
    
    This is a lightweight 2D representation of the transform gizmo
    that sits on top of the OpenGL viewport.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self._mode = GizmoMode.NONE
        self._position = (0, 0)  # Screen position
        self._hovered_axis = GizmoAxis.NONE
        self._active_axis = GizmoAxis.NONE
        self._visible = False
        
        # Colors
        self._colors = GizmoColors()
        self._axis_length = 80  # pixels
        self._handle_size = 12  # pixels
    
    def set_mode(self, mode: GizmoMode):
        """Set the gizmo mode."""
        self._mode = mode
        self.update()
    
    def set_position(self, x: int, y: int):
        """Set the gizmo screen position."""
        self._position = (x, y)
        self.update()
    
    def set_visible(self, visible: bool):
        """Set gizmo visibility."""
        self._visible = visible
        self.update()
    
    def set_hovered_axis(self, axis: GizmoAxis):
        """Set the hovered axis for highlighting."""
        self._hovered_axis = axis
        self.update()
    
    def set_active_axis(self, axis: GizmoAxis):
        """Set the active (being dragged) axis."""
        self._active_axis = axis
        self.update()
    
    def paintEvent(self, event):
        """Paint the gizmo overlay."""
        if not self._visible or self._mode == GizmoMode.NONE:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        cx, cy = self._position
        
        if self._mode == GizmoMode.MOVE:
            self._draw_move_gizmo(painter, cx, cy)
        elif self._mode == GizmoMode.ROTATE:
            self._draw_rotate_gizmo(painter, cx, cy)
        elif self._mode == GizmoMode.SCALE:
            self._draw_scale_gizmo(painter, cx, cy)
        
        painter.end()
    
    def _get_axis_color(self, axis: GizmoAxis) -> QColor:
        """Get the color for an axis."""
        is_active = axis == self._active_axis
        is_hovered = axis == self._hovered_axis
        
        if is_active or is_hovered:
            return QColor(255, 255, 76)  # Yellow highlight
        
        if axis == GizmoAxis.X:
            return QColor(230, 51, 51)  # Red
        elif axis == GizmoAxis.Y:
            return QColor(51, 230, 51)  # Green
        elif axis == GizmoAxis.Z:
            return QColor(51, 51, 230)  # Blue
        else:
            return QColor(200, 200, 200)  # White
    
    def _draw_move_gizmo(self, painter: QPainter, cx: int, cy: int):
        """Draw the move gizmo (arrows)."""
        length = self._axis_length
        arrow_size = 10
        
        # X axis (right, red)
        self._draw_arrow(painter, cx, cy, cx + length, cy, 
                        self._get_axis_color(GizmoAxis.X), arrow_size)
        
        # Y axis (up, green) - inverted for screen coords
        self._draw_arrow(painter, cx, cy, cx, cy - length,
                        self._get_axis_color(GizmoAxis.Y), arrow_size)
        
        # Z axis (diagonal, blue)
        zx = cx + int(length * 0.5)
        zy = cy + int(length * 0.5)
        self._draw_arrow(painter, cx, cy, zx, zy,
                        self._get_axis_color(GizmoAxis.Z), arrow_size)
        
        # Center circle
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(QColor(80, 80, 80)))
        painter.drawEllipse(cx - 6, cy - 6, 12, 12)
    
    def _draw_arrow(self, painter: QPainter, x1: int, y1: int, 
                    x2: int, y2: int, color: QColor, arrow_size: int):
        """Draw an arrow from (x1, y1) to (x2, y2)."""
        painter.setPen(QPen(color, 3))
        painter.drawLine(x1, y1, x2, y2)
        
        # Arrow head
        import math
        angle = math.atan2(y2 - y1, x2 - x1)
        
        # Left wing
        lx = x2 - arrow_size * math.cos(angle - math.pi/6)
        ly = y2 - arrow_size * math.sin(angle - math.pi/6)
        
        # Right wing
        rx = x2 - arrow_size * math.cos(angle + math.pi/6)
        ry = y2 - arrow_size * math.sin(angle + math.pi/6)
        
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        
        arrow = QPolygonF([
            QPointF(x2, y2),
            QPointF(lx, ly),
            QPointF(rx, ry)
        ])
        
        painter.setBrush(QBrush(color))
        painter.drawPolygon(arrow)
    
    def _draw_rotate_gizmo(self, painter: QPainter, cx: int, cy: int):
        """Draw the rotate gizmo (rings)."""
        radius = self._axis_length
        
        # X rotation ring (red, vertical)
        painter.setPen(QPen(self._get_axis_color(GizmoAxis.X), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(cx - radius//2, cy - radius, radius, radius * 2)
        
        # Y rotation ring (green, horizontal)
        painter.setPen(QPen(self._get_axis_color(GizmoAxis.Y), 3))
        painter.drawEllipse(cx - radius, cy - radius//2, radius * 2, radius)
        
        # Z rotation ring (blue, facing camera)
        painter.setPen(QPen(self._get_axis_color(GizmoAxis.Z), 3))
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
    
    def _draw_scale_gizmo(self, painter: QPainter, cx: int, cy: int):
        """Draw the scale gizmo (lines with cubes)."""
        length = self._axis_length
        cube_size = self._handle_size
        
        # X axis
        color = self._get_axis_color(GizmoAxis.X)
        painter.setPen(QPen(color, 3))
        painter.drawLine(cx, cy, cx + length, cy)
        painter.setBrush(QBrush(color))
        painter.drawRect(cx + length - cube_size//2, cy - cube_size//2, cube_size, cube_size)
        
        # Y axis
        color = self._get_axis_color(GizmoAxis.Y)
        painter.setPen(QPen(color, 3))
        painter.drawLine(cx, cy, cx, cy - length)
        painter.setBrush(QBrush(color))
        painter.drawRect(cx - cube_size//2, cy - length - cube_size//2, cube_size, cube_size)
        
        # Z axis
        color = self._get_axis_color(GizmoAxis.Z)
        painter.setPen(QPen(color, 3))
        zx = cx + int(length * 0.5)
        zy = cy + int(length * 0.5)
        painter.drawLine(cx, cy, zx, zy)
        painter.setBrush(QBrush(color))
        painter.drawRect(zx - cube_size//2, zy - cube_size//2, cube_size, cube_size)
        
        # Center cube (uniform scale)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(QColor(200, 200, 200)))
        painter.drawRect(cx - cube_size//2, cy - cube_size//2, cube_size, cube_size)
    
    def hit_test(self, x: int, y: int) -> GizmoAxis:
        """Test which axis handle is at the given screen position."""
        if not self._visible or self._mode == GizmoMode.NONE:
            return GizmoAxis.NONE
        
        cx, cy = self._position
        length = self._axis_length
        threshold = 15  # pixels
        
        # Check X axis
        if abs(y - cy) < threshold and cx < x < cx + length + threshold:
            return GizmoAxis.X
        
        # Check Y axis
        if abs(x - cx) < threshold and cy - length - threshold < y < cy:
            return GizmoAxis.Y
        
        # Check Z axis
        zx = cx + int(length * 0.5)
        zy = cy + int(length * 0.5)
        # Line distance check
        dx = zx - cx
        dy = zy - cy
        t = max(0, min(1, ((x - cx) * dx + (y - cy) * dy) / (dx * dx + dy * dy)))
        px = cx + t * dx
        py = cy + t * dy
        dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        if dist < threshold:
            return GizmoAxis.Z
        
        # Check center
        if (x - cx) ** 2 + (y - cy) ** 2 < threshold ** 2:
            return GizmoAxis.ALL
        
        return GizmoAxis.NONE
