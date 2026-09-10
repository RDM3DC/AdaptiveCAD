#!/usr/bin/env python3
"""Render Mandelbulb infinite zoom demo - mathematically stunning fractal detail."""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

# Import project modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adaptivecad.aacore.sdf import KIND_MANDELBULB, Prim, Scene
from adaptivecad.gui.analytic_viewport import AnalyticViewport

try:
    from PIL import Image, ImageDraw, ImageFont

    _HAVE_PIL = True
except Exception:
    _HAVE_PIL = False


def ease_in_out_cubic(t: float) -> float:
    """Smooth cubic easing for professional camera motion"""
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


def build_mandelbulb_scene() -> Scene:
    """Create a scene with high-detail Mandelbulb for infinite zoom."""
    scene = Scene()

    # High-iteration Mandelbulb for infinite detail
    mandelbulb = Prim(KIND_MANDELBULB, [8.0, 2.0, 32, 1.0], beta=0.0, color=(0.9, 0.3, 0.1))
    scene.add(mandelbulb)

    # Dramatic dark background
    scene.bg_color[:] = np.array([0.005, 0.01, 0.02], np.float32)
    scene.env_light[:] = np.array([1.5, 1.2, 1.0], np.float32)
    return scene


class MandelbulbZoomRunner:
    def __init__(self, args):
        self.args = args
        self.nframes = int(args.fps * args.seconds)
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Create viewport
        self.host = QWidget()
        self.layout = QVBoxLayout(self.host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.view = AnalyticViewport(self.host, aacore_scene=build_mandelbulb_scene())
        self.view.resize(args.w, args.h)
        self.layout.addWidget(self.view)
        self.host.resize(args.w, args.h)
        self.host.show()

        # Start with wide view of whole Mandelbulb
        self.view.distance = 5.0
        self.view.cam_target = np.array([0.0, 0.0, 0.0], np.float32)
        self.view.yaw = 0.2
        self.view.pitch = -0.1
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

        t_raw = self.i / max(1, self.nframes - 1)  # 0..1

        # Apply quintic easing for ultra-smooth cinematic motion
        t_smooth = ease_in_out_quint(t_raw)

        # Multi-phase zoom with dramatic pauses for better storytelling
        if t_raw < 0.15:  # Initial pause - show full Mandelbulb majesty
            zoom_t = 0.0
        elif t_raw < 0.35:  # Gentle approach phase
            zoom_t = smooth_step(0.15, 0.35, t_raw) * 0.3
        elif t_raw < 0.8:  # Main zoom acceleration
            zoom_t = 0.3 + smooth_step(0.35, 0.8, t_raw) * 0.6
        else:  # Final explosive zoom into infinite detail
            zoom_t = 0.9 + ease_in_out_cubic((t_raw - 0.8) / 0.2) * 0.1

        # Enhanced exponential zoom with smoother scaling
        zoom_factor = pow(10.0, zoom_t * 6.0)  # 1 to 1,000,000x zoom!
        self.view.distance = 5.0 / zoom_factor

        # Cinematic camera motion with orbital sweep
        angle_base = t_smooth * math.pi * 0.8  # Main rotation
        angle_micro = math.sin(t_raw * math.pi * 12) * 0.05  # Micro movements

        self.view.yaw = 0.2 + angle_base + angle_micro
        self.view.pitch = (
            -0.1 + 0.2 * math.sin(2 * math.pi * t_raw * 0.7) + 0.05 * math.cos(t_raw * math.pi * 15)
        )

        # Enhanced target with detail exploration path
        zoom_center = np.array(
            [
                0.8 * math.sin(t_raw * 2.0) * 0.5 * (1 + 0.1 * math.sin(t_raw * math.pi * 23)),
                0.6 * math.cos(t_raw * 3.0) * 0.3 * (1 + 0.1 * math.cos(t_raw * math.pi * 19)),
                0.4 * math.sin(t_raw * 5.0) * 0.2 * (1 + 0.1 * math.sin(t_raw * math.pi * 29)),
            ],
            np.float32,
        )
        self.view.cam_target = zoom_center

        # Adaptive iteration count for optimal detail vs performance
        mandelbulb = self.scene.prims[0]
        detail_level = int(16 + 48 * zoom_t)  # 16 to 64 iterations based on zoom
        mandelbulb.params[2] = detail_level  # max_iter parameter

        # Enhanced bailout radius for better convergence at high zoom
        bailout_radius = 2.0 + 0.5 * math.log10(max(1, zoom_factor / 100))
        mandelbulb.params[1] = bailout_radius

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

            # Title with fractal glow effect
            title_color = (255, 180, 100) if t_raw < 0.5 else (255, 120, 80)
            draw.text((50, 50), "Mandelbulb", fill=title_color, font=font_large)
            draw.text((50, 110), "Infinite Zoom", fill=(255, 255, 200), font=font_large)

            # Zoom level indicator with enhanced formatting
            if zoom_factor >= 1000000:
                zoom_text = f"Zoom: {zoom_factor/1000000:.1f}Mx"
            elif zoom_factor >= 1000:
                zoom_text = f"Zoom: {zoom_factor/1000:.1f}Kx"
            else:
                zoom_text = f"Zoom: {zoom_factor:.0f}x"
            draw.text((50, self.args.h - 120), zoom_text, fill=(100, 255, 150), font=font_small)

            # Detail level with performance indicator
            draw.text(
                (50, self.args.h - 80),
                f"Detail: {detail_level} iterations",
                fill=(200, 200, 255),
                font=font_small,
            )

            # Mathematical note for high zoom
            if t_raw > 0.7:
                draw.text(
                    (50, self.args.h - 40),
                    "Mathematically infinite detail",
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
            print(f"Rendered {self.i+1}/{self.nframes} (zoom: {zoom_factor:.0f}x)")
        self.i += 1


def main():
    ap = argparse.ArgumentParser(description="Render Mandelbulb infinite zoom demo.")
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--out", type=str, default=str(Path("renders") / "mandelbulb_zoom"))
    args = ap.parse_args()

    runner = MandelbulbZoomRunner(args)
    return runner.start()


if __name__ == "__main__":
    raise SystemExit(main())
