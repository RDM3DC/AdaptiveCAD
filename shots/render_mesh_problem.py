import argparse
import math
import os
import sys
from pathlib import Path

import numpy as np
from OpenGL.GL import *
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

# Import project modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adaptivecad.aacore.sdf import KIND_TORUS, Prim, Scene
from adaptivecad.gui.analytic_viewport import AnalyticViewport

try:
    from PIL import Image, ImageDraw, ImageFont

    _HAVE_PIL = True
except Exception:
    _HAVE_PIL = False


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2.0


def create_mesh_simulation(w, h, zoom_factor=1.0):
    """Create a fake 'meshed' torus with visible triangulation artifacts and surface details."""
    if not _HAVE_PIL:
        return np.zeros((h, w, 4), dtype=np.uint8)

    img = Image.new("RGBA", (w, h), (15, 20, 35, 255))  # dark bg
    draw = ImageDraw.Draw(img)

    # Torus parameters - keep reasonable size to prevent scaling out
    cx, cy = w // 2, h // 2
    base_size = min(w, h) * 0.3  # scale with viewport
    R = base_size * 0.8  # major radius
    r = base_size * 0.3  # minor radius

    # Number of segments (fewer = more visible faceting)
    # Make faceting very obvious especially when zoomed
    n_major = max(8, int(16 * zoom_factor**0.3))  # stay coarse
    n_minor = max(6, int(12 * zoom_factor**0.3))  # stay coarse

    # Draw faceted torus wireframe
    for i in range(n_major):
        for j in range(n_minor):
            # Current and next angles
            u1 = 2 * math.pi * i / n_major
            u2 = 2 * math.pi * (i + 1) / n_major
            v1 = 2 * math.pi * j / n_minor
            v2 = 2 * math.pi * (j + 1) / n_minor

            # Calculate quad vertices
            def torus_point(u, v):
                x = (R + r * math.cos(v)) * math.cos(u)
                y = (R + r * math.cos(v)) * math.sin(u)
                z = r * math.sin(v)
                # Simple perspective projection
                scale = 300 / (300 + z * 0.3)
                return (cx + x * scale, cy + y * scale * 0.8)

            p1 = torus_point(u1, v1)
            p2 = torus_point(u2, v1)
            p3 = torus_point(u2, v2)
            p4 = torus_point(u1, v2)

            # Always show triangulation - make it very obvious
            if zoom_factor > 2.0:  # When zoomed in, emphasize the problem
                edge_color = (120, 140, 180, 255)  # brighter edges
                fill_color = (45, 55, 75, 200)
                line_width = max(2, int(zoom_factor * 0.8))

                # Draw triangles with obvious faceting
                draw.polygon([p1, p2, p3], fill=fill_color)
                draw.polygon([p1, p3, p4], fill=fill_color)

                # Bright wireframe to show mesh structure
                draw.line([p1, p2], fill=edge_color, width=line_width)
                draw.line([p2, p3], fill=edge_color, width=line_width)
                draw.line([p3, p4], fill=edge_color, width=line_width)
                draw.line([p4, p1], fill=edge_color, width=line_width)
                draw.line([p1, p3], fill=edge_color, width=max(1, line_width - 1))  # diagonal

                # Add "surface texture" that shows faceting
                if zoom_factor > 3.0:
                    # Add dots to show vertex positions
                    dot_size = int(zoom_factor * 0.5)
                    for pt in [p1, p2, p3, p4]:
                        draw.ellipse(
                            [
                                pt[0] - dot_size,
                                pt[1] - dot_size,
                                pt[0] + dot_size,
                                pt[1] + dot_size,
                            ],
                            fill=(200, 100, 100),
                        )
            else:
                # Even at distance, show some edge structure
                edge_color = (80, 100, 130)
                fill_color = (60, 70, 90)
                draw.polygon([p1, p2, p3, p4], fill=fill_color)
                # Subtle wireframe
                draw.line([p1, p2], fill=edge_color, width=1)
                draw.line([p2, p3], fill=edge_color, width=1)
                draw.line([p3, p4], fill=edge_color, width=1)
                draw.line([p4, p1], fill=edge_color, width=1)

    return np.array(img)


