from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from adaptivecad.aacore.math import Xform, clamp
from adaptivecad.aacore.sdf import (
    KIND_CAPSULE,
    KIND_PI_BLOOM,
    KIND_SPHERE,
    KIND_TORUS,
    Prim,
    Scene,
)

try:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

    from adaptivecad.app.interactive_viewport import InteractiveViewport

    HAS_QT = True
except Exception:
    QApplication = None
    InteractiveViewport = None
    QLabel = None
    QMainWindow = object
    QTimer = None
    QVBoxLayout = None
    QWidget = object
    HAS_QT = False


try:
    _Key_W = Qt.Key.Key_W
    _Key_A = Qt.Key.Key_A
    _Key_S = Qt.Key.Key_S
    _Key_D = Qt.Key.Key_D
    _Key_Shift = Qt.Key.Key_Shift
    _Key_Space = Qt.Key.Key_Space
    _StrongFocus = Qt.FocusPolicy.StrongFocus
    _NoFocus = Qt.FocusPolicy.NoFocus
except Exception:
    _Key_W = None
    _Key_A = None
    _Key_S = None
    _Key_D = None
    _Key_Shift = None
    _Key_Space = None
    _StrongFocus = None
    _NoFocus = None


PHASE_PULSE_RADIUS = 3.4


def _vec3(values: Iterable[float]) -> np.ndarray:
    return np.asarray(list(values), dtype=np.float64)


def _set_prim_position(prim: Prim, position: np.ndarray) -> None:
    prim.xform.M[:3, 3] = np.asarray(position[:3], dtype=np.float32)
    try:
        prim.xform.M_inv = np.linalg.inv(prim.xform.M)
    except Exception:
        prim.xform.M_inv = None


@dataclass
class GameInputState:
    forward: bool = False
    backward: bool = False
    left: bool = False
    right: bool = False
    brake: bool = False
    pulse: bool = False

    def movement_vector(self) -> np.ndarray:
        move = np.array(
            [float(self.right) - float(self.left), 0.0, float(self.backward) - float(self.forward)],
            dtype=np.float64,
        )
        norm = float(np.linalg.norm(move))
        if norm > 1e-8:
            move /= norm
        return move


@dataclass
class GameActor:
    entity_id: int
    name: str
    role: str
    prim: Prim
    radius: float
    base_params: np.ndarray
    base_beta: float
    base_color: np.ndarray
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    phase_bias: float = 0.0
    pulse_response: float = 1.0
    collectible_value: int = 0
    damage: int = 0
    orbit_center: np.ndarray | None = None
    orbit_radius: float = 0.0
    orbit_speed: float = 0.0
    orbit_phase: float = 0.0
    bob_amp: float = 0.0
    bob_speed: float = 0.0
    active: bool = True

    @property
    def position(self) -> np.ndarray:
        return np.asarray(self.prim.xform.M[:3, 3], dtype=np.float64)

    def set_position(self, position: np.ndarray) -> None:
        _set_prim_position(self.prim, position)


@dataclass
class GameSnapshot:
    status: str
    score: int
    lives: int
    phase_energy: float
    remaining_collectibles: int
    event: str


