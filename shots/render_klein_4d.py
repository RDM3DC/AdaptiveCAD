#!/usr/bin/env python3
"""Render Klein bottle 4D rotation demo - impossible geometry visualization."""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

# Import project modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adaptivecad.aacore.sdf import KIND_KLEIN, Prim, Scene
from adaptivecad.gui.analytic_viewport import AnalyticViewport

try:
    from PIL import Image, ImageDraw, ImageFont

    _HAVE_PIL = True
except Exception:
    _HAVE_PIL = False


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2.0


def ease_in_out_quint(t: float) -> float:
    """Even smoother quintic easing for cinematic feel"""
    t = max(0.0, min(1.0, t))
    return 16 * t * t * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 5) / 2.0


def smooth_step(edge0: float, edge1: float, x: float) -> float:
    """Hermite interpolation for ultra-smooth transitions"""
    x = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return x * x * (3.0 - 2.0 * x)


def build_klein_scene() -> Scene:
    """Create a scene with Klein bottle showing 4D rotation."""
    scene = Scene()

    # Klein bottle with animated 4D rotation (75% smaller)
    klein = Prim(KIND_KLEIN, [0.3, 2.0, 0.0, 0.02], beta=0.0, color=(0.1, 0.6, 0.9))
    scene.add(klein)

    # Elegant lighting for impossible geometry
    scene.bg_color[:] = np.array([0.02, 0.03, 0.08], np.float32)
    scene.env_light[:] = np.array([1.3, 1.1, 1.4], np.float32)
    return scene


class KleinBottleRunner:
    def __init__(self, args):
        self.args = args
        self.nframes = int(args.fps * args.seconds)
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Create viewport
        self.host = QWidget()
        self.layout = QVBoxLayout(self.host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.view = AnalyticViewport(self.host, aacore_scene=build_klein_scene())
        self.view.resize(args.w, args.h)
        self.layout.addWidget(self.view)
        self.host.resize(args.w, args.h)
        self.host.show()

        # Camera setup for Klein bottle viewing
        self.view.distance = 6.0
        self.view.cam_target = np.array([0.0, 0.0, 0.0], np.float32)
        self.view.yaw = 0.0
        self.view.pitch = 0.1
        self.view._update_camera()

        self.scene = self.view.scene
        self.out_dir = Path(self.args.out)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.i = 0

        # Timer for frame stepping
        self.timer = QTimer()
        self.timer.setInterval(0)
        self.timer.timeout.connect(self.step)

    def start(self):
        # Wait for GL initialization
        self.readyTimer = QTimer()
        self.readyTimer.setInterval(16)

        def _check_ready():
            if self.view.isValid():
                self.readyTimer.stop()
                self.timer.start()

        self.readyTimer.timeout.connect(_check_ready)
        self.readyTimer.start()
        rc = self.app.exec()
        return rc

    def step(self):
        if self.i >= self.nframes:
            self.timer.stop()
            print(f"Done. Frames in {self.out_dir}")
            self.app.quit()
            return

        t = self.i / max(1, self.nframes - 1)  # 0..1

        # 4D rotation animation - the Klein bottle morphs through impossible shapes
        rotation_4d = 2 * math.pi * t * 1.5  # 1.5 full rotations in 4D

        # Camera orbits to show the impossible geometry from all angles
        self.view.yaw = 0.8 * math.sin(2 * math.pi * t * 0.7)
        self.view.pitch = 0.1 + 0.3 * math.cos(2 * math.pi * t * 0.5)

        # Gentle zoom in and out to show detail
        zoom_wave = 1.0 + 0.3 * math.sin(2 * math.pi * t * 1.2)
        self.view.distance = 6.0 / zoom_wave

        # Update Klein bottle 4D rotation parameter
        klein = self.scene.prims[0]
        klein.params[2] = rotation_4d  # t_offset parameter controls 4D rotation

        self.view._update_camera()

        # Render frame
        try:
            self.view.makeCurrent()
        except Exception:
            pass
        self.view._draw_frame(debug_override=0)

        # Capture frame
        qimg = self.view.grabFramebuffer()

        # Add text overlay
        if _HAVE_PIL:
            # Convert to PIL
            w, h = qimg.width(), qimg.height()
            ptr = qimg.bits()
            arr = np.frombuffer(ptr, dtype=np.uint8, count=w * h * 4).reshape(h, w, 4)

            img = Image.fromarray(arr, "RGBA")
            draw = ImageDraw.Draw(img)

            try:
                font_large = ImageFont.truetype("arial.ttf", 52)
                font_small = ImageFont.truetype("arial.ttf", 36)
            except BaseException:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Title with impossible geometry theme
            draw.text((50, 50), "Klein Bottle", fill=(150, 200, 255), font=font_large)
            draw.text((50, 110), "4D Rotation", fill=(100, 180, 255), font=font_large)

            # 4D rotation indicator
            rotation_degrees = (rotation_4d * 180 / math.pi) % 360
            draw.text(
                (50, self.args.h - 120),
                f"4D Rotation: {rotation_degrees:.0f}°",
                fill=(255, 200, 100),
                font=font_small,
            )

            # Impossible geometry note
            draw.text(
                (50, self.args.h - 80),
                "Self-intersecting 4D surface",
                fill=(200, 255, 200),
                font=font_small,
            )

            if t > 0.6:
                draw.text(
                    (50, self.args.h - 40),
                    "Impossible in 3D space",
                    fill=(255, 255, 255),
                    font=font_small,
                )

            # Save with text
            frame_path = self.out_dir / f"frame_{self.i:05d}.png"
            img.save(frame_path)
        else:
            # Save without text
            frame_path = self.out_dir / f"frame_{self.i:05d}.png"
            qimg.save(str(frame_path))

        if (self.i % 10) == 0:
            rotation_deg = (rotation_4d * 180 / math.pi) % 360
            print(f"Rendered {self.i+1}/{self.nframes} (4D rotation: {rotation_deg:.0f}°)")
        self.i += 1


def main():
    ap = argparse.ArgumentParser(description="Render Klein bottle 4D rotation demo.")
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--out", type=str, default=str(Path("renders") / "klein_4d_rotation"))
    args = ap.parse_args()

    runner = KleinBottleRunner(args)
    return runner.start()


if __name__ == "__main__":
    raise SystemExit(main())