def save_frame_rgba(view: AnalyticViewport, path: str):
    """Capture current framebuffer via QOpenGLWidget.grabFramebuffer."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    qimg = view.grabFramebuffer()
    try:
        qimg.save(path)
    except Exception:
        ptr = qimg.bits()
        ptr.setsize(qimg.sizeInBytes())
        arr = np.array(ptr, dtype=np.uint8).reshape(qimg.height(), qimg.width(), 4)
        if _HAVE_PIL:
            Image.fromarray(arr, "RGBA").save(path)
        else:
            with open(path + ".raw", "wb") as f:
                f.write(arr.tobytes())


def build_scene() -> Scene:
    """Create a simple torus scene for comparison."""
    scene = Scene()
    # Single torus with nice proportions
    torus = Prim(KIND_TORUS, [1.2, 0.45, 0, 0], beta=0.0, color=(0.9, 0.7, 0.5))
    scene.add(torus)

    # Clean lighting
    scene.bg_color[:] = np.array([0.06, 0.08, 0.14], np.float32)
    scene.env_light[:] = np.array([1.0, 0.9, 1.1], np.float32)
    return scene


class MeshProblemRunner:
    def __init__(self, args):
        self.args = args
        self.nframes = int(args.fps * args.seconds)
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Create viewport for analytic (right side)
        self.host = QWidget()
        self.layout = QVBoxLayout(self.host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.view = AnalyticViewport(self.host, aacore_scene=build_scene())
        self.view.resize(args.w // 2, args.h)  # Half width for split screen
        self.layout.addWidget(self.view)
        self.host.resize(args.w // 2, args.h)
        self.host.show()

        # Camera setup
        self.view.distance = 4.5
        self.view.cam_target = np.array([0.0, 0.0, 0.0], np.float32)
        self.view.yaw = 0.3
        self.view.pitch = 0.2
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
            self.view.update()
            if (
                getattr(self.view, "prog", None) is not None
                and getattr(self.view, "_vao", None) is not None
            ):
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

        # Much slower, more controlled animation to prevent objects scaling out
        if t < 0.3:
            # Initial wide shot - establish the scene (longer)
            phase_t = t / 0.3
            self.view.distance = 5.0 - 0.2 * phase_t  # gentle approach
            self.view.yaw = 0.2 + 0.3 * phase_t
            self.view.pitch = -0.3 + 0.1 * phase_t  # better angle to show torus hole
            zoom_factor = 1.0
            debug_mode = 0  # beauty mode initially
        elif t < 0.7:
            # Gradual zoom - show the difference emerging, switch to heatmap
            phase_t = (t - 0.3) / 0.4
            e = ease_in_out_cubic(phase_t)
            self.view.distance = 4.8 - 0.8 * e  # much more conservative zoom
            self.view.yaw = 0.5 + 0.4 * phase_t
            self.view.pitch = -0.2 + 0.2 * phase_t  # rotate to show surface detail
            zoom_factor = 1.0 + 3.0 * e  # only 4x zoom max to keep in frame
            # Switch to adaptive heatmap partway through
            debug_mode = 5 if phase_t > 0.5 else 0
        else:
            # Final detailed view - hold and rotate slowly, show adaptive features
            phase_t = (t - 0.7) / 0.3
            self.view.distance = 4.0  # safe distance
            self.view.yaw = 0.9 + 0.3 * phase_t  # continue rotation
            self.view.pitch = 0.0 + 0.1 * phase_t  # gentle tilt to show geometry
            zoom_factor = 4.0  # controlled max zoom
            debug_mode = 5  # adaptive heatmap mode

        self.view._update_camera()

        # Render analytic (right) side with adaptive heatmap in later phases
        try:
            self.view.makeCurrent()
        except Exception:
            pass
        self.view._draw_frame(debug_override=debug_mode)
        analytic_qimg = self.view.grabFramebuffer()

        # Convert to numpy array
        w, h = analytic_qimg.width(), analytic_qimg.height()
        ptr = analytic_qimg.bits()
        analytic_arr = np.frombuffer(ptr, dtype=np.uint8, count=w * h * 4).reshape(h, w, 4)

        # Resize analytic array to fit right half of target resolution
        target_w, target_h = self.args.w // 2, self.args.h
        if _HAVE_PIL:
            # Use PIL for high-quality resizing
            analytic_img = Image.fromarray(analytic_arr, "RGBA")
            analytic_img = analytic_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            analytic_arr = np.array(analytic_img)
        else:
            # Fallback: simple crop/pad (not ideal but functional)
            if analytic_arr.shape[:2] != (target_h, target_w):
                new_arr = np.zeros((target_h, target_w, 4), dtype=np.uint8)
                min_h = min(target_h, analytic_arr.shape[0])
                min_w = min(target_w, analytic_arr.shape[1])
                new_arr[:min_h, :min_w, :] = analytic_arr[:min_h, :min_w, :]
                analytic_arr = new_arr

        # Create mesh simulation (left side)
        mesh_arr = create_mesh_simulation(self.args.w // 2, self.args.h, zoom_factor)

        # Combine side by side
        combined = np.zeros((self.args.h, self.args.w, 4), dtype=np.uint8)
        combined[:, : self.args.w // 2, :] = mesh_arr  # Left: meshed
        combined[:, self.args.w // 2 :, :] = analytic_arr  # Right: analytic

        # Add text overlays using PIL
        if _HAVE_PIL:
            combined_img = Image.fromarray(combined, "RGBA")
            draw = ImageDraw.Draw(combined_img)

            try:
                # Try to load a font
                font_large = ImageFont.truetype("arial.ttf", 36)
                font_small = ImageFont.truetype("arial.ttf", 28)
            except BaseException:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Text overlays with slower timing and adaptive explanation
            if t < 0.25:
                # Initial labels - show longer
                draw.text((40, 40), "Traditional CAD", fill=(255, 120, 120), font=font_small)
                draw.text(
                    (self.args.w // 2 + 40, 40), "Adaptive π", fill=(120, 255, 180), font=font_small
                )
            elif t > 0.4:
                # Problem becomes visible earlier
                if t > 0.5:
                    draw.text(
                        (self.args.w // 2 - 180, self.args.h - 140),
                        "Every CAD system",
                        fill=(255, 255, 255),
                        font=font_large,
                    )
                    draw.text(
                        (self.args.w // 2 - 140, self.args.h - 100),
                        "has this problem.",
                        fill=(255, 255, 255),
                        font=font_large,
                    )
                if t > 0.75:
                    draw.text(
                        (self.args.w // 2 - 80, self.args.h - 60),
                        "Until now.",
                        fill=(120, 255, 180),
                        font=font_large,
                    )

                # Add adaptive feature explanations
                if debug_mode == 5 and t > 0.6:
                    draw.text(
                        (self.args.w // 2 + 40, self.args.h - 100),
                        "Adaptive Heatmap",
                        fill=(255, 255, 100),
                        font=font_small,
                    )
                    draw.text(
                        (self.args.w // 2 + 40, self.args.h - 70),
                        "Shows distance field",
                        fill=(200, 200, 200),
                        font=font_small,
                    )
                    draw.text(
                        (self.args.w // 2 + 40, self.args.h - 40),
                        "gradients",
                        fill=(200, 200, 200),
                        font=font_small,
                    )

                # Add zoom indicator when appropriate
                if t > 0.6:
                    zoom_text = f"{zoom_factor:.1f}x zoom"
                    draw.text(
                        (40, self.args.h - 60), zoom_text, fill=(255, 200, 100), font=font_small
                    )

            # Divider line
            draw.line(
                [(self.args.w // 2, 0), (self.args.w // 2, self.args.h)], fill=(80, 80, 80), width=2
            )

            combined = np.array(combined_img)

        # Save frame
        frame_path = self.out_dir / f"frame_{self.i:05d}.png"
        if _HAVE_PIL:
            Image.fromarray(combined, "RGBA").save(frame_path)
        else:
            combined.tofile(str(frame_path) + ".raw")

        if (self.i % 10) == 0:
            print(f"Rendered {self.i+1}/{self.nframes}")
        self.i += 1


def main():
    ap = argparse.ArgumentParser(description='Render "The Mesh Problem" comparison video.')
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--out", type=str, default=str(Path("renders") / "mesh_problem"))
    args = ap.parse_args()

    runner = MeshProblemRunner(args)
    return runner.start()


if __name__ == "__main__":
    raise SystemExit(main())