class AdaptiveGameEngine:
    """Realtime gameplay layer that treats AdaptiveCAD primitives as actors."""

    def __init__(self, scene: Scene | None = None, *, arena_radius: float = 7.5):
        self.scene = scene if scene is not None else Scene()
        self.scene.bg_color = np.array([0.045, 0.055, 0.08], dtype=np.float32)
        self.scene.env_light = np.array([0.55, 0.95, 0.65], dtype=np.float32)
        self.arena_radius = float(arena_radius)
        self.fixed_dt = 1.0 / 60.0
        self.input_state = GameInputState()
        self.time_seconds = 0.0
        self.score = 0
        self.lives = 3
        self.phase_energy = 1.0
        self.phase_cooldown = 0.0
        self.damage_cooldown = 0.0
        self.status = "running"
        self.last_event = "Collect the bloom cores. Press Space to pulse the field."
        self._actors: dict[int, GameActor] = {}
        self._player_id: int | None = None
        self._next_entity_id = 1
        self._collectible_target = 0
        self._pulse_latched = False

    @property
    def actors(self) -> dict[int, GameActor]:
        return self._actors

    @property
    def player(self) -> GameActor | None:
        if self._player_id is None:
            return None
        return self._actors.get(self._player_id)

    @property
    def remaining_collectibles(self) -> int:
        return sum(1 for actor in self._actors.values() if actor.active and actor.collectible_value > 0)

    def snapshot(self) -> GameSnapshot:
        return GameSnapshot(
            status=self.status,
            score=self.score,
            lives=self.lives,
            phase_energy=self.phase_energy,
            remaining_collectibles=self.remaining_collectibles,
            event=self.last_event,
        )

    def spawn_actor(
        self,
        *,
        name: str,
        role: str,
        kind: int,
        params: Iterable[float],
        position: Iterable[float],
        radius: float,
        color: Iterable[float],
        beta: float = 0.0,
        pulse_response: float = 1.0,
        collectible_value: int = 0,
        damage: int = 0,
        orbit_center: Iterable[float] | None = None,
        orbit_radius: float = 0.0,
        orbit_speed: float = 0.0,
        orbit_phase: float = 0.0,
        bob_amp: float = 0.0,
        bob_speed: float = 0.0,
    ) -> GameActor:
        entity_id = self._next_entity_id
        self._next_entity_id += 1
        prim = Prim(kind, list(params), xform=Xform.identity(), beta=float(beta), pid=entity_id, color=tuple(color))
        actor = GameActor(
            entity_id=entity_id,
            name=name,
            role=role,
            prim=prim,
            radius=float(radius),
            base_params=np.asarray(list(params), dtype=np.float64).copy(),
            base_beta=float(beta),
            base_color=np.asarray(list(color), dtype=np.float64).copy(),
            pulse_response=float(pulse_response),
            collectible_value=int(collectible_value),
            damage=int(damage),
            orbit_center=None if orbit_center is None else _vec3(orbit_center),
            orbit_radius=float(orbit_radius),
            orbit_speed=float(orbit_speed),
            orbit_phase=float(orbit_phase),
            bob_amp=float(bob_amp),
            bob_speed=float(bob_speed),
        )
        actor.set_position(_vec3(position))
        self._actors[entity_id] = actor
        if actor.collectible_value > 0:
            self._collectible_target += 1
        self.scene.add(prim)
        return actor

    def spawn_player(self, position: Iterable[float] = (0.0, 0.0, 0.0)) -> GameActor:
        actor = self.spawn_actor(
            name="Pulse Core",
            role="player",
            kind=KIND_SPHERE,
            params=[0.42, 0.0, 0.0, 0.0],
            position=position,
            radius=0.42,
            color=(0.98, 0.52, 0.34),
            beta=0.08,
            pulse_response=0.0,
        )
        self._player_id = actor.entity_id
        return actor

    def spawn_collectible(
        self,
        position: Iterable[float],
        *,
        orbit_center: Iterable[float] | None = None,
        orbit_radius: float = 0.0,
        orbit_speed: float = 0.0,
        orbit_phase: float = 0.0,
        bob_amp: float = 0.0,
        bob_speed: float = 0.0,
        value: int = 10,
    ) -> GameActor:
        return self.spawn_actor(
            name="Bloom Core",
            role="collectible",
            kind=KIND_PI_BLOOM,
            params=[0.58, 0.26, 7.0, 0.24],
            position=position,
            radius=0.58,
            color=(0.92, 0.45, 0.62),
            beta=0.04,
            pulse_response=1.25,
            collectible_value=value,
            orbit_center=orbit_center,
            orbit_radius=orbit_radius,
            orbit_speed=orbit_speed,
            orbit_phase=orbit_phase,
            bob_amp=bob_amp,
            bob_speed=bob_speed,
        )

    def spawn_hazard(self, position: Iterable[float], *, lateral: bool = False) -> GameActor:
        kind = KIND_CAPSULE if lateral else KIND_TORUS
        params = [0.34, 1.4, 0.0, 0.0] if lateral else [1.05, 0.22, 0.0, 0.0]
        actor = self.spawn_actor(
            name="Null Gate",
            role="hazard",
            kind=kind,
            params=params,
            position=position,
            radius=0.74,
            color=(0.28, 0.84, 0.88),
            beta=0.02,
            pulse_response=0.8,
            damage=1,
        )
        if lateral:
            actor.prim.euler[2] = 90.0
        return actor

    def step(self, dt: float) -> GameSnapshot:
        if dt <= 0.0:
            return self.snapshot()
        if self.status != "running":
            return self.snapshot()

        self.time_seconds += dt
        self.phase_energy = clamp(self.phase_energy + dt * 0.18, 0.0, 1.0)
        self.phase_cooldown = max(0.0, self.phase_cooldown - dt)
        self.damage_cooldown = max(0.0, self.damage_cooldown - dt)

        self._update_non_player_actors()
        self._update_player(dt)
        self._decay_phase_fields(dt)
        self._resolve_collisions()
        self._refresh_player_visuals()

        if self._collectible_target > 0 and self.remaining_collectibles == 0:
            self.status = "won"
            self.last_event = "Arena stabilized. Every bloom core is in sync."
        elif self.lives <= 0:
            self.status = "lost"
            self.last_event = "The null gates collapsed your pulse core."

        return self.snapshot()

    def emit_phase_pulse(self, *, center: Iterable[float] | None = None, strength: float = 1.0) -> int:
        pulse_center = self.player.position if center is None and self.player is not None else _vec3(center or (0.0, 0.0, 0.0))
        touched = 0
        for actor in self._actors.values():
            if not actor.active or actor.role == "player":
                continue
            offset = actor.position - pulse_center
            distance = float(np.linalg.norm(offset))
            if distance >= PHASE_PULSE_RADIUS:
                continue
            influence = float(strength) * max(0.0, 1.0 - distance / PHASE_PULSE_RADIUS) * actor.pulse_response
            if influence <= 1e-6:
                continue
            actor.phase_bias = max(actor.phase_bias, influence)
            touched += 1
        if touched:
            self.last_event = f"Phase pulse resonated with {touched} actor(s)."
        return touched

    def _update_player(self, dt: float) -> None:
        player = self.player
        if player is None or not player.active:
            return

        move = self.input_state.movement_vector()
        accel = 8.5 if not self.input_state.brake else 4.0
        damping = 3.4 if not self.input_state.brake else 7.2

        player.velocity += move * accel * dt
        player.velocity *= max(0.0, 1.0 - damping * dt)

        next_pos = player.position + player.velocity * dt
        radial = np.array([next_pos[0], 0.0, next_pos[2]], dtype=np.float64)
        radial_norm = float(np.linalg.norm(radial))
        max_radius = self.arena_radius - player.radius
        if radial_norm > max_radius:
            radial = radial / max(radial_norm, 1e-6) * max_radius
            next_pos[0] = radial[0]
            next_pos[2] = radial[2]
            player.velocity[0] *= -0.35
            player.velocity[2] *= -0.35
            self.last_event = "Arena edge reflected the pulse core."

        next_pos[1] = 0.18 * math.sin(self.time_seconds * 2.4)
        player.set_position(next_pos)

        if self.input_state.pulse and not self._pulse_latched and self.phase_cooldown <= 0.0 and self.phase_energy >= 0.35:
            strength = 0.65 + self.phase_energy * 0.35
            touched = self.emit_phase_pulse(strength=strength)
            self.phase_energy = max(0.0, self.phase_energy - 0.45)
            self.phase_cooldown = 0.42
            if touched == 0:
                self.last_event = "Phase pulse dissipated into empty space."
        self._pulse_latched = self.input_state.pulse

    def _update_non_player_actors(self) -> None:
        for actor in self._actors.values():
            if not actor.active or actor.role == "player":
                continue
            if actor.orbit_center is not None and actor.orbit_radius > 0.0:
                theta = actor.orbit_phase + self.time_seconds * actor.orbit_speed
                pos = actor.orbit_center + np.array(
                    [
                        math.cos(theta) * actor.orbit_radius,
                        actor.bob_amp * math.sin(self.time_seconds * actor.bob_speed + actor.orbit_phase),
                        math.sin(theta) * actor.orbit_radius,
                    ],
                    dtype=np.float64,
                )
                actor.set_position(pos)

    def _decay_phase_fields(self, dt: float) -> None:
        for actor in self._actors.values():
            if not actor.active:
                continue
            actor.phase_bias = max(0.0, actor.phase_bias - dt * 1.7)
            actor.prim.beta = actor.base_beta + 0.18 * actor.phase_bias
            actor.prim.color = np.clip(
                actor.base_color + actor.phase_bias * np.array([0.06, 0.12, 0.08], dtype=np.float64),
                0.0,
                1.0,
            )
            if actor.prim.kind == KIND_PI_BLOOM:
                actor.prim.params[1] = actor.base_params[1] + 0.45 * actor.phase_bias
                actor.prim.params[3] = actor.base_params[3] + 0.25 * actor.phase_bias
            elif actor.prim.kind == KIND_TORUS:
                actor.prim.params[1] = actor.base_params[1] * (1.0 + 0.18 * actor.phase_bias)

    def _resolve_collisions(self) -> None:
        player = self.player
        if player is None or not player.active:
            return
        player_pos = player.position

        for actor in list(self._actors.values()):
            if not actor.active or actor.role == "player":
                continue
            distance = float(np.linalg.norm(actor.position - player_pos))
            if distance > actor.radius + player.radius:
                continue
            if actor.collectible_value > 0:
                self.score += actor.collectible_value
                self.phase_energy = clamp(self.phase_energy + 0.25, 0.0, 1.0)
                self.last_event = f"Collected {actor.name}. Score {self.score}."
                self._deactivate_actor(actor)
            elif actor.damage > 0 and self.damage_cooldown <= 0.0:
                push = player_pos - actor.position
                push_norm = float(np.linalg.norm(push))
                if push_norm > 1e-6:
                    player.velocity += (push / push_norm) * 4.5
                self.lives -= actor.damage
                self.damage_cooldown = 0.9
                self.phase_energy = clamp(self.phase_energy + 0.12, 0.0, 1.0)
                self.last_event = f"Hit by {actor.name}. Lives left: {self.lives}."

    def _refresh_player_visuals(self) -> None:
        player = self.player
        if player is None:
            return
        speed = float(np.linalg.norm(player.velocity))
        player.prim.params[0] = 0.42 + min(0.08, speed * 0.03)
        player.prim.beta = 0.08 + min(0.16, speed * 0.04) + 0.08 * self.phase_energy
        player.prim.color = np.clip(
            player.base_color + np.array([0.04, 0.08, 0.16], dtype=np.float64) * self.phase_energy,
            0.0,
            1.0,
        )

    def _deactivate_actor(self, actor: GameActor) -> None:
        actor.active = False
        try:
            idx = self.scene.prims.index(actor.prim)
        except ValueError:
            idx = -1
        if idx >= 0:
            self.scene.remove_index(idx)
        self._actors.pop(actor.entity_id, None)


