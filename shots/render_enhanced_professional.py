#!/usr/bin/env python3
"""
AdaptiveCAD: Professional Video Enhancement Suite
Creates polished, branded videos with smooth motion and educational overlays
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
from adaptivecad.aacore.sdf import (
    KIND_MANDELBULB,
    Prim,
    Scene,
)
from adaptivecad.gui.analytic_viewport import AnalyticViewport

try:
    from PIL import Image, ImageDraw, ImageFont

    _HAVE_PIL = True
except Exception:
    _HAVE_PIL = False


# Professional easing functions
def ease_in_out_quint(t: float) -> float:
    """Ultra-smooth quintic easing for cinematic camera motion"""
    t = max(0.0, min(1.0, t))
    return 16 * t * t * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 5) / 2.0


def smooth_step(edge0: float, edge1: float, x: float) -> float:
    """Hermite interpolation for buttery-smooth transitions"""
    x = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return x * x * (3.0 - 2.0 * x)


def ease_bounce_out(t: float) -> float:
    """Bounce easing for playful motion accents"""
    t = max(0.0, min(1.0, t))
    if t < 1 / 2.75:
        return 7.5625 * t * t
    elif t < 2 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    elif t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    else:
        t -= 2.625 / 2.75
        return 7.5625 * t * t + 0.984375


# AdaptiveCAD Brand Colors
BRAND_PRIMARY = (0, 174, 255)  # Bright blue
BRAND_SECONDARY = (255, 107, 53)  # Orange accent
BRAND_ACCENT = (138, 255, 128)  # Green highlight
BRAND_DARK = (20, 25, 35)  # Deep background
BRAND_LIGHT = (240, 245, 250)  # Light text


def add_professional_overlay(draw, width, height, title, subtitle, t, extra_info=None):
    """Add professional branding and educational overlays"""

    try:
        # Professional fonts
        font_title = ImageFont.truetype("arial.ttf", 48)
        font_subtitle = ImageFont.truetype("arial.ttf", 32)
        font_body = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 20)
    except BaseException:
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Gradient background for titles (simulate with rectangles)
    overlay_alpha = int(180 * smooth_step(0.0, 0.2, t))
    for i in range(5):
        alpha = overlay_alpha - i * 30
        if alpha > 0:
            color = (*BRAND_DARK, alpha)
            draw.rectangle([0, 0, width, 150 - i * 10], fill=color)

    # Main title with glow effect
    title_y = 30
    # Glow effect (multiple offset draws)
    for offset in [(2, 2), (-2, 2), (2, -2), (-2, -2), (0, 2), (0, -2), (2, 0), (-2, 0)]:
        draw.text(
            (30 + offset[0], title_y + offset[1]), title, fill=(*BRAND_DARK, 100), font=font_title
        )
    # Main text
    draw.text((30, title_y), title, fill=BRAND_LIGHT, font=font_title)

    # Subtitle
    draw.text((30, title_y + 60), subtitle, fill=BRAND_ACCENT, font=font_subtitle)

    # Educational context
    if extra_info:
        context_y = height - 150
        for i, info in enumerate(extra_info):
            draw.text((30, context_y + i * 30), info, fill=BRAND_LIGHT, font=font_body)

    # AdaptiveCAD logo area (placeholder)
    logo_x, logo_y = width - 300, height - 120
    draw.rectangle(
        [logo_x, logo_y, logo_x + 250, logo_y + 80],
        fill=(*BRAND_PRIMARY, 180),
        outline=BRAND_LIGHT,
        width=2,
    )
    draw.text((logo_x + 20, logo_y + 15), "AdaptiveCAD", fill=BRAND_LIGHT, font=font_subtitle)
    draw.text(
        (logo_x + 20, logo_y + 45), "Mathematical Precision", fill=BRAND_ACCENT, font=font_small
    )

    # Progress bar
    progress_width = 400
    progress_x = width - progress_width - 30
    progress_y = 30

    # Background
    draw.rectangle(
        [progress_x, progress_y, progress_x + progress_width, progress_y + 8],
        fill=(*BRAND_DARK, 100),
        outline=BRAND_LIGHT,
        width=1,
    )

    # Fill with gradient effect
    fill_width = int(progress_width * t)
    draw.rectangle(
        [progress_x, progress_y, progress_x + fill_width, progress_y + 8], fill=BRAND_PRIMARY
    )

    # Kickstarter CTA (appears at end)
    if t > 0.85:
        cta_alpha = int(255 * smooth_step(0.85, 1.0, t))
        cta_y = height - 60
        draw.text(
            (width // 2 - 150, cta_y),
            "Support on Kickstarter",
            fill=(*BRAND_SECONDARY, cta_alpha),
            font=font_subtitle,
        )


class EnhancedMandelbulbRunner:
    """Professional Mandelbulb infinite zoom with enhanced visuals"""

    def __init__(self, args):
        self.args = args
        self.nframes = int(args.fps * args.seconds)
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Create scene
        scene = Scene()
        mandelbulb = Prim(
            KIND_MANDELBULB, [8.0, 2.5, 16, 1.0], beta=0.0, color=(0.9, 0.4, 0.1)
        )  # Warm orange
        scene.add(mandelbulb)
        scene.bg_color[:] = np.array([0.02, 0.03, 0.08], np.float32)
        scene.env_light[:] = np.array([1.5, 1.2, 1.0], np.float32)

        # Create viewport
        self.host = QWidget()
        self.layout = QVBoxLayout(self.host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.view = AnalyticViewport(self.host, aacore_scene=scene)
        self.view.resize(args.w, args.h)
        self.layout.addWidget(self.view)
        self.host.resize(args.w, args.h)
        self.host.show()

        # Professional camera setup
        self.view.distance = 5.0
        self.view.cam_target = np.array([0.0, 0.0, 0.0], np.float32)
        self.view.yaw = 0.2
        self.view.pitch = -0.1
        self.view._update_camera()

        self.scene = self.view.scene
        self.out_dir = Path(self.args.out)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.i = 0

        # Timer setup
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
        return self.app.exec()

    def step(self):
        if self.i >= self.nframes:
            print(f"✓ Enhanced Mandelbulb complete! ({self.nframes} frames)")
            self.app.quit()
            return

        t_raw = self.i / (self.nframes - 1)

        # Multi-phase cinematic zoom
        if t_raw < 0.2:  # Hero pause
            zoom_t = 0.0
        elif t_raw < 0.4:  # Gentle approach
            zoom_t = smooth_step(0.2, 0.4, t_raw) * 0.3
        elif t_raw < 0.8:  # Main acceleration
            zoom_t = 0.3 + smooth_step(0.4, 0.8, t_raw) * 0.6
        else:  # Final zoom burst
            zoom_t = 0.9 + ease_bounce_out((t_raw - 0.8) / 0.2) * 0.1

        # Professional zoom curve
        zoom_factor = pow(10.0, zoom_t * 6.0)  # 1x to 1M
        self.view.distance = 5.0 / zoom_factor

        # Cinematic camera movement
        angle = ease_in_out_quint(t_raw) * math.pi * 0.8
        self.view.yaw = 0.2 + angle
        self.view.pitch = -0.1 + 0.15 * math.sin(t_raw * math.pi * 1.7)

        # Detail exploration target
        detail_scale = 0.5 * (zoom_factor / 10000) ** 0.3
        self.view.cam_target = np.array(
            [
                detail_scale * math.sin(t_raw * 2.3),
                detail_scale * math.cos(t_raw * 3.1),
                detail_scale * math.sin(t_raw * 4.7),
            ],
            np.float32,
        )

        # Adaptive quality
        detail_level = int(16 + 48 * zoom_t)
        self.scene.prims[0].params[2] = detail_level

        self.view._update_camera()
        self.view.update()
        self.app.processEvents()

        QTimer.singleShot(16, lambda: self.capture_frame(t_raw, zoom_factor, detail_level))

    def capture_frame(self, t, zoom_factor, detail_level):
        qimg = self.view.grabFramebuffer()

        if _HAVE_PIL:
            w, h = qimg.width(), qimg.height()
            ptr = qimg.bits()
            arr = np.frombuffer(ptr, dtype=np.uint8, count=w * h * 4).reshape(h, w, 4)

            img = Image.fromarray(arr, "RGBA")
            draw = ImageDraw.Draw(img)

            # Professional overlay
            zoom_text = (
                f"{zoom_factor/1000000:.2f}M×"
                if zoom_factor >= 1000000
                else f"{zoom_factor/1000:.1f}K×" if zoom_factor >= 1000 else f"{zoom_factor:.0f}×"
            )

            extra_info = [
                f"Zoom Level: {zoom_text}",
                f"Iteration Detail: {detail_level}",
                "Infinite mathematical precision",
            ]

            add_professional_overlay(
                draw, w, h, "Mandelbulb Fractal", "Infinite Zoom Capability", t, extra_info
            )

            frame_path = self.out_dir / f"frame_{self.i:05d}.png"
            img.save(frame_path)
        else:
            frame_path = self.out_dir / f"frame_{self.i:05d}.png"
            qimg.save(str(frame_path))

        print(f"Enhanced frame {self.i + 1}/{self.nframes}: {frame_path}")
        self.i += 1
        QTimer.singleShot(0, self.step)


def main():
    parser = argparse.ArgumentParser(description="Enhanced AdaptiveCAD video renderer")
    parser.add_argument("--w", type=int, default=1920, help="Width (default 1920)")
    parser.add_argument("--h", type=int, default=1080, help="Height (default 1080)")
    parser.add_argument("--fps", type=int, default=30, help="FPS (default 30)")
    parser.add_argument("--seconds", type=float, default=12, help="Duration")
    parser.add_argument(
        "--type",
        type=str,
        default="mandelbulb",
        choices=["mandelbulb", "klein", "menger", "hyperbolic"],
        help="Video type to render",
    )
    parser.add_argument("--out", type=str, default="renders/enhanced", help="Output directory")

    args = parser.parse_args()

    print(f"🎬 Rendering enhanced {args.type} video: {args.w}x{args.h} @ {args.fps}fps")
    print("Professional quality with branding and smooth motion")

    if args.type == "mandelbulb":
        runner = EnhancedMandelbulbRunner(args)
    else:
        print(f"Enhanced {args.type} renderer coming soon!")
        return 1

    return runner.start()


if __name__ == "__main__":
    sys.exit(main())
