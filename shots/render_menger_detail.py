#!/usr/bin/env python3
"""Render Menger sponge infinite detail demo - CSG fractal showcase."""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

# Import project modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adaptivecad.aacore.sdf import KIND_MENGER, Prim, Scene
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


def build_menger_scene() -> Scene:
    """Create a scene with adaptive detail Menger sponge."""
    scene = Scene()

    # Start with medium detail, will increase during zoom
    menger = Prim(KIND_MENGER, [3, 1.0, 0, 0], beta=0.0, color=(0.9, 0.7, 0.3))
    scene.add(menger)

    # Dramatic lighting for CSG details
    scene.bg_color[:] = np.array([0.01, 0.02, 0.04], np.float32)
    scene.env_light[:] = np.array([1.6, 1.3, 1.0], np.float32)
    return scene


class MengerZoomRunner:
    def __init__(self, args):
        self.args = args
        self.nframes = int(args.fps * args.seconds)
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Create viewport
        self.host = QWidget()
        self.layout = QVBoxLayout(self.host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.view = AnalyticViewport(self.host, aacore_scene=build_menger_scene())
        self.view.resize(args.w, args.h)
        self.layout.addWidget(self.view)
        self.host.resize(args.w, args.h)
        self.host.show()

        # Start with overview of the whole sponge
        self.view.distance = 6.0
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

        # Progressive zoom into fractal details
        zoom_factor = 1.0 + pow(t, 1.5) * 15.0  # 1x to 16x zoom
        self.view.distance = 6.0 / zoom_factor

        # Rotate to show different faces and holes
        self.view.yaw = 0.3 + 1.2 * t
        self.view.pitch = -0.2 + 0.4 * math.sin(2 * math.pi * t * 0.8)

        # Target interesting corner regions as we zoom
        corner_offset = np.array(
            [0.3 * math.sin(t * 3.0), 0.3 * math.cos(t * 2.5), 0.2 * math.sin(t * 4.0)], np.float32
        )
        self.view.cam_target = corner_offset

        # Increase detail level as we zoom in
        detail_level = 3 + int(t * 3)  # 3 to 6 iterations
        detail_level = min(detail_level, 6)  # Cap at 6 for performance

        menger = self.scene.prims[0]
        menger.params[0] = detail_level  # iterations parameter

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

            # Title with fractal theme
            draw.text((50, 50), "Menger Sponge", fill=(255, 200, 120), font=font_large)
            draw.text((50, 110), "Infinite CSG Detail", fill=(255, 220, 140), font=font_large)

            # Detail level indicator
            draw.text(
                (50, self.args.h - 140),
                f"Detail Level: {detail_level}",
                fill=(150, 255, 150),
                font=font_small,
            )

            # Zoom level
            draw.text(
                (50, self.args.h - 100),
                f"Zoom: {zoom_factor:.1f}x",
                fill=(100, 200, 255),
                font=font_small,
            )

            # CSG operations count (estimated)
            operations = 20 * (3**detail_level)  # Exponential growth
            if operations < 1000:
                ops_text = f"{operations} CSG operations"
            else:
                ops_text = f"{operations//1000}K+ CSG operations"
            draw.text((50, self.args.h - 60), ops_text, fill=(255, 180, 100), font=font_small)

            # Mathematical note
            if t > 0.7:
                draw.text(
                    (50, self.args.h - 20),
                    "Perfect boolean operations",
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
            print(
                f"Rendered {self.i+1}/{self.nframes} (detail: L{detail_level}, zoom: {zoom_factor:.1f}x)"
            )
        self.i += 1


def main():
    ap = argparse.ArgumentParser(description="Render Menger sponge infinite detail demo.")
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--out", type=str, default=str(Path("renders") / "menger_detail"))
    args = ap.parse_args()

    runner = MengerZoomRunner(args)
    return runner.start()


if __name__ == "__main__":
    raise SystemExit(main())
