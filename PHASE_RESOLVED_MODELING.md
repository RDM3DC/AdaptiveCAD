# Phase-Resolved (PR) modeling framework (AdaptiveCAD)

This document captures the **Phase‑Resolved modeling** concept as a concrete, implementable layer inside AdaptiveCAD.

## Scope (MVP)

- A **Phase‑Resolved point** is represented as Euclidean position plus a phase vector.
- A **Phase field** is represented as a vector field on a discrete lattice (grid) for headless simulation and MCP integration.
- A minimal **PR solver loop** evolves the phase field by:
  - phase diffusion (smoothness / continuity)
  - optional coupling to a scalar “geometry proxy” field (e.g. curvature or density)

This is intentionally not a first‑principles physics solver; it is a controllable computational substrate for research and generative design.

## Core data model

### PR point

A Phase‑Resolved point carries:

- position: $x \in \mathbb{R}^d$
- phase: $\varphi \in \mathbb{R}^n$
- optional adaptive state (history, metadata)

Conceptually:

$$\text{PRPoint} = (x, \varphi, \text{state})$$

### PR field (grid)

For headless experiments, we treat phase as a vector field on a grid:

- phase: $\varphi[i,j] \in \mathbb{R}^n$
- geometry proxy: $g[i,j] \in \mathbb{R}$ (optional)

In the current implementation, $g$ is also the main “universe-like dynamics” control surface:
it is a *synthetic* scalar field (not a first-principles physics result) that can be shaped by
frequency bands and then used as the coupling target for the PR evolution.

## What is $\varphi$? (phase space + invariances)

To be implementable, $\varphi$ must have a declared domain and a declared notion of “difference” $\Delta\varphi$.

We support two MVP phase spaces:

1) **Wrapped phase** (angle-like): $\varphi \in (S^1)^n$.

- Gauge-like invariance: $\varphi \mapsto \varphi + 2\pi k$ is equivalent.
- Only *differences* are physically meaningful unless you add an absolute anchor term.

2) **Unwrapped phase** (vector-like): $\varphi \in \mathbb{R}^n$.

- No wrapping; continuity is enforced by smoothness penalties.
- Absolute values are meaningful (useful for “tracking” a target field).

## PR-Root (⊙√) as an explicit branch rule

In the MVP, PR‑Root is operationalized as a deterministic **branch selection** for angle differences.

Define the principal-branch “wrap to $(-\pi,\pi]$” operator:

$$\operatorname{wrap}(\delta) = ((\delta + \pi) \bmod 2\pi) - \pi$$

Then the **phase-resolved difference** used by energies and updates is:

$$\Delta\varphi_{ij} = \operatorname{wrap}(\varphi_j - \varphi_i)$$

This is the minimal, testable place where “PR‑Root bookkeeping” enters computation: it prevents branch flips from injecting artificial discontinuities.

If you have a canon note (e.g. `202506-phase-resolved-root-pr-root.md`), this is where it plugs in: as the explicit unwrapping / branch rule.

## Energy functional (math-complete MVP)

We use a composite objective that matches your working description:

$$E_{\text{total}} = E_{\text{phase}} + \lambda\,E_{\text{geom}} + \mu\,E_{\text{couple}}$$

### Discrete phase smoothness (Dirichlet / Laplacian)

On a graph or grid with neighbor pairs $(i,j)$ and weights $w_{ij}$:

$$E_{\text{phase}}(\varphi)= \tfrac12\sum_{(i,j)} w_{ij}\,\lVert\Delta\varphi_{ij}\rVert^2$$

Where:

- **Unwrapped**: $\Delta\varphi_{ij}=\varphi_j-\varphi_i$.
- **Wrapped**: $\Delta\varphi_{ij}=\operatorname{wrap}(\varphi_j-\varphi_i)$ applied componentwise.

On a 2D grid with 4-neighborhood and uniform weights, this corresponds to the usual discrete Laplacian update.

### Geometry term (placeholder, but implementable)

In the MVP grid demo, $g[i,j]$ is a scalar “geometry proxy” field. If you want a geometry regularizer, one simple choice is:

$$E_{\text{geom}}(g)=\tfrac12\sum_{(i,j)} w_{ij}(g_j-g_i)^2$$

In most experiments, you can treat $g$ as fixed input (so $E_{\text{geom}}$ is omitted).

## “Tune out frequencies”: spectral geometry proxy

To support “parts that tune out frequencies”, the solver supports two geometry-proxy synthesis modes:

1) `smooth_noise` (legacy): low-frequency noise made by repeated local averaging.
2) `spectral_band`: band-pass filtered noise in Fourier space.

Conceptually, `spectral_band` does:

- draw white noise $\eta(x,y)$
- compute a 2D FFT: $\mathcal{F}[\eta]$
- apply a radial band-pass mask $M(|\mathbf{f}|)$ with edges $(f_{\text{low}}, f_{\text{high}})$
- invert FFT to get $g(x,y)$ and normalize

