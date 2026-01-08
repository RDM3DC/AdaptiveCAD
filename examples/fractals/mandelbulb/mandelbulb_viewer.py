"""Mandelbulb fragment-shader viewer.

This example wraps the Mandelbulb distance-estimator fragment shader in a
PySide6 / QOpenGLWidget viewer so it can be launched directly from the
AdaptiveCAD repository.  The shader itself lives in ``mandelbulb.frag`` and is
kept self-contained so it can also be copy-pasted into engines such as
Three.js, Godot, Unity, or Shadertoy.
"""
from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from OpenGL import GL
from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

SHADER_DIR = Path(__file__).resolve().parent


@dataclass
class CameraState:
    pos: np.ndarray
    target: np.ndarray
    up: np.ndarray
    fov_radians: float


class MandelbulbWidget(QOpenGLWidget):
    """OpenGL widget that renders the Mandelbulb using the DE shader."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 480)
        self._start_time = time.perf_counter()
        self._program = None
        self._vao = None
        self._vbo = None
        self._uniform_locations: dict[str, int] = {}
        self._camera = CameraState(
            pos=np.array([0.0, 0.0, 4.0], dtype=np.float32),
            target=np.array([0.0, 0.0, 0.0], dtype=np.float32),
            up=np.array([0.0, 1.0, 0.0], dtype=np.float32),
            fov_radians=math.radians(45.0),
        )
        self._uniform_values = {
            "uPower": 8.0,
            "uBailout": 8.0,
            "uMaxIter": 14,
            "uMaxSteps": 160,
            "uEps": 8e-4,
            "uMaxDist": 60.0,
            "uColorMode": 1,
            "uOrbitShellR": 1.0,
            "uNiScale": 0.08,
            "uLightDir": np.array([0.8, 0.6, 0.3], dtype=np.float32),
        }

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)

    # --- Qt OpenGL lifecycle -------------------------------------------------
    def initializeGL(self) -> None:  # noqa: N802 (Qt signature)
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)

        vertex_src = (SHADER_DIR / "fullscreen_quad.vert").read_text(encoding="utf-8")
        frag_src = (SHADER_DIR / "mandelbulb.frag").read_text(encoding="utf-8")

        vert_shader = self._compile_shader(vertex_src, GL.GL_VERTEX_SHADER)
        frag_shader = self._compile_shader(frag_src, GL.GL_FRAGMENT_SHADER)

        program = GL.glCreateProgram()
        GL.glAttachShader(program, vert_shader)
        GL.glAttachShader(program, frag_shader)
        GL.glLinkProgram(program)

        link_status = GL.glGetProgramiv(program, GL.GL_LINK_STATUS)
        if link_status != GL.GL_TRUE:
            info = GL.glGetProgramInfoLog(program).decode("utf-8", errors="ignore")
            raise RuntimeError(f"Failed to link shader program:\n{info}")

        GL.glDeleteShader(vert_shader)
        GL.glDeleteShader(frag_shader)

        self._program = program
        self._fetch_uniform_locations()
        self._init_quad_geometry()

    def resizeGL(self, width: int, height: int) -> None:  # noqa: N802 (Qt signature)
        GL.glViewport(0, 0, width, height)

    def paintGL(self) -> None:  # noqa: N802 (Qt signature)
        if self._program is None or self._vao is None:
            return

        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glUseProgram(self._program)

        elapsed = float(time.perf_counter() - self._start_time)
        GL.glUniform1f(self._uniform_locations["uTime"], elapsed)
        GL.glUniform2f(self._uniform_locations["uResolution"], float(self.width()), float(self.height()))

        cam = self._camera
        GL.glUniform3f(self._uniform_locations["uCamPos"], *(float(v) for v in cam.pos))
        GL.glUniform3f(self._uniform_locations["uCamTarget"], *(float(v) for v in cam.target))
        GL.glUniform3f(self._uniform_locations["uCamUp"], *(float(v) for v in cam.up))
        GL.glUniform1f(self._uniform_locations["uFov"], float(cam.fov_radians))

        # Scalar uniforms
        GL.glUniform1f(self._uniform_locations["uPower"], float(self._uniform_values["uPower"]))
        GL.glUniform1f(self._uniform_locations["uBailout"], float(self._uniform_values["uBailout"]))
        GL.glUniform1i(self._uniform_locations["uMaxIter"], int(self._uniform_values["uMaxIter"]))
        GL.glUniform1i(self._uniform_locations["uMaxSteps"], int(self._uniform_values["uMaxSteps"]))
        GL.glUniform1f(self._uniform_locations["uEps"], float(self._uniform_values["uEps"]))
        GL.glUniform1f(self._uniform_locations["uMaxDist"], float(self._uniform_values["uMaxDist"]))
        GL.glUniform1i(self._uniform_locations["uColorMode"], int(self._uniform_values["uColorMode"]))
        GL.glUniform1f(self._uniform_locations["uOrbitShellR"], float(self._uniform_values["uOrbitShellR"]))
        GL.glUniform1f(self._uniform_locations["uNiScale"], float(self._uniform_values["uNiScale"]))

        light_dir = self._uniform_values["uLightDir"]
        norm_light = light_dir / np.linalg.norm(light_dir)
        GL.glUniform3f(self._uniform_locations["uLightDir"], *(float(v) for v in norm_light))

        GL.glBindVertexArray(self._vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
        GL.glBindVertexArray(0)
        GL.glUseProgram(0)

    # --- Uniform updates from UI --------------------------------------------
    def set_color_mode(self, index: int) -> None:
        self._uniform_values["uColorMode"] = int(index)
        self.update()

    def set_power(self, value: float) -> None:
        self._uniform_values["uPower"] = float(value)
        self.update()

    def set_orbit_radius(self, value: float) -> None:
        self._uniform_values["uOrbitShellR"] = float(value)
        self.update()

    def set_ni_scale(self, value: float) -> None:
        self._uniform_values["uNiScale"] = float(value)
        self.update()

    # --- Internal helpers ----------------------------------------------------
    def _compile_shader(self, source: str, shader_type: int) -> int:
        shader = GL.glCreateShader(shader_type)
        GL.glShaderSource(shader, source)
        GL.glCompileShader(shader)
        status = GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS)
        if status != GL.GL_TRUE:
            info = GL.glGetShaderInfoLog(shader).decode("utf-8", errors="ignore")
            shader_name = "vertex" if shader_type == GL.GL_VERTEX_SHADER else "fragment"
            raise RuntimeError(f"Failed to compile {shader_name} shader:\n{info}")
        return shader

    def _fetch_uniform_locations(self) -> None:
        assert self._program is not None
        names = [
            "uResolution",
            "uTime",
            "uCamPos",
            "uCamTarget",
            "uCamUp",
            "uFov",
            "uPower",
            "uBailout",
            "uMaxIter",
            "uMaxSteps",
            "uEps",
            "uMaxDist",
            "uColorMode",
            "uOrbitShellR",
            "uNiScale",
            "uLightDir",
        ]
        for name in names:
            loc = GL.glGetUniformLocation(self._program, name)
            if loc == -1:
                raise RuntimeError(f"Uniform {name} not found in shader")
            self._uniform_locations[name] = loc

    def _init_quad_geometry(self) -> None:
        quad = np.array(
            [
                -1.0, -1.0,
                 1.0, -1.0,
                -1.0,  1.0,
                -1.0,  1.0,
                 1.0, -1.0,
                 1.0,  1.0,
            ],
            dtype=np.float32,
        )
        vao = GL.glGenVertexArrays(1)
        vbo = GL.glGenBuffers(1)
        GL.glBindVertexArray(vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, quad.nbytes, quad, GL.GL_STATIC_DRAW)
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, False, 0, None)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glBindVertexArray(0)
        self._vao = vao
        self._vbo = vbo

    def close(self) -> None:
        self._timer.stop()
        super().close()


class MandelbulbWindow(QMainWindow):
    """Main window with a couple of controls for the Mandelbulb viewer."""

    COLOR_MODES = [
        "Smooth NI",
        "Orbit Trap",
        "Angular",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AdaptiveCAD – Mandelbulb Viewer")

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(12)

        mode_label = QLabel("Color mode:")
        mode_combo = QComboBox()
        for label in self.COLOR_MODES:
            mode_combo.addItem(label)
        mode_combo.setCurrentIndex(1)
        mode_label.setBuddy(mode_combo)

        power_label = QLabel("Power:")
        power_spin = QDoubleSpinBox()
        power_spin.setRange(2.0, 16.0)
        power_spin.setSingleStep(0.5)
        power_spin.setValue(8.0)
        power_spin.setDecimals(2)
        power_label.setBuddy(power_spin)

        shell_label = QLabel("Orbit shell R:")
        shell_spin = QDoubleSpinBox()
        shell_spin.setRange(0.1, 4.0)
        shell_spin.setSingleStep(0.1)
        shell_spin.setValue(1.0)
        shell_spin.setDecimals(2)
        shell_label.setBuddy(shell_spin)

        ni_label = QLabel("NI scale:")
        ni_spin = QDoubleSpinBox()
        ni_spin.setRange(0.01, 0.3)
        ni_spin.setSingleStep(0.01)
        ni_spin.setDecimals(3)
        ni_spin.setValue(0.08)
        ni_label.setBuddy(ni_spin)

        controls_layout.addWidget(mode_label)
        controls_layout.addWidget(mode_combo)
        controls_layout.addSpacing(12)
        controls_layout.addWidget(power_label)
        controls_layout.addWidget(power_spin)
        controls_layout.addSpacing(12)
        controls_layout.addWidget(shell_label)
        controls_layout.addWidget(shell_spin)
        controls_layout.addSpacing(12)
        controls_layout.addWidget(ni_label)
        controls_layout.addWidget(ni_spin)
        controls_layout.addStretch(1)

        self._gl_widget = MandelbulbWidget()
        self._gl_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addLayout(controls_layout)
        layout.addWidget(self._gl_widget, 1)
        central.setLayout(layout)
        self.setCentralWidget(central)

        mode_combo.currentIndexChanged.connect(self._gl_widget.set_color_mode)
        power_spin.valueChanged.connect(self._gl_widget.set_power)
        shell_spin.valueChanged.connect(self._gl_widget.set_orbit_radius)
        ni_spin.valueChanged.connect(self._gl_widget.set_ni_scale)

        self.resize(1100, 750)


def configure_default_format() -> None:
    surface_format = QSurfaceFormat()
    surface_format.setVersion(3, 3)
    surface_format.setProfile(QSurfaceFormat.CoreProfile)
    surface_format.setDepthBufferSize(0)
    surface_format.setStencilBufferSize(0)
    QSurfaceFormat.setDefaultFormat(surface_format)


def main() -> int:
    configure_default_format()
    app = QApplication(sys.argv)
    window = MandelbulbWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
