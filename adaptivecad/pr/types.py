from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass(frozen=True)
class PRFieldConfig:
    """Configuration for a grid-based Phase‑Resolved field."""

    size: int = 64
    steps: int = 200
    dt: float = 0.15
    diffusion: float = 0.35
    coupling: float = 0.25
    coupling_mode: Literal["none", "geom_target"] = "geom_target"

    # --- "Universe dynamics" knobs (geometry target synthesis) ---
    # smooth_noise: low-frequency noise via repeated averaging (legacy behavior)
    # spectral_band: band-pass filtered noise in Fourier space (frequency tuning)
    geom_mode: Literal["smooth_noise", "spectral_band"] = "smooth_noise"
    geom_smooth_iters: int = 6
    # Band edges are in cycles-per-sample radius, in [0.0 .. ~0.707].
    # (Nyquist along axis is 0.5; radial max is sqrt(0.5^2+0.5^2)).
    geom_freq_low: float = 0.02
    geom_freq_high: float = 0.12
    # Emphasize higher or lower frequencies inside the band.
    geom_freq_power: float = 1.0
    phase_dim: int = 2
    phase_space: Literal["unwrapped", "wrapped"] = "unwrapped"
    seed: int | None = 0


@dataclass
class PRFieldState:
    """State for a grid-based Phase‑Resolved field."""

    phi: np.ndarray  # (N,N,phase_dim)
    geom: np.ndarray  # (N,N) scalar geometry proxy
    falsifier_residual: np.ndarray | None = None  # (N,N) plaquette holonomy/branch residual


__all__ = ["PRFieldConfig", "PRFieldState"]