def create_phase_bloom_demo_engine() -> AdaptiveGameEngine:
    engine = AdaptiveGameEngine(arena_radius=7.8)
    engine.spawn_player((0.0, 0.0, 0.0))

    ring_center = np.array([0.0, 0.35, 0.0], dtype=np.float64)
    for index, phase in enumerate(np.linspace(0.0, 2.0 * math.pi, 5, endpoint=False)):
        engine.spawn_collectible(
            (math.cos(phase) * 3.2, 0.0, math.sin(phase) * 3.2),
            orbit_center=ring_center,
            orbit_radius=3.2,
            orbit_speed=0.32 + index * 0.035,
            orbit_phase=float(phase),
            bob_amp=0.28,
            bob_speed=1.2 + index * 0.1,
            value=12,
        )

    engine.spawn_hazard((4.4, 0.0, 0.0), lateral=False)
    engine.spawn_hazard((-3.8, 0.0, 2.8), lateral=True)
    engine.spawn_hazard((0.0, 0.0, -4.8), lateral=False)

    return engine


if HAS_QT:
    class PhaseBloomArenaWidget(QWidget):
        def __init__(self, parent=None, *, engine: AdaptiveGameEngine | None = None):
            super().__init__(parent)
            self.engine = engine if engine is not None else create_phase_bloom_demo_engine()
            self._last_tick = time.perf_counter()
            self._accumulator = 0.0

            self.setFocusPolicy(_StrongFocus)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            self._hud = QLabel(self)
            self._hud.setStyleSheet(
                "background:#101726;color:#f6f2e8;padding:10px 14px;font:600 12pt 'Segoe UI';"
            )
            layout.addWidget(self._hud)

            self._viewport_host = InteractiveViewport(self, scene=self.engine.scene)
            self._viewport_host.setFocusPolicy(_NoFocus)
            if self._viewport_host.viewport is not None:
                self._viewport_host.viewport.setFocusPolicy(_NoFocus)
                self._viewport_host.viewport.distance = 11.5
                self._viewport_host.viewport.yaw = 0.55
                self._viewport_host.viewport.pitch = -0.38
                self._viewport_host.viewport.cam_target = np.array([0.0, 0.3, 0.0], dtype=np.float32)
            layout.addWidget(self._viewport_host, 1)

            self._hint = QLabel("WASD move   Shift brake   Space phase pulse", self)
            self._hint.setStyleSheet(
                "background:#0b1120;color:#93d7d0;padding:8px 14px;font:500 10pt 'Segoe UI';"
            )
            layout.addWidget(self._hint)

            self._timer = QTimer(self)
            self._timer.timeout.connect(self._on_tick)
            self._timer.start(16)
            self._update_hud()

        def _set_key_state(self, key: int, is_pressed: bool) -> None:
            if key == _Key_W:
                self.engine.input_state.forward = is_pressed
            elif key == _Key_S:
                self.engine.input_state.backward = is_pressed
            elif key == _Key_A:
                self.engine.input_state.left = is_pressed
            elif key == _Key_D:
                self.engine.input_state.right = is_pressed
            elif key == _Key_Shift:
                self.engine.input_state.brake = is_pressed
            elif key == _Key_Space:
                self.engine.input_state.pulse = is_pressed

        def _on_tick(self) -> None:
            now = time.perf_counter()
            frame_dt = min(0.05, now - self._last_tick)
            self._last_tick = now
            self._accumulator += frame_dt
            while self._accumulator >= self.engine.fixed_dt:
                self.engine.step(self.engine.fixed_dt)
                self._accumulator -= self.engine.fixed_dt
            self._update_hud()
            if self._viewport_host.viewport is not None:
                self._viewport_host.viewport.update()
            self._viewport_host.update()

        def _update_hud(self) -> None:
            snap = self.engine.snapshot()
            phase_pct = int(round(snap.phase_energy * 100.0))
            self._hud.setText(
                f"Status: {snap.status.upper()}   Score: {snap.score}   Lives: {snap.lives}   "
                f"Phase: {phase_pct}%   Blooms: {snap.remaining_collectibles}   {snap.event}"
            )

        def keyPressEvent(self, event):
            self._set_key_state(event.key(), True)
            event.accept()

        def keyReleaseEvent(self, event):
            self._set_key_state(event.key(), False)
            event.accept()


    class PhaseBloomArenaWindow(QMainWindow):
        def __init__(self, parent=None, *, engine: AdaptiveGameEngine | None = None):
            super().__init__(parent)
            self.setWindowTitle("AdaptiveCAD Phase Bloom Arena")
            self.resize(1360, 860)
            widget = PhaseBloomArenaWidget(self, engine=engine)
            self.setCentralWidget(widget)
            widget.setFocus()


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the AdaptiveCAD phase-bloom game demo.")
    parser.add_argument("--title", default="AdaptiveCAD Phase Bloom Arena")
    return parser


def main(argv: list[str] | None = None) -> int:
    if not HAS_QT:
        raise RuntimeError("PySide6 is required to launch the AdaptiveCAD game window.")

    parser = build_argument_parser()
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
    window = PhaseBloomArenaWindow()
    window.setWindowTitle(args.title)
    window.show()
    return app.exec()


__all__ = [
    "AdaptiveGameEngine",
    "GameActor",
    "GameInputState",
    "GameSnapshot",
    "HAS_QT",
    "PhaseBloomArenaWidget",
    "PhaseBloomArenaWindow",
    "create_phase_bloom_demo_engine",
    "main",
]