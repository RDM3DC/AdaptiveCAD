# Navier–Stokes research and AdaptiveCAD: bounded scope assessment

Date: September 10, 2026.

## Source result

OpenAI's September 8 announcement and *Finite time blowup for Navier–Stokes* report a smooth-forcing construction with initially resting fluid, bounded kinetic energy and unbounded velocity in finite time. The stated Navier–Stokes result is forced; it is not a new general-purpose numerical flow solver. The accompanying repository contains Lean formalizations. We have not independently rebuilt or audited the full formal proof.

Primary sources:
- https://openai.com/index/navier-stokes-solution/
- https://cdn.openai.com/pdf/32d9f210-8b73-45e0-91bc-82a30aef8a9a/navier-stokes.pdf (Theorem 1.1; Section 2)
- https://github.com/openai/NavierStokesAndEuler

## Useful inference, not a CAD theorem from that paper

Controlling an integral or average does not by itself control a local maximum. The CAD analogue worth checking is whether a patch with ordinary total area and curvature still has a highly sensitive parameter-to-model map. Singular-value conditioning is established numerical geometry, not mathematics newly invented by this project or imported as a consequence of the Navier–Stokes proof.

## Implemented experiment

Run from this branch:

```sh
python -m examples.metric_conditioning_probe
python -m pytest -q --noconftest tests/test_metric_conditioning_probe.py
```

The example uses the existing native `Surface.jet` evaluator, not triangle meshes. At a specified parameter point it measures J = [S_u S_v], maximum and minimum stretch, the singular-value ratio of J, and its square (the condition number of J^T J).

The analytic control is S_e(u,v) = (e*u, v/e, 0), for u,v in [0,1]. Every example is a valid flat rectangle of area one and zero Gaussian curvature. Nonetheless:

| e | Area | Gaussian curvature | Jacobian condition | Metric condition |
|---|---:|---:|---:|---:|
| 1 | 1 | 0 | 1 | 1 |
| 0.1 | 1 | 0 | 100 | 10,000 |
| 0.01 | 1 | 0 | 10,000 | 100,000,000 |
| 0.0001 | 1 | 0 | 100,000,000 | 10^16 |

These values are numerical experiments and also follow from the diagonal Gram matrix diag(e^2,e^-2). The 29 test cases cover this analytic control, rigid rotations, uniform unit changes, independent NumPy singular values, degenerate derivatives, input validation and finite result handling. Local execution passed all 29 before publication; repository CI results are tracked separately.

## Recommended eventual integration

For future curved-face mapping, surface inversions, and directional refinement, expose minimum/maximum stretch with the declared parameter scales alongside curvature and area. Do not use one averaged Adaptive-pi number as a full quality certificate. Use local coordinate rescaling where appropriate, then compare residuals and error budgets in consistent units. Whole-patch claims additionally require adaptive coverage or analytic/interval bounds; a finite set of samples is not a proof.

The current explicit curve-transfer operation uses perpendicular plane axes and uniform unit conversion. This experiment does not identify a conditioning defect in that map. It prepares a diagnostic for the more general surface-to-chart integration that is not yet implemented.

## Limits

- Conditioning depends on parameterization; it is invariant under rigid spatial rotations and uniform length-unit conversion, not arbitrary parameter rescaling.
- Large conditioning does not make a skinny rectangle invalid or prove an operation fails. It indicates potential sensitivity for calculations using that parameterization.
- This diagnostic observes one point, does not mutate geometry, and is not an automatic rejection gate.
- `degenerate_or_unresolved` deliberately combines rank loss and floating-point underflow; the code cannot certify which occurred in every extreme input.
- No CAD booleans, face attachment, surface unwrapping, globally shortest paths, fluid simulation, manufacturing output, or physical Adaptive-pi law is established by this example.
- A formal proof of a fluid theorem does not automatically verify CAD source code. The transferable practice is to specify and independently check the CAD invariants we actually rely on.
