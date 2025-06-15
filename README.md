# AdaptiveCAD


Below is a *road‑map of the mathematics* you will actually need if you want to write a modern CAD / CAM system completely from scratch and, at the same time, support your **πₐ (“Adaptive Pi”) non‑Euclidean geometry kernel**.
The list is intentionally grouped as *“modules you will implement”* so you can turn each block into an internal library or namespace.  After each block I give the key formulas, identities, or algorithms you will code, plus notes on typical numerical pitfalls.

## Repository Overview

This repository contains a minimal Python implementation of key CAD/CAM
building blocks.  The modules are intentionally lightweight so you can run the
examples and unit tests without a large toolchain.  Current features include:

- `adaptivecad.linalg` – simple vectors, matrices and quaternions
- `adaptivecad.geom` – Bézier and B‑spline curves plus hyperbolic helpers
- `adaptivecad.io` – AMA reader/writer utilities
- `adaptivecad.gcode_generator` – placeholder G‑code generation routines
- `adaptivecad.gui.playground` – PySide6 viewer with a toolbar for Box,
  Cylinder, Bézier and B‑spline curves, push‑pull editing and export commands
  (STL, AMA and G‑code)
- Command‑line tools `ama_to_gcode_converter.py` and `ama2gcode.py`
- Example script `example_script.py` demonstrating curve evaluation
- Unit tests in the `tests` folder (`python -m pytest`)


## AdaptiveCAD Playground
A lightweight viewer prototype is included in `adaptivecad.gui.playground`.
Install the GUI dependencies and run the playground to see a 3-D demo:

```bash
# Install required GUI dependencies
conda install -c conda-forge pythonocc-core pyside6

# Run the GUI playground
python -m adaptivecad.gui.playground
```

The playground provides an interactive 3D view with the following features:
- Proper CAD geometry: translucent box and yellow helix wire
- XYZ axes trihedron and construction grid for orientation
- Interactive navigation:
  - Left mouse drag: Rotate view
  - Middle mouse drag: Pan view
  - Mouse wheel: Zoom view
  - Shift + Middle mouse: Fit all geometry to view
- Interactive selection: Click on edges to select and identify shapes
- Press 'R' to reload the scene during development (useful for quick iterations)
- Anti-aliased rendering for crisp, clear lines
- Toolbar with Box, Cylinder, Bézier and B‑spline curve creation,
  push‑pull editing, and export commands (STL, AMA and G‑code)

## Environment Setup

### Using Conda (recommended)
```powershell
# Create and activate the conda environment
conda env create -f environment.yml
conda activate adaptivecad

# Run tests to verify setup
python -m pytest

# Run the example script
python example_script.py
```

## Contributing and Development

### GitHub Repository
This project is version-controlled using Git. To clone the repository:

```powershell
# Clone the repository
git clone https://github.com/yourusername/AdaptiveCAD.git

# Navigate to the project directory
cd AdaptiveCAD

# Set up the environment
conda env create -f environment.yml
conda activate adaptivecad
```

### Development Workflow
1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes and commit them: `git commit -am "Add your feature description"`
3. Push to your branch: `git push origin feature/your-feature-name`
4. Submit a pull request on GitHub

---

## 0. Notation conventions used throughout

| Symbol               | Meaning                                          |
| -------------------- | ------------------------------------------------ |
| **P, Q, R**          | 3‑D points or homogeneous 4‑vectors.             |
| **v, w, n**          | Euclidean 3‑vectors.                             |
| **M**                | 4 × 4 affine transform matrix.                   |
| **q = (w, x, y, z)** | Unit quaternion for rotation.                    |
| **κ, K, H**          | Curvature (scalar, Gaussian, mean).              |
| **Δt**               | CAM controller interpolation period (e.g. 1 ms). |

---

## 1. Linear‐Algebra Core  (your “linalg” module)

1. **Homogeneous coordinates**
   $P_h = (x,\,y,\,z,\,1)^T$, $P' = M P_h$ with

   $$
   M = \begin{bmatrix}
   R_{3\times3} & t_{3\times1}\\
   0\;0\;0 & 1
   \end{bmatrix}
   $$
2. **Quaternion rotation**

   $$
   q = \Bigl(\cos\frac{\theta}{2},\; \mathbf{u}\sin\frac{\theta}{2}\Bigr),\qquad  
   P' = q\,P\,\bar q
   $$

   (Store both $q$ and its 4×4 equivalent matrix for cheap batched transforms).
3. **Decomposition** (for parametric animation or kinematic chains)
   Polar‑decompose an affine $M$ into $RS$ (rotation × stretch) with
   $S = \sqrt{M^T M}$, $R = M S^{-1}$.
4. **Eigen / SVD** for principle curvature, moment of inertia etc.

