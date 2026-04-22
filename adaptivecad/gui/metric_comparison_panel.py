from __future__ import annotations

"""Metric comparison panel for Euclidean, pi_f, and pi_a.

This module adds a lightweight Qt panel that compares several geometric
measurements under three metric interpretations:

- Euclidean: ordinary flat-space geometry
- pi_f: a *prototype* flat-adaptive metric field used for experimentation
- pi_a: the existing AdaptiveCAD curvature-aware pi_a kernel

Important note:
The repository already has a real ``pi_a`` implementation, but it does not yet
have a canonical first-class ``pi_f`` kernel. For that reason this panel uses a
bounded radial prototype for ``pi_f`` so the user can explore comparisons now
without pretending the formal pi_f kernel is finalized.
"""

from dataclasses import dataclass
import math
from typing import Callable, Iterable

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QApplication,
        QDoubleSpinBox,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QPlainTextEdit,
        QPushButton,
        QSpinBox,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except Exception as exc:  # pragma: no cover - runtime dependency path
    raise RuntimeError("PySide6 is required to run the metric comparison panel") from exc

from adaptivecad.pi.kernel import PiAParams, adaptive_arc_length, pi_a


PHI = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass(frozen=True)
class PiFParams:
    """Prototype flat-adaptive metric parameters.

    beta:
        Controls how strongly the local flat-adaptive field deviates from pi.
    s0:
        Reference scale in drawing units.
    clamp:
        Maximum fractional deviation from ordinary pi.
    phi_weight:
        Optional golden-ratio/Fibonacci-inspired weighting term. This is kept
        explicit so experiments can toggle it without claiming it is part of the
        canonical theory.
    """

    beta: float = 0.15
    s0: float = 10.0
    clamp: float = 0.25
    phi_weight: float = 0.0


@dataclass(frozen=True)
class Point2:
    x: float
    y: float


@dataclass(frozen=True)
class SegmentSpec:
    p0: Point2
    p1: Point2
    ambient_kappa: float
    samples: int


@dataclass(frozen=True)
class ArcSpec:
    center: Point2
    radius: float
    start_deg: float
    sweep_deg: float
    samples: int


@dataclass(frozen=True)
class RowResult:
    label: str
    euclidean: float
    pi_f: float
    pi_a: float


def _clamp(value: float, lo: float, hi: float) -> float:
    return hi if value > hi else lo if value < lo else value


def _lerp(a: float, b: float, t: float) -> float:
    return (1.0 - t) * a + t * b


def euclidean_distance(p: Point2, q: Point2) -> float:
    return math.hypot(q.x - p.x, q.y - p.y)


def pi_f_value(point: Point2, reference: Point2, params: PiFParams) -> float:
    """Prototype pi_f field evaluated at a point.

    The field is intentionally simple and bounded:

        pi_f(x) = pi * (1 + beta * (r/s0)^2 + phi_weight * phi_term), clamped

    where r is the Euclidean distance to the chosen reference origin.  The
    optional phi_term lets the user explore whether golden-ratio weighting helps
    stabilize or organize experiments, without treating it as established fact.
    """

    r = euclidean_distance(point, reference)
    s0 = max(float(params.s0), 1e-9)
    frac = float(params.beta) * (r / s0) ** 2
    if abs(params.phi_weight) > 1e-12:
        frac += float(params.phi_weight) * ((1.0 / PHI) - 0.5)
    frac = _clamp(frac, -abs(float(params.clamp)), abs(float(params.clamp)))
    return math.pi * (1.0 + frac)


def integrate_segment(
    p0: Point2,
    p1: Point2,
    samples: int,
    scale_fn: Callable[[Point2], float],
) -> float:
    n = max(8, int(samples))
    total = 0.0
    for i in range(n):
        t0 = i / n
        t1 = (i + 1) / n
        a = Point2(_lerp(p0.x, p1.x, t0), _lerp(p0.y, p1.y, t0))
        b = Point2(_lerp(p0.x, p1.x, t1), _lerp(p0.y, p1.y, t1))
        mid = Point2(0.5 * (a.x + b.x), 0.5 * (a.y + b.y))
        total += euclidean_distance(a, b) * float(scale_fn(mid))
    return total


def integrate_arc(
    center: Point2,
    radius: float,
    start_deg: float,
    sweep_deg: float,
    samples: int,
    scale_fn: Callable[[Point2], float],
) -> float:
    n = max(16, int(samples))
    r = max(1e-9, float(radius))
    total = 0.0
    start = math.radians(float(start_deg))
    sweep = math.radians(float(sweep_deg))
    for i in range(n):
        t0 = i / n
        t1 = (i + 1) / n
        a0 = start + sweep * t0
        a1 = start + sweep * t1
        p0 = Point2(center.x + r * math.cos(a0), center.y + r * math.sin(a0))
        p1 = Point2(center.x + r * math.cos(a1), center.y + r * math.sin(a1))
        mid = Point2(0.5 * (p0.x + p1.x), 0.5 * (p0.y + p1.y))
        total += euclidean_distance(p0, p1) * float(scale_fn(mid))
    return total


