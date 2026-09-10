#!/usr/bin/env python3
"""Render a 4D torus demo video showing slicing through the 4th dimension."""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

# Import project modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adaptivecad.aacore.sdf import KIND_TORUS4D, Prim, Scene
from adaptivecad.gui.analytic_viewport import AnalyticViewport

try:
    from PIL import Image, ImageDraw, ImageFont

    _HAVE_PIL = True
except Exception:
    _HAVE_PIL = False


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2.0


def build_4d_torus_scene() -> Scene:
    """Create a scene with animated 4D torus."""
    scene = Scene()

    # Main 4D torus that we'll slice through
    torus4d = Prim(KIND_TORUS4D, [1.2, 0.8, 0.2, 0.0], beta=0.0, color=(0.9, 0.4, 0.7))
    scene.add(torus4d)

    # Clean dark background with nice lighting
    scene.bg_color[:] = np.array([0.02, 0.05, 0.12], np.float32)
    scene.env_light[:] = np.array([1.2, 1.0, 1.4], np.float32)
    return scene


class Torus4DRunner:
    def __init__(self, args):
        self.args = args
        self.nframes = int(args.fps * args.seconds)
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Create viewport
        self.host = QWidget()
        self.layout = QVBoxLayout(self.host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.view = AnalyticViewport(self.host, aacore_scene=build_4d_torus_scene())
        self.view.resize(args.w, args.h)
        self.layout.addWidget(self.view)
        self.host.resize(args.w, args.h)
        self.host.show()

        # Camera setup - nice cinematic angle
        self.view.distance = 4.0
        self.view.cam_target = np.array([0.0, 0.0, 0.0], np.float32)
        self.view.yaw = 0.3
        self.view.pitch = -0.2
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

        # Gentle camera orbit
        orbit_speed = 0.5
        self.view.yaw = 0.3 + orbit_speed * t
        self.view.pitch = -0.2 + 0.1 * math.sin(2 * math.pi * t * 0.7)

        # 4D slice animation - sweep through the 4th dimension
        w_slice = 1.5 * math.sin(2 * math.pi * t * 1.0)  # -1.5 to +1.5

        # Update the 4D torus parameters
        torus = self.scene.prims[0]
        torus.params[3] = w_slice  # w_slice parameter

        self.view._update_camera()

        # Render frame
        try:
            self.view.makeCurrent()
        except Exception:
            pass
        self.view._draw_frame(debug_override=0)

        # Capture frame
        qimg = self.view.grabFramebuffer()

        # Add text overlay using PIL
        if _HAVE_PIL:
            # Convert to PIL
            w, h = qimg.width(), qimg.height()
            ptr = qimg.bits()
            arr = np.frombuffer(ptr, dtype=np.uint8, count=w * h * 4).reshape(h, w, 4)

            img = Image.fromarray(arr, "RGBA")
            draw = ImageDraw.Draw(img)

            try:
                font_large = ImageFont.truetype("arial.ttf", 48)
                font_small = ImageFont.truetype("arial.ttf", 32)
            except BaseException:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Title
            draw.text((50, 50), "4D Torus (Duocylinder)", fill=(255, 255, 255), font=font_large)

            # 4D slice indicator
            slice_text = f"4D Slice: w = {w_slice:.2f}"
            draw.text((50, self.args.h - 120), slice_text, fill=(255, 200, 100), font=font_small)

            # Description
            draw.text(
                (50, self.args.h - 80),
                "Cross-section through 4th dimension",
                fill=(200, 200, 200),
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
            print(f"Rendered {self.i+1}/{self.nframes}")
        self.i += 1


def main():
    ap = argparse.ArgumentParser(description="Render 4D torus slicing demo video.")
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--out", type=str, default=str(Path("renders") / "torus4d_demo"))
    args = ap.parse_args()

    runner = Torus4DRunner(args)
    return runner.start()


if __name__ == "__main__":
    raise SystemExit(main())