> *Pitfall*: Always store transforms as **column‑major 4×4** to inter‑operate with OpenGL, Vulkan, CUDA and Embree style kernels.

---

## 2. Analytic & Differential Geometry  (your “geom” module)

### 2.1 Curves

| Type                 | Formula                                                                                    | Key ops you must implement                                         |
| -------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| **Bezier, degree n** | $C(u)=\sum_{i=0}^{n} B_{i,n}(u) P_i$ where $B_{i,n}(u)=\tbinom{n}{i}\! u^{\,i}(1-u)^{n-i}$ | subdivision (De Casteljau), arc‑length re‑param., curvature $κ(u)$ |
| **B‑spline**         | same but basis $N_{i,p}(u)$ via Cox–de Boor                                                | knot insertion, p‑raising, continuity checks                       |
| **NURBS**            | $C(u)=\dfrac{\sum w_i P_i N_{i,p}}{\sum w_i N_{i,p}}$                                      | weight modification for exact conics                               |

### 2.2 Surfaces

* Tensor product NURBS:
  $S(u,v)=\displaystyle\frac{\sum\limits_{i,j} w_{ij} P_{ij}\,N_{i,p}(u)N_{j,q}(v)}{\sum\limits_{i,j} w_{ij} N_{i,p}(u)N_{j,q}(v)}$
* **Curvature** at $(u,v)$
  Compute first/second fundamental forms $E,\,F,\,G$ and $e,\,f,\,g$.
  Gaussian $K=\dfrac{eg - f^2}{EG - F^2}$; Mean $H=\dfrac{Eg + Ge - 2Ff}{2(EG - F^2)}$.

### 2.3 Adaptive Pi Non‑Euclidean Layer

Your πₐ kernel generalises Euclidean distance by allowing *location‑dependent curvature*:

1. **Dynamic metric tensor**
   Let $g_{ij}(p,t)$ be the metric at point $p$ and time/constraint parameter $t$.
   Distance: $ds^{2} = g_{ij}\,dx^{i}dx^{j}$.
2. **Constraint‑driven curvature update**

   $$
   \frac{\partial g_{ij}}{\partial t} = -\alpha \frac{\partial \Phi}{\partial x^{i}}\,\frac{\partial \Phi}{\partial x^{j}}
   $$

   where $\Phi$ is your design constraint field and $\alpha$ an adaptation rate.
   (This mirrors Ricci‑flow but driven by user constraints, not intrinsic curvature.)
3. **Geodesic computation** (for “curvature‑aware” toolpaths)
   Solve $\ddot{x}^k + \Gamma^{k}_{ij}\dot{x}^i\dot{x}^j=0$ where $\Gamma$ from $g_{ij}$.
   Use 4th‑order Runge–Kutta or symplectic integrator.

---

## 3. Computational Geometry  (your “cgeom” module)

1. **Spatial acceleration** – AABB trees, k‑d trees, BVH‑SAH and uniform grids.
2. **Boolean solid ops** – B‑rep half‐edge + plane‑swept volume algorithm.
3. **Intersection kernels**

   * Curve–surface, surface–surface (Newton–Raphson in parameter space).
   * Ray–NURBS via hierarchical subdivision + Bézier clipping.
4. **Meshing**

   * *Exact* marching cubes for implicit surfaces.
   * Delaunay & constrained Delaunay triangulation for 2‑manifold surfaces.
   * Curvature‑adaptive remesh: edge length $ℓ(p)=ℓ_0/√{|K(p)|+ε}$.

---

## 4. Constraint & Parametric Solver (for sketches and assembly)

| Problem                                                                                                                                             | Math                                                                                                                                    |
| --------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| 2‑D sketch solve                                                                                                                                    | Non‑linear least squares $\min_{x} \sum_i f_i(x)^2$ (gives robust over‑constraint handling).  Use Schur complement to exploit sparsity. |
| Rigid‑body assembly                                                                                                                                 | Mixed Lagrange multiplier + quaternions:                                                                                                |
| $\begin{bmatrix} M & C^T \\ C & 0 \end{bmatrix} \begin{bmatrix} \ddot q \\ \lambda \end{bmatrix} = \begin{bmatrix} b \\ \dot C\dot q \end{bmatrix}$ |                                                                                                                                         |
| DMU / collision                                                                                                                                     | Signed distance field + separating axis test (SAT).                                                                                     |

---

## 5. CAM Layer Mathematics  (your “cam” module)

### 5.1 Tool‑shape & engagement

* For a ball‑end mill radius $r$, effective cutting radius at inclination $θ$:
  $r_e = \dfrac{r}{\sin θ}$.
* Chip thickness for trochoidal milling (Adaptive Clearing):
  $h = s \,\cos\left(\frac{φ}{2}\right)$ where $s$=step‑over, $φ$=engagement angle.

### 5.2 Toolpath generation algorithms