def circumference_pi_f(center: Point2, radius: float, samples: int, ref: Point2, params: PiFParams) -> float:
    return integrate_arc(
        center=center,
        radius=radius,
        start_deg=0.0,
        sweep_deg=360.0,
        samples=samples,
        scale_fn=lambda p: pi_f_value(p, ref, params) / math.pi,
    )


def circumference_pi_a(radius: float, pia_params: PiAParams) -> float:
    r = max(1e-9, float(radius))
    pa = pi_a(kappa=1.0 / r, scale=r, params=pia_params)
    return 2.0 * r * pa


def segment_pi_a_length(spec: SegmentSpec, pia_params: PiAParams) -> float:
    euclid = euclidean_distance(spec.p0, spec.p1)
    if euclid <= 1e-12:
        return 0.0
    pa = pi_a(kappa=float(spec.ambient_kappa), scale=euclid, params=pia_params)
    return euclid * (pa / math.pi)


def arc_pi_a_length(spec: ArcSpec, pia_params: PiAParams) -> float:
    r = max(1e-9, float(spec.radius))
    return adaptive_arc_length(
        radius=r,
        angle_rad=math.radians(float(spec.sweep_deg)),
        kappa=1.0 / r,
        scale=r,
        params=pia_params,
    )


def build_results(
    reference: Point2,
    seg: SegmentSpec,
    arc: ArcSpec,
    pif_params: PiFParams,
    pia_params: PiAParams,
) -> list[RowResult]:
    seg_e = euclidean_distance(seg.p0, seg.p1)
    seg_f = integrate_segment(
        seg.p0,
        seg.p1,
        seg.samples,
        scale_fn=lambda p: pi_f_value(p, reference, pif_params) / math.pi,
    )
    seg_a = segment_pi_a_length(seg, pia_params)

    arc_e = abs(math.radians(arc.sweep_deg)) * max(0.0, arc.radius)
    arc_f = integrate_arc(
        arc.center,
        arc.radius,
        arc.start_deg,
        arc.sweep_deg,
        arc.samples,
        scale_fn=lambda p: pi_f_value(p, reference, pif_params) / math.pi,
    )
    arc_a = arc_pi_a_length(arc, pia_params)

    circ_e = 2.0 * math.pi * max(0.0, arc.radius)
    circ_f = circumference_pi_f(arc.center, arc.radius, arc.samples, reference, pif_params)
    circ_a = circumference_pi_a(arc.radius, pia_params)

    return [
        RowResult("Segment length", seg_e, seg_f, seg_a),
        RowResult("Arc length", arc_e, arc_f, arc_a),
        RowResult("Circle circumference", circ_e, circ_f, circ_a),
    ]


class FloatBox(QDoubleSpinBox):
    def __init__(self, value: float, lo: float = -1e9, hi: float = 1e9, decimals: int = 6):
        super().__init__()
        self.setRange(lo, hi)
        self.setDecimals(decimals)
        self.setValue(value)
        self.setSingleStep(0.1)


class MetricComparisonPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Metric Comparison Panel — Euclidean vs pi_f vs pi_a")

        outer = QHBoxLayout(self)
        controls = QVBoxLayout()
        results = QVBoxLayout()
        outer.addLayout(controls, 0)
        outer.addLayout(results, 1)

        controls.addWidget(self._build_reference_box())
        controls.addWidget(self._build_segment_box())
        controls.addWidget(self._build_arc_box())
        controls.addWidget(self._build_metric_box())

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch(1)
        controls.addLayout(btn_row)
        controls.addStretch(1)

        self.table = QTableWidget(3, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Quantity",
                "Euclidean",
                "pi_f",
                "pi_a",
                "Δ pi_f",
                "% pi_f",
                "% pi_a",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        try:
            self.table.horizontalHeader().setStretchLastSection(True)
        except Exception:
            pass
        results.addWidget(self.table)

        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        try:
            self.summary.setFont(QFont("Courier New", 10))
        except Exception:
            pass
        results.addWidget(self.summary, 1)

        self.refresh()

    def _build_reference_box(self) -> QGroupBox:
        box = QGroupBox("Reference origin for pi_f field")
        form = QFormLayout(box)
        self.ref_x = FloatBox(0.0)
        self.ref_y = FloatBox(0.0)
        form.addRow("Reference X", self.ref_x)
        form.addRow("Reference Y", self.ref_y)
        return box

    def _build_segment_box(self) -> QGroupBox:
        box = QGroupBox("Segment test")
        grid = QGridLayout(box)
        self.seg_x0 = FloatBox(0.0)
        self.seg_y0 = FloatBox(0.0)
        self.seg_x1 = FloatBox(10.0)
        self.seg_y1 = FloatBox(0.0)
        self.seg_kappa = FloatBox(0.0, lo=-1e6, hi=1e6)
        self.seg_samples = QSpinBox()
        self.seg_samples.setRange(8, 2048)
        self.seg_samples.setValue(128)
        grid.addWidget(QLabel("P0 X"), 0, 0)
        grid.addWidget(self.seg_x0, 0, 1)
        grid.addWidget(QLabel("P0 Y"), 0, 2)
        grid.addWidget(self.seg_y0, 0, 3)
        grid.addWidget(QLabel("P1 X"), 1, 0)
        grid.addWidget(self.seg_x1, 1, 1)
        grid.addWidget(QLabel("P1 Y"), 1, 2)
        grid.addWidget(self.seg_y1, 1, 3)
        grid.addWidget(QLabel("Ambient κ for pi_a"), 2, 0)
        grid.addWidget(self.seg_kappa, 2, 1)
        grid.addWidget(QLabel("Samples"), 2, 2)
        grid.addWidget(self.seg_samples, 2, 3)
        return box

    def _build_arc_box(self) -> QGroupBox:
        box = QGroupBox("Arc / circle test")
        grid = QGridLayout(box)
        self.arc_cx = FloatBox(0.0)
        self.arc_cy = FloatBox(0.0)
        self.arc_r = FloatBox(10.0, lo=1e-9, hi=1e9)
        self.arc_start = FloatBox(0.0)
        self.arc_sweep = FloatBox(90.0)
        self.arc_samples = QSpinBox()
        self.arc_samples.setRange(16, 4096)
        self.arc_samples.setValue(256)
        grid.addWidget(QLabel("Center X"), 0, 0)
        grid.addWidget(self.arc_cx, 0, 1)
        grid.addWidget(QLabel("Center Y"), 0, 2)
        grid.addWidget(self.arc_cy, 0, 3)
        grid.addWidget(QLabel("Radius"), 1, 0)
        grid.addWidget(self.arc_r, 1, 1)
        grid.addWidget(QLabel("Start deg"), 1, 2)
        grid.addWidget(self.arc_start, 1, 3)
        grid.addWidget(QLabel("Sweep deg"), 2, 0)
        grid.addWidget(self.arc_sweep, 2, 1)
        grid.addWidget(QLabel("Samples"), 2, 2)
        grid.addWidget(self.arc_samples, 2, 3)
        return box

    def _build_metric_box(self) -> QGroupBox:
        box = QGroupBox("Metric parameters")
        grid = QGridLayout(box)
        self.pif_beta = FloatBox(0.15, lo=-1e3, hi=1e3)
        self.pif_s0 = FloatBox(10.0, lo=1e-9, hi=1e9)
        self.pif_clamp = FloatBox(0.25, lo=0.0, hi=1.0)
        self.pif_phi_weight = FloatBox(0.0, lo=-10.0, hi=10.0)
        self.pia_beta = FloatBox(0.2, lo=-1e3, hi=1e3)
        self.pia_s0 = FloatBox(1.0, lo=1e-9, hi=1e9)
        self.pia_clamp = FloatBox(0.3, lo=0.0, hi=1.0)
        grid.addWidget(QLabel("pi_f β"), 0, 0)
        grid.addWidget(self.pif_beta, 0, 1)
        grid.addWidget(QLabel("pi_f s0"), 0, 2)
        grid.addWidget(self.pif_s0, 0, 3)
        grid.addWidget(QLabel("pi_f clamp"), 1, 0)
        grid.addWidget(self.pif_clamp, 1, 1)
        grid.addWidget(QLabel("pi_f φ-weight"), 1, 2)
        grid.addWidget(self.pif_phi_weight, 1, 3)
        grid.addWidget(QLabel("pi_a β"), 2, 0)
        grid.addWidget(self.pia_beta, 2, 1)
        grid.addWidget(QLabel("pi_a s0"), 2, 2)
        grid.addWidget(self.pia_s0, 2, 3)
        grid.addWidget(QLabel("pi_a clamp"), 3, 0)
        grid.addWidget(self.pia_clamp, 3, 1)
        return box

    def _reference(self) -> Point2:
        return Point2(float(self.ref_x.value()), float(self.ref_y.value()))

    def _segment_spec(self) -> SegmentSpec:
        return SegmentSpec(
            p0=Point2(float(self.seg_x0.value()), float(self.seg_y0.value())),
            p1=Point2(float(self.seg_x1.value()), float(self.seg_y1.value())),
            ambient_kappa=float(self.seg_kappa.value()),
            samples=int(self.seg_samples.value()),
        )

    def _arc_spec(self) -> ArcSpec:
        return ArcSpec(
            center=Point2(float(self.arc_cx.value()), float(self.arc_cy.value())),
            radius=float(self.arc_r.value()),
            start_deg=float(self.arc_start.value()),
            sweep_deg=float(self.arc_sweep.value()),
            samples=int(self.arc_samples.value()),
        )

    def _pif_params(self) -> PiFParams:
        return PiFParams(
            beta=float(self.pif_beta.value()),
            s0=float(self.pif_s0.value()),
            clamp=float(self.pif_clamp.value()),
            phi_weight=float(self.pif_phi_weight.value()),
        )

    def _pia_params(self) -> PiAParams:
        return PiAParams(
            beta=float(self.pia_beta.value()),
            s0=float(self.pia_s0.value()),
            clamp=float(self.pia_clamp.value()),
        )

    def refresh(self) -> None:
        ref = self._reference()
        seg = self._segment_spec()
        arc = self._arc_spec()
        pif_params = self._pif_params()
        pia_params = self._pia_params()
        rows = build_results(ref, seg, arc, pif_params, pia_params)

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            delta_f = row.pi_f - row.euclidean
            pct_f = 100.0 * delta_f / row.euclidean if abs(row.euclidean) > 1e-12 else 0.0
            pct_a = 100.0 * (row.pi_a - row.euclidean) / row.euclidean if abs(row.euclidean) > 1e-12 else 0.0
            values = [
                row.label,
                f"{row.euclidean:.6f}",
                f"{row.pi_f:.6f}",
                f"{row.pi_a:.6f}",
                f"{delta_f:+.6f}",
                f"{pct_f:+.3f}%",
                f"{pct_a:+.3f}%",
            ]
            for col, text in enumerate(values):
                self.table.setItem(row_index, col, QTableWidgetItem(text))

        euclid_seg = rows[0].euclidean
        ref_pf = pi_f_value(ref, ref, pif_params)
        arc_pf_mid = pi_f_value(
            Point2(
                arc.center.x + arc.radius * math.cos(math.radians(arc.start_deg + 0.5 * arc.sweep_deg)),
                arc.center.y + arc.radius * math.sin(math.radians(arc.start_deg + 0.5 * arc.sweep_deg)),
            ),
            ref,
            pif_params,
        )
        pa_arc = pi_a(kappa=1.0 / max(1e-9, arc.radius), scale=max(1e-9, arc.radius), params=pia_params)
        pa_seg = pi_a(kappa=seg.ambient_kappa, scale=max(euclid_seg, 1e-9), params=pia_params)

        lines = [
            "Metric comparison panel summary",
            "================================",
            f"Reference origin for pi_f field: ({ref.x:.4f}, {ref.y:.4f})",
            "",
            "Interpretation notes:",
            "- Euclidean is the ordinary flat baseline.",
            "- pi_f here is a bounded prototype field, not yet a canonical repo-wide kernel.",
            "- pi_a uses the existing AdaptiveCAD pi_a kernel.",
            "",
            f"Segment Euclidean length: {euclid_seg:.6f}",
            f"Segment pi_a value at ambient κ={seg.ambient_kappa:.6f}: {pa_seg:.6f}",
            f"Arc pi_f value at mid-arc sample: {arc_pf_mid:.6f}",
            f"Arc pi_a value from radius-derived κ=1/r: {pa_arc:.6f}",
            f"pi_f value at the reference origin: {ref_pf:.6f}",
            "",
            "How to read the table:",
            "- Δ pi_f is the absolute change from Euclidean to pi_f.",
            "- % pi_f and % pi_a are percentage changes relative to Euclidean.",
            "- For a straight segment, pi_a will reduce to Euclidean when ambient κ = 0.",
            "- For a circle, pi_a uses κ = 1/r so the metric response is visible immediately.",
            "",
            "Suggested experiments:",
            "1. Move the reference origin away from the geometry and watch pi_f change.",
            "2. Set segment ambient κ=0 to verify pi_a collapses toward Euclidean.",
            "3. Increase radius to test whether pi_a cleanly approaches the ordinary regime.",
            "4. Toggle phi-weight away from zero only as an experiment, not as proof.",
        ]
        self.summary.setPlainText("\n".join(lines))


class MetricComparisonWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AdaptiveCAD Metric Comparison")
        self.resize(1180, 760)
        panel = MetricComparisonPanel(self)
        self.setCentralWidget(panel)


def main() -> int:
    app = QApplication.instance() or QApplication([])
    win = MetricComparisonWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
