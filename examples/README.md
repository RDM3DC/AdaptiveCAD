# Examples

## entanglement_backreaction.py

Prototype numpy simulation that evolves a linear qubit chain and feeds
entanglement back into curvature variables. Five complementary modes are
available:

1. **Gate mode** (default) replays the minimal RXX gate sweep discussed in the
	 chat.
2. **Hamiltonian mode** constructs the full XX-coupled Hamiltonian each step,
	 updates couplings from pairwise entropies, and (optionally) plots history
	 traces.
3. **Phase sweep** maps out how the Hamiltonian system responds across a grid of
	 learning rates/entropy targets, producing both trajectory samples and a heat
	 map of average couplings/instabilities.
4. **Goldilocks sweep** reproduces the connectivity/stability map from the notes
	 (average coupling vs variance) to pinpoint the smooth-yet-connected region.
5. **Stage-two analysis** runs a longer burn-in in the "Goldilocks" regime and
	 compares the emergent graph distances against the mutual-information matrix.

```bash
# original gate-based prototype
python examples/entanglement_backreaction.py --mode gate --steps 200 --n-qubits 6

# Hamiltonian evolution with plotting enabled
python examples/entanglement_backreaction.py --mode hamiltonian --n-qubits 5 --steps 150 --plot-history

# Phase diagram sweep with plotting
python examples/entanglement_backreaction.py --phase-sweep --plot-phase-diagram --plot-sweep-trajectories

# Goldilocks connectivity/stability sweep
python examples/entanglement_backreaction.py --goldilocks-sweep --plot-goldilocks

# Stage-two mutual-information vs geometry analysis
python examples/entanglement_backreaction.py --stage-two --plot-stage-two
```

Useful flags:

- `--entropy-target` controls the desired von Neumann entropy per cut/bond.
- `--eta` sets how fast the curvature variable responds to entropy error.
- `--lambda` and `--theta-gain` tune the gate-mode feedback strengths.
- `--initial-pi` sets the starting coupling for Hamiltonian mode; `--plot-history`
	displays the entropy and curvature traces.
- `--phase-sweep` switches into the multi-run experiment. Combine with
	`--sweep-etas`, `--sweep-targets`, `--sweep-steps`, `--sweep-mu`, and the plot
	toggles to reproduce the stage-1 diagrams shared in chat.
- `--goldilocks-sweep` runs the connectivity/stability grid. Tune it with
	 `--gold-etas`, `--gold-targets`, `--gold-steps`, `--gold-burn`, `--gold-mu`, and
	 `--plot-goldilocks` for the two heatmaps.
- `--stage-two` enables the mutual-information diagnostics. Tune it with
	 `--stage2-eta`, `--stage2-target`, `--stage2-mu`, `--stage2-steps`, `--stage2-pi0`,
	 `--stage2-min-pi`, the `--stage2-distance-*` knobs, `--stage2-info-eps` for the
	 entanglement geodesic, and `--stage2-export-prefix` to dump CSV matrices. Add
	 `--plot-stage-two` for the seaborn heatmaps.

Running with no flags reproduces the baseline numbers from the prototype shared
in chat.

## adaptive_josephson_lattice.py

Phenomenological adaptive Josephson lattice that ties an entanglement-load
proxy to Josephson couplings. The defaults match the "Goldilocks" parameters
from the discussion.

```bash
python examples/adaptive_josephson_lattice.py --size 48 --steps 400 --eta 0.6 --mu 0.1
```

Interesting knobs:

- `--s-target` shifts the desired entanglement load; scan it to see how the toy
	`Tc_proxy` responds.
- `--gamma` controls the `G ~ 1 / S^gamma` scaling in the stiffness proxy.
- `--noise` regulates how turbulent the entanglement proxy becomes.

Outputs are printed to stdout and the full state (maps + histories) can be
captured by importing `run_simulation` in notebooks for deeper analysis.