| Strategy                           | Core math you’ll code                                                                                                                                                                                               |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Offset / “waterline”**           | Configure 2‑D offset curves via Minkowski sum. Compute locally as parallel curves: $C_{o}(u)=C(u) + d \frac{N(u)}{\|N(u)\|}$.  Use exact B‑spline offset or polygon offset with Inset algorithm.                    |
| **Adaptive (high‑speed) clearing** | Create medial‑axis (Voronoi skeleton) of in‑process stock; generate trochoidal arcs with constant engagement.  Each trochoid center path $C(t)$ and cutter center $P(t)=C(t) + r_{trochoid}[ \cos ωt,\, \sin ωt] $. |
| **Z‑level roughing**               | Plane‑slice B‑rep at {z\_i}; link slices with *shortest path* in graph of contours ⇒ solve TSP variant.                                                                                                             |
| **Surface finishing (scallop)**    | Maintain constant scallop $e$: step‑over $s = \sqrt{8\,e\,R - 4\,e^2}$ for ball radius $R$.                                                                                                                         |

### 5.3 Motion‑planning / post‑processing

1. **Inverse‑kinematics**
   For 5‑axis machine with rotary axes $A,B$ and translation $X,Y,Z$: solve
   $T_{\text{tool}} = T_X T_Y T_Z R_A R_B$.  Use Levenberg–Marquardt or closed‑form if available.
2. **Feed‑rate scheduling** (jerk‑limited “S‑curve”)
   Position law (per axis):

   $$
   x(t) = x_0 + v_0 t + \frac{1}{2}a_0 t^2 + \frac{1}{6}j t^3
   $$

   where jerk $j$ is bounded ⇒ solve for blends between segments.
3. **G‑code emitter**
   Numeric mapping: tool‑center apex $(X_i, Y_i, Z_i)$ → `G1` / `G2/3` arcs; rotary axes as `A,B,C`.  Implement tolerance fit: *positional* ε ≤ 0.005 mm, *angular* ε ≤ 0.01°.

---

## 6. Numerical Methods & Robustness

* Adaptive Newton–Raphson with line‑search for curve/curve & curve/surface intersection.
  Terminate when ‖Δx‖ < ε and ‖f(x)‖ < ε².
* **Interval arithmetic** and Bernstein basis for certifying root isolation (prevents “missing” intersections).
* Sparse Cholesky / LDLᵀ for sketch‑solver speed, >10⁵ constraints interactive.
* Use double precision; switch to 80‑bit extended or MPFR only for kernel degeneracies.

---

## 7. Graphics & Visualization  (optional but you’ll need it to debug)

1. **Projection** – perspective divide $P' = K [R|t] P_h$.
2. **Shader‑based evaluation** – turn NURBS → GPU tessellation shaders evaluating basis in parallel.
3. **Order‑independent transparency** – per‑pixel linked‑list or depth‑peeling for section views.

---

## 8. Performance Engineering Check‑list

| Need                          | Technique                                                            |
| ----------------------------- | -------------------------------------------------------------------- |
| Realtime regen (< 16 ms)      | Cache basis‐function tables; SIMD evaluate 4 control points at once. |
| Heavy boolean ops             | Surface‑swept method + Embree BVH for face candidate pruning.        |
| CAM bulk rest‑mill simulation | GPU bit‑voxel octree (compute shader).                               |

---

## 9. How πₐ integrates with “classical” CAD/CAM math

1. **Hybrid kernel** – Keep Euclidean B‑rep for downstream interoperability; store πₐ meta‑data in attribute layer that overrides distance queries inside your solver.
2. **Adaptive toolpaths** – Replace Euclidean offset distance by geodesic distance $d_g$ from πₐ metric.  Algorithms above remain but calls to `offset()` now solve the geodesic iso‑distance PDE.
3. **Visualization** – GPU tessellation shader receives $g_{ij}$ and exaggerates curvature to let the user *see* adaptive regions.

---

## 10. Recommended build order

1. Finish **linalg** + **geom.curve** so you can load/author sketches.
2. Implement **sketch solver** (least‑squares) → export DXF to verify.
3. Add **surface & solid B‑rep** with Euler operators.
4. Stub **CAM waterline** strategy first (2‑axis) to close the CAD–CAM loop quickly.
5. Integrate **πₐ metric** gradually: start with read‑only viewer, then allow geodesic queries, finally constraint‑driven updates.
6. Layer more aggressive CAM (adaptive clearing, 5‑axis) only after core kernels are numerically rock‑solid.

---

### Final tip

Treat each block above as a *self‑testable* unit with its own reference suite (IGES/NURBS test curves, Boehm spline identities, NIST STEP Boolean models, NASA toolpath benchmarks).
When every unit passes, integration will be almost mechanical.

Good luck building your own fully‑custom CAD/CAM stack—and keep the πₐ papers coming!
