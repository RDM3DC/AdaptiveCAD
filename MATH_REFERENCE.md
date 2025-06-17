# AdaptiveCAD Mathematics Reference

This document serves as a reference for the core mathematical concepts and equations used in the AdaptiveCAD project. It's intended to help new developers understand the mathematical foundations of the code.

## Table of Contents

1. [Linear Algebra](#1-linear-algebra-linalgpy)
2. [Curve Geometry](#2-curve-geometry-bezierpy-bsplinepy)
3. [Hyperbolic Geometry](#3-hyperbolic-geometry-hyperbolicpy)
4. [CAM Layer](#4-cam-layer-gcode_generatorpy-readmemd)
5. [Constraint Solver](#5-constraint-solver)
6. [Geodesic Distance & πₐ Metric Kernel](#6-geodesic-distance--πₐ-metric-kernel)
7. [N-Dimensional Geometry](#7-n-dimensional-geometry-for-higher-dimensions)
8. [Symbolic/Automatic Differentiation](#8-symbolicautomatic-differentiation)
9. [Numerics & Solvers](#9-numerics--solvers)
10. [πₐ-aware Cache & History](#10-πₐ-aware-cache--history)

## 1. Linear Algebra (linalg.py)

### Homogeneous Coordinates

$$P_h = (x, y, z, 1)^T, P' = M \cdot P_h, M = \begin{bmatrix} R & t \\ 0 & 1 \end{bmatrix}$$

### Quaternions (rotation)

$$q = (\cos\frac{\theta}{2}, u\sin\frac{\theta}{2}), P' = q P \bar{q}$$

### Polar Decomposition

$$S = M^T M, R = MS^{-1}$$

## 2. Curve Geometry (bezier.py, bspline.py)

### Bezier Curve

$$C(u) = \sum_{i=0}^n B_{i,n}(u) \cdot P_i, B_{i,n}(u) = \binom{n}{i} u^i (1-u)^{n-i}$$

Algorithm: de Casteljau for evaluation and subdivision.

### B-spline Curve

$$C(u) = \sum N_{i,p}(u) P_i$$

Algorithm: de Boor for evaluation, with support for knot vectors and span finding.

### Differential Geometry on Curves

#### Tangent
$$T(u) = C'(u)$$

#### Curvature
$$\kappa(u) = \frac{||C'(u) \times C''(u)||}{||C'(u)||^3}$$

#### Arc length parameterization
$$s(u) = \int_0^u ||C'(t)|| dt$$

### Surface Geometry (Tensor Product NURBS)

#### First fundamental form
$$E = \frac{\partial S}{\partial u} \cdot \frac{\partial S}{\partial u}, \quad F = \frac{\partial S}{\partial u} \cdot \frac{\partial S}{\partial v}, \quad G = \frac{\partial S}{\partial v} \cdot \frac{\partial S}{\partial v}$$

#### Second fundamental form
$$e = \frac{\partial^2 S}{\partial u^2} \cdot N, \quad f = \frac{\partial^2 S}{\partial u \partial v} \cdot N, \quad g = \frac{\partial^2 S}{\partial v^2} \cdot N$$

where $N$ is the unit normal vector.

#### Curvatures
$$K = \frac{eg - f^2}{EG - F^2}, \quad H = \frac{Eg + Ge - 2Ff}{2(EG - F^2)}$$

where $K$ is the Gaussian curvature and $H$ is the mean curvature.

## 3. Hyperbolic Geometry (hyperbolic.py)

### Adaptive π ratio

$$\frac{\pi_a}{\pi} = \frac{\kappa \sinh(r/\kappa)}{r}$$

### Full turn in degrees

$$\text{full\_turn\_deg}(r, \kappa) = \frac{360 \kappa \sinh(r/\kappa)}{r}$$

### Rotation mapping

$$\text{rotate\_cmd}(\Delta\theta_a, r, \kappa) = \frac{\Delta\theta_a}{\text{full\_turn\_deg}(r, \kappa)} \cdot 2\pi$$

## 4. CAM Layer (gcode_generator.py, README.md)

### Effective radius for ball-end mill

$$r_e = \frac{r}{\sin\theta}$$

### Trochoidal chip thickness

$$h = s\cos(\frac{\phi}{2})$$

### Scallop height formula

$$s = \sqrt{8eR - 4e^2}$$

### Z-level roughing & TSP for contour linking
- Traveling Salesman Problem (TSP) for optimal path ordering
- Contour isolation and nesting

### Feed-rate S-curve (jerk-limited)

$$x(t) = x_0 + v_0 t + \frac{1}{2}a_0 t^2 + \frac{1}{6}jt^3$$

### Geodesic-Aware Toolpaths

#### Euclidean offset
$$C_o(u) = C(u) + d \cdot \frac{N(u)}{||N(u)||}$$

#### Geodesic offset
$$C_g(u) = \text{Iso-geodesic contour at } d_g(u)$$

Implementation via PDE solution or fast marching method.

## 5. Constraint Solver

### Non-linear least squares for sketches

$$\min_x \sum f_i(x)^2$$

### Mixed constraint dynamics

$$\begin{bmatrix} M & C^T \\ C & 0 \end{bmatrix} \begin{bmatrix} \ddot{q} \\ \lambda \end{bmatrix} = \begin{bmatrix} b \\ -\dot{C}\dot{q} \end{bmatrix}$$

## 6. Geodesic Distance & πₐ Metric Kernel

### Metric-based distance

$$ds^2 = g_{ij} dx^i dx^j$$

### Geodesic Distance

$$d(p, q) = \int_0^1 \sqrt{ \dot{x}^i g_{ij} \dot{x}^j } \, dt$$

### Constraint-driven curvature update

$$\frac{\partial g_{ij}}{\partial t} = -\alpha \frac{\partial \Phi}{\partial x^i} \frac{\partial \Phi}{\partial x^j}$$

### Geodesic ODE

$$\ddot{x}^k + \Gamma^k_{ij} \dot{x}^i \dot{x}^j = 0 \quad\text{where}\quad \Gamma^k_{ij} = \frac{1}{2} g^{kl} \left( \partial_i g_{jl} + \partial_j g_{il} - \partial_l g_{ij} \right)$$

## 7. N-Dimensional Geometry (for higher dimensions)

### Vector in ℝⁿ (VecN)

$$v = [v_1, v_2, …, v_n]$$

Basic operations:

#### Addition
$$v + w = [v_i + w_i] \text{ for } i=1,…,n$$

#### Scalar multiplication
$$a \cdot v = [a \cdot v_i]$$

#### Dot product
$$v \cdot w = \sum_{i=1}^{n} v_i w_i$$

#### Norm (length)
$$\|v\| = \sqrt{\sum_{i=1}^{n} v_i^2}$$

### Matrix in ℝⁿˣⁿ (MatrixN)

An affine transform in ℝⁿ uses an $(n+1) \times (n+1)$ matrix:

$$M = \begin{bmatrix} R_{n \times n} & t_{n \times 1} \\ 0 \ldots 0 & 1 \end{bmatrix}$$

To transform a point $p \in R^n$:
1. Convert to homogeneous: $p_h = [p_1, ..., p_n, 1]^T$
2. Apply: $p' = M \cdot p_h$

### Generalized Bezier Curve (N-D)

Given control points $P_0, ..., P_n \in R^D$, the Bezier curve is:

$$C(u) = \sum_{i=0}^{n} B_{i,n}(u) \cdot P_i$$

with Bernstein basis:

$$B_{i,n}(u) = \binom{n}{i} u^i (1-u)^{n-i}$$

De Casteljau algorithm works identically in N-D:

Iteratively interpolate between points using:

$$P_i^{(r)} = (1-u)P_i^{(r-1)} + uP_{i+1}^{(r-1)}$$

### Generalized B-spline Curve (N-D)

Given:
- Degree $p$
- Control points $P_0, ..., P_n \in R^D$
- Knot vector $U = [u_0, u_1, ..., u_{n+p+1}]$

Evaluate using de Boor's algorithm (already N-D compatible).

### Geodesics and Metric Tensor in ℝⁿ

#### Distance
$$ds^2 = \sum_{i,j=1}^{n} g_{ij}(x) dx^i dx^j$$

#### Christoffel symbols for geodesics
$$\Gamma^k_{ij} = \frac{1}{2} g^{kl} \left( \frac{\partial g_{jl}}{\partial x^i} + \frac{\partial g_{il}}{\partial x^j} - \frac{\partial g_{ij}}{\partial x^l} \right)$$

#### Geodesic equation (for toolpath planning or curvature-aware modeling)
$$\ddot{x}^k + \Gamma^k_{ij} \dot{x}^i \dot{x}^j = 0$$

## 8. Symbolic/Automatic Differentiation

Essential for πₐ dynamics and constraint systems:

### Derivatives required for πₐ system
- $\frac{\partial g_{ij}}{\partial t}$ - Metric tensor time evolution
- $\frac{\partial \Phi}{\partial x^i}$ - Constraint gradient
- $\nabla\Phi$ - Complete gradient vector
- Hessian$(\Phi)$ - Second derivatives for optimization

### Implementation approaches
- Dual numbers
- Reverse-mode automatic differentiation
- Libraries: autograd, jax
- Symbolic mathematics (e.g., SymPy)

## 9. Numerics & Solvers

### Geodesic integrators
- Runge-Kutta 4 (RK4)
- Symplectic integrator (for energy conservation)

### Matrix solvers
- Cholesky decomposition (for positive-definite matrices)
- LDL$^T$ factorization
- Conjugate Gradient (CG) for large sparse systems

### Root isolation
- Interval arithmetic
- Bernstein bounds

### Metric validation
- Positive-definiteness check of $g_{ij}$
- Eigenvalue computation

## 10. πₐ-aware Cache & History

### Curve/surface evaluation caching
- Position
- Evaluation basis
- Metric tensor at location
- Timestamp

### Memory-aware curves (undo/history, path-tracking)
- Persistent data structures (functional list/tree for curve edits)
- Time-stamped control points + evaluation results
- Hash-based deduplication for curve caches

### Cache invalidation criteria
- Curvature field changes
- Constraint modifications