This gives a clean frequency dial that changes the dominant feature scale:

- lower band → larger structures (slow variations)
- higher band → finer structures (fast variations)

### Implementation mapping (current code)

These knobs are exposed on `PRFieldConfig`:

- `geom_mode`: `smooth_noise` | `spectral_band`
- `geom_smooth_iters`: averaging iterations for `smooth_noise`
- `geom_freq_low`, `geom_freq_high`: band edges (cycles-per-sample radius)
- `geom_freq_power`: within-band shaping (bias)

And through the bridge CLI:

```bash
python apps-sdk/adaptivecad_bridge.py run_pr_and_export_ama \
  --size 96 --steps 200 \
  --geom-mode spectral_band \
  --geom-freq-low 0.02 --geom-freq-high 0.06 --geom-freq-power 1.0 \
  --return path
```

### Coupling term (explicit, testable)

Pick a target map $T(g)$ into phase-space and penalize deviation:

$$E_{\text{couple}}(\varphi,g)=\tfrac12\sum_i \lVert\Delta(\varphi_i, T(g_i))\rVert^2$$

Where:

- **Unwrapped**: $\Delta(\varphi, T)=\varphi-T$.
- **Wrapped**: $\Delta(\varphi, T)=\operatorname{wrap}(\varphi-T)$.

One implementable MVP choice is:

- Unwrapped ($\mathbb{R}^n$): $T(g)= (\alpha g, 0,\dots,0)$.
- Wrapped ($S^1$): $T(g)=\pi\tanh(g)$.

This gives you a concrete “curvature/density-to-phase tracking” pattern without needing mesh curvature yet.

## Solver update rule (discrete time)

For gradient descent / relaxation on $\varphi$:

$$\varphi^{(t+1)}=\varphi^{(t)} + \eta\,\kappa\,\Delta \varphi^{(t)} - \eta\,\mu\,\nabla_{\varphi}E_{\text{couple}}$$

On a grid with uniform weights:

- $\Delta$ is the discrete Laplacian.
- $\kappa$ is the diffusion strength.
- $\eta$ is a timestep / stepsize.

For the coupling term above, the per-site descent direction is:

- **Unwrapped**: $\nabla_{\varphi_i}E_{\text{couple}}=\varphi_i-T(g_i)$.
- **Wrapped**: use $\operatorname{wrap}(\varphi_i-T(g_i))$.

After each step in wrapped mode, re-wrap $\varphi$ into $(-\pi,\pi]$.

## Convergence / stopping (MVP)

Any of these is sufficient for v0:

- Energy decrease: $|E^{(t+1)}-E^{(t)}|<\epsilon$
- Step norm: $\lVert\varphi^{(t+1)}-\varphi^{(t)}\rVert < \epsilon$
- Max iterations

- $E_{\text{phase}}$: phase smoothness (penalize gradients)
- $E_{\text{geom}}$: optional “geometry proxy” regularization
- $E_{\text{couple}}$: phase alignment with the proxy (e.g. prefer larger phase magnitude where proxy is high)

## Solver semantics

A minimal iterative evolution loop:

1. Compute wrapped/unwrapped differences
2. Accumulate Laplacian-like diffusion update
3. Apply coupling descent step
4. Track metrics (energy components, coherence proxy)

This supports:

- **dynamic relaxation** (converge to stable field)
- **phase-driven deformation hooks** (later: map phase changes back into geometry)

## Planned extensions (non-MVP)

- Attach PR fields directly to meshes (vertices/faces) and drive mesh relaxation.
- Add constraint terms compatible with `adaptivecad.sketch.core.solver.ConstraintSolver`.
- Replace the simple coupling term with rule sets (diffusion, gradient alignment, constraint stabilization).

## Where the code lives

- `adaptivecad/pr/` — PR data structures + solver
- `adaptivecad/pr/types.py` — configuration (including frequency tuning knobs)
- `adaptivecad/pr/solver.py` — relaxation loop + geometry-proxy synthesis
- `examples/pr_phase_relax_demo.py` — headless demo
- `apps-sdk/` — MCP tool wrappers (so ChatGPT can run PR solvers)

## From PR dynamics to a 3D model (current pipeline)

Today, the “3D model from PR-Root dynamics” pipeline is:

1) run PR relaxation to obtain a scalar field (typically $\varphi[:,:,0]$)
2) export as:
  - `.ama` (preferred): contains the field + analytic layer metadata for the analytic viewer
  - STL heightmap: a physical mesh derived from the scalar field

The `.ama` export includes multiple diagnostic/derived layers so you can inspect what the
system is doing (gradient magnitude, Laplacian, curvature proxy, smoothed field, falsifier residual).
