#!/usr/bin/env python3
"""
AdaptiveCAD: Hyperbolic Geometry Showcase
Demonstrates non-Euclidean geometry through {7,3} tiling
Mathematical Beauty: Infinite tessellation in hyperbolic space
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

# Import project modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adaptivecad.aacore.math import Xform
from adaptivecad.aacore.sdf import KIND_HYPERBOLIC, Prim, Scene
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


def create_hyperbolic_scene():
    """Create scene with hyperbolic {7,3} tiling"""
    scene = Scene()

    # Main hyperbolic tiling - classic {7,3}
    main_tiling = Prim(
        kind=KIND_HYPERBOLIC,
        params=[2.0, 7, 3, 0],  # scale, order, symmetry, unused
        beta=0.0,
        color=(0.9, 0.3, 0.7),  # Vibrant purple-pink
        xform=Xform(),
    )
    scene.add(main_tiling)

    # Set environment
    scene.global_beta = 0.0
    scene.env_light[:] = np.array([1.5, 1.2, 1.0], np.float32)
    return scene


class HyperbolicGeometryRunner:
    def __init__(self, args):
        self.args = args
        self.nframes = int(args.fps * args.seconds)
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Create viewport
        self.host = QWidget()
        self.layout = QVBoxLayout(self.host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.view = AnalyticViewport(self.host, aacore_scene=create_hyperbolic_scene())
        self.view.resize(args.w, args.h)
        self.layout.addWidget(self.view)
        self.host.resize(args.w, args.h)
        self.host.show()

        # Start with good view of hyperbolic tiling
        self.view.distance = 4.0
        self.view.cam_target = np.array([0.0, 0.0, 0.0], np.float32)
        self.view.yaw = 0.0
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
            print(f"✓ Completed {self.nframes} frames!")
            self.app.quit()
            return

        # Animation parameters
        t = self.i / (self.nframes - 1)  # 0 to 1

        # Order morphing: 7 -> 5 -> 8 -> 7 (impossible in Euclidean space!)
        if t < 0.33:
            order = 7.0 + (5.0 - 7.0) * (t / 0.33) * 3
        elif t < 0.66:
            order = 5.0 + (8.0 - 5.0) * ((t - 0.33) / 0.33) * 3
        else:
            order = 8.0 + (7.0 - 8.0) * ((t - 0.66) / 0.34) * 3

        # Scale pulsing
        base_scale = 2.0
        scale_pulse = 0.3 * math.sin(t * math.pi * 4)
        scale = base_scale + scale_pulse

        # Update the hyperbolic tiling parameters
        if len(self.scene.prims) > 0:
            self.scene.prims[0].params[0] = scale  # scale
            self.scene.prims[0].params[1] = int(order)  # order

        # Camera rotation around the hyperbolic structure
        angle = t * math.pi * 2  # Full rotation
        self.view.yaw = angle
        self.view.pitch = -0.2 + 0.3 * math.sin(t * math.pi * 3)  # Vertical oscillation
        self.view.distance = 4.0 + 1.0 * math.sin(t * math.pi * 2)  # Distance oscillation
        self.view._update_camera()

        # Force update
        self.view.update()
        self.app.processEvents()

        # Capture frame after a brief delay for rendering
        QTimer.singleShot(16, self.capture_frame)

    def capture_frame(self):
        t = self.i / (self.nframes - 1)

        # Capture the rendered image
        qimg = self.view.grabFramebuffer()

        if _HAVE_PIL:
            # Convert to PIL Image for text overlay
            w, h = qimg.width(), qimg.height()
            ptr = qimg.bits()
            arr = np.frombuffer(ptr, dtype=np.uint8, count=w * h * 4).reshape(h, w, 4)

            pil_img = Image.fromarray(arr, "RGBA")
            draw = ImageDraw.Draw(pil_img)

            try:
                font_large = ImageFont.truetype("arial.ttf", 48)
                font_medium = ImageFont.truetype("arial.ttf", 32)
                font_small = ImageFont.truetype("arial.ttf", 24)
            except BaseException:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Title
            title = "AdaptiveCAD: Hyperbolic Geometry"
            draw.text((20, 20), title, fill=(255, 255, 255), font=font_large)

            # Mathematical info
            current_order = self.scene.prims[0].params[1] if len(self.scene.prims) > 0 else 7
            order_text = f"{{7,3}} Tiling - Order: {current_order:.1f}"
            draw.text((20, 80), order_text, fill=(255, 255, 255), font=font_medium)

            # Description
            desc = "Non-Euclidean tessellation • Infinite geometric detail"
            draw.text((20, 120), desc, fill=(200, 200, 200), font=font_small)

            # Impossible in traditional CAD
            impossible = "Impossible in tessellation-based CAD systems"
            draw.text((20, h - 80), impossible, fill=(255, 255, 100), font=font_small)

            # Math equation
            equation = "Distance Field: atanh(r) modulated by angular symmetry"
            draw.text((20, h - 50), equation, fill=(150, 255, 150), font=font_small)

            # Progress indicator
            progress_width = 300
            progress_x = w - progress_width - 20
            progress_y = h - 30

            # Progress bar background
            draw.rectangle(
                [progress_x, progress_y, progress_x + progress_width, progress_y + 20],
                fill=(50, 50, 50),
                outline=(100, 100, 100),
            )

            # Progress bar fill
            fill_width = int(progress_width * t)
            draw.rectangle(
                [progress_x, progress_y, progress_x + fill_width, progress_y + 20],
                fill=(0, 255, 150),
            )

            # Progress text
            progress_text = f"Frame {self.i + 1}/{self.nframes}"
            draw.text(
                (progress_x, progress_y - 25), progress_text, fill=(255, 255, 255), font=font_small
            )

            # Save frame
            frame_path = self.out_dir / f"frame_{self.i:05d}.png"
            pil_img.save(frame_path)
        else:
            # Fallback: save Qt image directly
            frame_path = self.out_dir / f"frame_{self.i:05d}.png"
            qimg.save(str(frame_path))

        print(f"Rendered frame {self.i + 1}/{self.nframes}: {frame_path}")
        self.i += 1

        # Continue to next frame
        QTimer.singleShot(0, self.step)


def render_frame(frame_idx, total_frames, width, height, out_dir):
    """Legacy function - now using Qt-based rendering"""
    pass


def main():
    parser = argparse.ArgumentParser(description="Render hyperbolic geometry video")
    parser.add_argument("--w", type=int, default=1280, help="Width")
    parser.add_argument("--h", type=int, default=720, help="Height")
    parser.add_argument("--fps", type=int, default=30, help="FPS")
    parser.add_argument("--seconds", type=float, default=10, help="Duration in seconds")
    parser.add_argument(
        "--out", type=str, default="renders/hyperbolic_geometry", help="Output directory"
    )

    args = parser.parse_args()

    print(
        f"Rendering hyperbolic geometry showcase: {args.w}x{args.h} @ {args.fps}fps for {args.seconds}s"
    )
    print(f"Output directory: {args.out}")

    runner = HyperbolicGeometryRunner(args)
    return runner.start()


if __name__ == "__main__":
    sys.exit(main())
