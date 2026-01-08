#!/usr/bin/env python3
"""PR-Root Vibration Simulator CLI

End-to-end vibration testing for analytic SDF geometry.
No OCC dependency. Uses mass-spring lattice approximation.

Examples:
    # Modal analysis only
    python pr_vibe_sim.py modal --ama square_tube_gyroid.ama --out modes.json

    # Compare baseline vs candidate
    python pr_vibe_sim.py compare --baseline plain_tube.ama --candidate gyroid_tube.ama --out comparison.json

    # Full report with plots
    python pr_vibe_sim.py compare --baseline plain_tube.ama --candidate gyroid_tube.ama --out report.json --plot

    # Export Manim-ready data
    python pr_vibe_sim.py manim --baseline plain_tube.ama --candidate gyroid_tube.ama --out manim_data.json

Math Summary (for Manim):
=========================
1. Voxelize SDF: sample analytic scene on grid, solid where SDF < 0
2. Build mass-spring lattice:
   - Each solid voxel = node with mass m = ρ·h³
   - Springs connect 26-neighbors with axial stiffness k = E·h²/L
3. Modal analysis:
   - Solve: K·φ = ω²·M·φ
   - Natural frequencies: f = ω / (2π)
4. Forced response at frequency f:
   - Solve: [(1 + iη)K - ω²M]·u = F
   - Transmissibility: T(f) = RMS(u_out) / RMS(u_in)
5. Comparison:
   - ΔdB(f) = 20·log₁₀(T_candidate / T_baseline)
   - Negative = attenuation (geometry reduces vibration)
   - Positive = amplification (geometry makes it worse)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

# Allow running without installing package
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def cmd_modal(args):
    """Run modal analysis."""
    from adaptivecad.sim import run_modal_analysis, VibrationTestConfig
    from adaptivecad.sim.materials import PLA, ABS, PETG, TPU, STEEL, ALUMINUM

    materials = {"PLA": PLA, "ABS": ABS, "PETG": PETG, "TPU": TPU, "STEEL": STEEL, "ALUMINUM": ALUMINUM}
    mat = materials.get(args.material.upper(), PLA)

    config = VibrationTestConfig(
        extent=args.extent,
        resolution=args.res,
        material=mat,
        num_modes=args.modes,
        f_min_hz=args.f0,
        f_max_hz=args.f1,
        n_freq=args.nfreq,
        loss_factor=args.eta,
    )

    print(f"[pr_vibe_sim] Modal analysis: {args.ama}")
    print(f"  Material: {mat.name}, E={mat.youngs_modulus/1e9:.2f} GPa, ρ={mat.density:.0f} kg/m³")
    print(f"  Resolution: {args.res}³, Extent: ±{args.extent}")

    result = run_modal_analysis(args.ama, config)

    print(f"\n[Results]")
    print(f"  Solid voxels: {result.n_solid_voxels}")
    print(f"  Free nodes: {result.n_free_nodes}")
    print(f"  Rigid body modes detected: {result.modal.n_rigid}")
    print(f"\n  Natural frequencies (Hz):")
    for i, f in enumerate(result.modal.frequencies_hz):
        print(f"    Mode {i+1}: {f:.2f} Hz")

    if args.out:
        result.save_json(args.out)
        print(f"\n  Saved to: {args.out}")

    return result


def cmd_compare(args):
    """Compare baseline vs candidate."""
    from adaptivecad.sim import run_vibration_comparison, VibrationTestConfig
    from adaptivecad.sim.materials import PLA, ABS, PETG, TPU, STEEL, ALUMINUM

    materials = {"PLA": PLA, "ABS": ABS, "PETG": PETG, "TPU": TPU, "STEEL": STEEL, "ALUMINUM": ALUMINUM}
    mat = materials.get(args.material.upper(), PLA)

    config = VibrationTestConfig(
        extent=args.extent,
        resolution=args.res,
        material=mat,
        num_modes=args.modes,
        f_min_hz=args.f0,
        f_max_hz=args.f1,
        n_freq=args.nfreq,
        loss_factor=args.eta,
    )

    print(f"[pr_vibe_sim] Vibration comparison")
    print(f"  Baseline:  {args.baseline}")
    print(f"  Candidate: {args.candidate}")
    print(f"  Material: {mat.name}, E={mat.youngs_modulus/1e9:.2f} GPa")
    print(f"  Frequency sweep: {args.f0}–{args.f1} Hz ({args.nfreq} points)")

    baseline_result, candidate_result = run_vibration_comparison(
        args.baseline, args.candidate, config
    )

    comp = candidate_result.comparison
    print(f"\n[Comparison Results]")
    print(f"  Best attenuation:   {comp.best_attenuation_dB:.2f} dB at {comp.best_attenuation_hz:.1f} Hz")
    print(f"  Worst amplification: {comp.worst_amplification_dB:.2f} dB at {comp.worst_amplification_hz:.1f} Hz")

    # Summary statistics
    delta = comp.delta_dB
    n_atten = int(np.sum(delta < -3.0))  # >3dB attenuation
    n_amp = int(np.sum(delta > 3.0))     # >3dB amplification
    print(f"\n  Frequency bins with >3dB attenuation: {n_atten}/{len(delta)}")
    print(f"  Frequency bins with >3dB amplification: {n_amp}/{len(delta)}")

    if args.out:
        candidate_result.save_json(args.out)
        print(f"\n  Saved to: {args.out}")

    if args.out_csv:
        # Export CSV for easy plotting
        with open(args.out_csv, "w") as f:
            f.write("freq_hz,T_baseline,T_candidate,delta_dB\n")
            for i in range(len(comp.frequencies_hz)):
                f.write(f"{comp.frequencies_hz[i]:.2f},{comp.baseline_T[i]:.6e},{comp.candidate_T[i]:.6e},{comp.delta_dB[i]:.2f}\n")
        print(f"  CSV saved to: {args.out_csv}")

    if args.plot:
        _plot_comparison(comp, baseline_result, candidate_result, args)

    return baseline_result, candidate_result


def _plot_comparison(comp, baseline, candidate, args):
    """Generate comparison plot."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [warning] matplotlib not available, skipping plot")
        return

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # Top: Transmissibility
    ax1 = axes[0]
    ax1.semilogy(comp.frequencies_hz, comp.baseline_T, "b-", label="Baseline (plain tube)", linewidth=1.5)
    ax1.semilogy(comp.frequencies_hz, comp.candidate_T, "r--", label="Candidate (gyroid tube)", linewidth=1.5)
    ax1.set_ylabel("Transmissibility T(f)")
    ax1.set_title("Vibration Transmissibility: Baseline vs Gyroid Tube")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Bottom: Delta dB
    ax2 = axes[1]
    ax2.fill_between(comp.frequencies_hz, comp.delta_dB, 0,
                     where=comp.delta_dB < 0, color="green", alpha=0.4, label="Attenuation")
    ax2.fill_between(comp.frequencies_hz, comp.delta_dB, 0,
                     where=comp.delta_dB > 0, color="red", alpha=0.4, label="Amplification")
    ax2.axhline(0, color="k", linewidth=0.5)
    ax2.axhline(-3, color="green", linestyle="--", linewidth=0.5, label="-3dB threshold")
    ax2.axhline(+3, color="red", linestyle="--", linewidth=0.5, label="+3dB threshold")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("ΔdB = 20·log₁₀(T_cand/T_base)")
    ax2.set_title(f"Vibration Reduction: Best={comp.best_attenuation_dB:.1f}dB @ {comp.best_attenuation_hz:.0f}Hz")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    plot_path = args.out.replace(".json", ".png") if args.out else "vibe_comparison.png"
    plt.savefig(plot_path, dpi=150)
    print(f"  Plot saved to: {plot_path}")
    plt.close()


def cmd_manim_export(args):
    """Export data formatted for Manim animation."""
    from adaptivecad.sim import run_vibration_comparison, VibrationTestConfig
    from adaptivecad.sim.materials import PLA

    config = VibrationTestConfig(
        extent=args.extent,
        resolution=args.res,
        material=PLA,
        f_min_hz=args.f0,
        f_max_hz=args.f1,
        n_freq=args.nfreq,
    )

    print(f"[pr_vibe_sim] Manim data export")
    print(f"  Baseline:  {args.baseline}")
    print(f"  Candidate: {args.candidate}")

    baseline_result, candidate_result = run_vibration_comparison(
        args.baseline, args.candidate, config
    )

    comp = candidate_result.comparison

    # Manim-friendly export
    manim_data = {
        "title": "PR-Root Vibration Simulator",
        "subtitle": "Does the gyroid geometry reduce vibrations?",
        "material": {
            "name": "PLA",
            "youngs_modulus_GPa": 3.5,
            "density_kg_m3": 1240,
        },
        "math": {
            "mass_spring_eq": "m_i = ρ·h³, k_{ij} = E·h²/L_{ij}",
            "modal_eq": "K·φ = ω²·M·φ → f = ω/(2π)",
            "forced_eq": "[(1+iη)K - ω²M]·u = F",
            "transmissibility_eq": "T(f) = RMS(u_out) / RMS(u_in)",
            "comparison_eq": "ΔdB = 20·log₁₀(T_candidate / T_baseline)",
        },
        "baseline": {
            "path": str(args.baseline),
            "modal_frequencies_hz": baseline_result.modal.frequencies_hz.tolist(),
            "n_solid_voxels": baseline_result.n_solid_voxels,
            "n_free_nodes": baseline_result.n_free_nodes,
        },
        "candidate": {
            "path": str(args.candidate),
            "modal_frequencies_hz": candidate_result.modal.frequencies_hz.tolist(),
            "n_solid_voxels": candidate_result.n_solid_voxels,
            "n_free_nodes": candidate_result.n_free_nodes,
        },
        "comparison": {
            "frequencies_hz": comp.frequencies_hz.tolist(),
            "baseline_T": comp.baseline_T.tolist(),
            "candidate_T": comp.candidate_T.tolist(),
            "delta_dB": comp.delta_dB.tolist(),
            "best_attenuation": {
                "dB": comp.best_attenuation_dB,
                "hz": comp.best_attenuation_hz,
            },
            "worst_amplification": {
                "dB": comp.worst_amplification_dB,
                "hz": comp.worst_amplification_hz,
            },
        },
        "conclusion": (
            f"The gyroid geometry provides up to {abs(comp.best_attenuation_dB):.1f} dB "
            f"vibration reduction at {comp.best_attenuation_hz:.0f} Hz, "
            f"but amplifies vibrations by {comp.worst_amplification_dB:.1f} dB "
            f"at {comp.worst_amplification_hz:.0f} Hz."
        ),
    }

    out_path = args.out or "manim_vibe_data.json"
    with open(out_path, "w") as f:
        json.dump(manim_data, f, indent=2)

    print(f"\n  Manim data exported to: {out_path}")
    print(f"\nConclusion: {manim_data['conclusion']}")


def cmd_heat(args):
    """Compute heat generation from vibration damping."""
    from adaptivecad.sim import VibrationTestConfig, load_and_voxelize_ama, build_lattice_system
    from adaptivecad.sim.materials import MATERIALS, PLA
    from adaptivecad.sim.heat_generation import compute_heat_sweep, compare_heat_generation

    mat = MATERIALS.get(args.material.upper(), PLA)
    
    print(f"[pr_vibe_sim] Heat generation analysis")
    print(f"  Material: {mat.name}, E={mat.youngs_modulus/1e9:.2f} GPa, η={getattr(mat, 'loss_factor', 0.05):.3f}")
    print(f"  Frequency sweep: {args.f0}–{args.f1} Hz ({args.nfreq} points)")
    print(f"  Force amplitude: {args.force} N")

    freq_hz = np.linspace(args.f0, args.f1, args.nfreq)

    def analyze_ama(ama_path):
        """Load, voxelize, build lattice, and compute heat sweep."""
        solid, dist, voxel_size, scene = load_and_voxelize_ama(
            ama_path, extent=args.extent, resolution=args.res, iso=0.0
        )
        
        # Build clamp mask (bottom 5%)
        clamp = np.zeros_like(solid, dtype=bool)
        z_indices = np.where(solid)[2]
        if len(z_indices) > 0:
            z_min = z_indices.min()
            z_max = z_indices.max()
            z_range = z_max - z_min + 1
            clamp_height = int(0.05 * z_range) + 1
            clamp[:, :, z_min:z_min + clamp_height] = True
        
        system = build_lattice_system(
            solid, voxel_size=voxel_size, material=mat,
            clamp_mask=clamp, neighbor_mode="26"
        )
        
        result = compute_heat_sweep(
            system, freq_hz=freq_hz, material=mat,
            input_z_frac=0.1, force_amplitude=args.force
        )
        return result, system.n_nodes, int(solid.sum())

    # Single AMA analysis
    if args.ama and not (args.baseline or args.candidate):
        print(f"\n  Analyzing: {args.ama}")
        result, n_nodes, n_voxels = analyze_ama(args.ama)
        
        print(f"\n[Results]")
        print(f"  Solid voxels: {n_voxels}, Free nodes: {n_nodes}")
        print(f"  Peak heat generation: {result.peak_power_watts:.6e} W at {result.peak_frequency_hz:.1f} Hz")
        print(f"  Avg efficiency: {np.mean(result.efficiency)*100:.1f}%")
        
        # Find top 5 heating frequencies
        top_idx = np.argsort(result.total_power_watts)[-5:][::-1]
        print(f"\n  Top 5 heating frequencies:")
        for i, idx in enumerate(top_idx):
            print(f"    {i+1}. {result.frequencies_hz[idx]:.1f} Hz → {result.total_power_watts[idx]:.6e} W")
        
        if args.out:
            data = {
                "ama_path": str(args.ama),
                "material": mat.name,
                "loss_factor": getattr(mat, 'loss_factor', 0.05),
                "force_amplitude_N": args.force,
                "frequencies_hz": result.frequencies_hz.tolist(),
                "total_power_watts": result.total_power_watts.tolist(),
                "efficiency": result.efficiency.tolist(),
                "peak_frequency_hz": result.peak_frequency_hz,
                "peak_power_watts": result.peak_power_watts,
            }
            with open(args.out, "w") as f:
                json.dump(data, f, indent=2)
            print(f"\n  Saved to: {args.out}")
        
        if args.plot:
            _plot_heat_single(result, args)
        
        return result

    # Comparison mode
    if args.baseline and args.candidate:
        print(f"\n  Baseline:  {args.baseline}")
        print(f"  Candidate: {args.candidate}")
        
        base_result, base_nodes, base_voxels = analyze_ama(args.baseline)
        cand_result, cand_nodes, cand_voxels = analyze_ama(args.candidate)
        
        comparison = compare_heat_generation(base_result, cand_result)
        
        print(f"\n[Results]")
        print(f"  Baseline:  {base_voxels} voxels, peak {base_result.peak_power_watts:.6e} W @ {base_result.peak_frequency_hz:.1f} Hz")
        print(f"  Candidate: {cand_voxels} voxels, peak {cand_result.peak_power_watts:.6e} W @ {cand_result.peak_frequency_hz:.1f} Hz")
        print(f"\n  Best heat amplification: +{comparison.best_amplification_dB:.2f} dB at {comparison.best_amplification_hz:.1f} Hz")
        print(f"    → Candidate generates {10**(comparison.best_amplification_dB/10):.1f}× more heat at this frequency")
        
        # Summary
        n_more = int(np.sum(comparison.power_ratio_dB > 3.0))
        n_less = int(np.sum(comparison.power_ratio_dB < -3.0))
        print(f"\n  Frequency bins where candidate generates >2× more heat: {n_more}/{len(freq_hz)}")
        print(f"  Frequency bins where candidate generates <0.5× heat: {n_less}/{len(freq_hz)}")
        
        if args.out:
            data = {
                "baseline_path": str(args.baseline),
                "candidate_path": str(args.candidate),
                "material": mat.name,
                "loss_factor": getattr(mat, 'loss_factor', 0.05),
                "force_amplitude_N": args.force,
                "frequencies_hz": comparison.frequencies_hz.tolist(),
                "baseline_power_watts": comparison.baseline_power.tolist(),
                "candidate_power_watts": comparison.candidate_power.tolist(),
                "power_ratio_dB": comparison.power_ratio_dB.tolist(),
                "best_amplification_dB": comparison.best_amplification_dB,
                "best_amplification_hz": comparison.best_amplification_hz,
                "baseline_peak_hz": comparison.baseline_peak_hz,
                "candidate_peak_hz": comparison.candidate_peak_hz,
                "math": {
                    "heat_power_eq": "P = π · η · f · k · |u|²",
                    "explanation": "Damping converts vibration energy to heat. Higher displacement amplitude (from resonance/amplification) means more heat.",
                },
            }
            with open(args.out, "w") as f:
                json.dump(data, f, indent=2)
            print(f"\n  Saved to: {args.out}")
        
        if args.out_csv:
            with open(args.out_csv, "w") as f:
                f.write("freq_hz,P_baseline_W,P_candidate_W,ratio_dB\n")
                for i in range(len(comparison.frequencies_hz)):
                    f.write(f"{comparison.frequencies_hz[i]:.2f},{comparison.baseline_power[i]:.6e},{comparison.candidate_power[i]:.6e},{comparison.power_ratio_dB[i]:.2f}\n")
            print(f"  CSV saved to: {args.out_csv}")
        
        if args.plot:
            _plot_heat_comparison(comparison, base_result, cand_result, args)
        
        return comparison
    
    print("Error: Provide --ama for single analysis, or --baseline and --candidate for comparison")
    return None


def _plot_heat_single(result, args):
    """Plot heat generation for single structure."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [warning] matplotlib not available, skipping plot")
        return
    
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    # Heat power vs frequency
    ax1 = axes[0]
    ax1.semilogy(result.frequencies_hz, result.total_power_watts, 'b-', linewidth=1.5)
    ax1.axvline(result.peak_frequency_hz, color='r', linestyle='--', alpha=0.7,
                label=f'Peak: {result.peak_frequency_hz:.0f} Hz')
    ax1.set_ylabel("Heat Power (W)")
    ax1.set_title("Vibration-to-Heat Conversion: P = π·η·f·k·|u|²")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Efficiency
    ax2 = axes[1]
    ax2.plot(result.frequencies_hz, result.efficiency * 100, 'g-', linewidth=1.5)
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Conversion Efficiency (%)")
    ax2.set_title("Fraction of Input Power Converted to Heat")
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    plot_path = args.out.replace(".json", ".png") if args.out else "heat_generation.png"
    plt.savefig(plot_path, dpi=150)
    print(f"  Plot saved to: {plot_path}")
    plt.close()


def _plot_heat_comparison(comp, base, cand, args):
    """Plot heat generation comparison."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [warning] matplotlib not available, skipping plot")
        return
    
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    # Heat power comparison
    ax1 = axes[0]
    ax1.semilogy(comp.frequencies_hz, comp.baseline_power, 'b-', label='Baseline (plain)', linewidth=1.5)
    ax1.semilogy(comp.frequencies_hz, comp.candidate_power, 'r--', label='Candidate (gyroid)', linewidth=1.5)
    ax1.axvline(base.peak_frequency_hz, color='b', linestyle=':', alpha=0.5)
    ax1.axvline(cand.peak_frequency_hz, color='r', linestyle=':', alpha=0.5)
    ax1.set_ylabel("Heat Power (W)")
    ax1.set_title("Heat Generation: Baseline vs Gyroid Structure")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Power ratio
    ax2 = axes[1]
    ax2.fill_between(comp.frequencies_hz, comp.power_ratio_dB, 0,
                     where=comp.power_ratio_dB > 0, color='red', alpha=0.4,
                     label='Candidate generates MORE heat')
    ax2.fill_between(comp.frequencies_hz, comp.power_ratio_dB, 0,
                     where=comp.power_ratio_dB < 0, color='blue', alpha=0.4,
                     label='Candidate generates LESS heat')
    ax2.axhline(0, color='k', linewidth=0.5)
    ax2.axhline(3, color='r', linestyle='--', linewidth=0.5, alpha=0.7)
    ax2.axhline(-3, color='b', linestyle='--', linewidth=0.5, alpha=0.7)
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Heat Ratio (dB) = 10·log₁₀(P_cand/P_base)")
    ax2.set_title(f"Peak Heat Amplification: +{comp.best_amplification_dB:.1f} dB @ {comp.best_amplification_hz:.0f} Hz")
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    plot_path = args.out.replace(".json", ".png") if args.out else "heat_comparison.png"
    plt.savefig(plot_path, dpi=150)
    print(f"  Plot saved to: {plot_path}")
    plt.close()



def main():
    parser = argparse.ArgumentParser(
        description="PR-Root Vibration Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Modal subcommand
    p_modal = subparsers.add_parser("modal", help="Run modal analysis")
    p_modal.add_argument("--ama", required=True, help="Path to analytic .ama")
    p_modal.add_argument("--out", help="Output JSON path")
    p_modal.add_argument("--extent", type=float, default=1.5, help="Sampling extent")
    p_modal.add_argument("--res", type=int, default=24, help="Voxel resolution")
    p_modal.add_argument("--material", default="PLA", help="Material name")
    p_modal.add_argument("--modes", type=int, default=12, help="Number of modes")
    p_modal.add_argument("--f0", type=float, default=50.0, help="Min frequency Hz")
    p_modal.add_argument("--f1", type=float, default=2500.0, help="Max frequency Hz")
    p_modal.add_argument("--nfreq", type=int, default=100, help="Number of frequency points")
    p_modal.add_argument("--eta", type=float, default=0.05, help="Loss factor")
    p_modal.set_defaults(func=cmd_modal)

    # Compare subcommand
    p_cmp = subparsers.add_parser("compare", help="Compare baseline vs candidate")
    p_cmp.add_argument("--baseline", required=True, help="Baseline .ama")
    p_cmp.add_argument("--candidate", required=True, help="Candidate .ama")
    p_cmp.add_argument("--out", help="Output JSON path")
    p_cmp.add_argument("--out-csv", help="Output CSV path")
    p_cmp.add_argument("--plot", action="store_true", help="Generate plot")
    p_cmp.add_argument("--extent", type=float, default=1.5, help="Sampling extent")
    p_cmp.add_argument("--res", type=int, default=24, help="Voxel resolution")
    p_cmp.add_argument("--material", default="PLA", help="Material name")
    p_cmp.add_argument("--modes", type=int, default=12, help="Number of modes")
    p_cmp.add_argument("--f0", type=float, default=50.0, help="Min frequency Hz")
    p_cmp.add_argument("--f1", type=float, default=2500.0, help="Max frequency Hz")
    p_cmp.add_argument("--nfreq", type=int, default=100, help="Number of frequency points")
    p_cmp.add_argument("--eta", type=float, default=0.05, help="Loss factor")
    p_cmp.set_defaults(func=cmd_compare)

    # Manim export subcommand
    p_manim = subparsers.add_parser("manim", help="Export data for Manim animation")
    p_manim.add_argument("--baseline", required=True, help="Baseline .ama")
    p_manim.add_argument("--candidate", required=True, help="Candidate .ama")
    p_manim.add_argument("--out", help="Output JSON path")
    p_manim.add_argument("--extent", type=float, default=1.5, help="Sampling extent")
    p_manim.add_argument("--res", type=int, default=24, help="Voxel resolution")
    p_manim.add_argument("--f0", type=float, default=50.0, help="Min frequency Hz")
    p_manim.add_argument("--f1", type=float, default=2500.0, help="Max frequency Hz")
    p_manim.add_argument("--nfreq", type=int, default=100, help="Number of frequency points")
    p_manim.set_defaults(func=cmd_manim_export)

    # Heat generation subcommand
    p_heat = subparsers.add_parser("heat", help="Compute heat generation from vibration")
    p_heat.add_argument("--ama", help="Single .ama to analyze")
    p_heat.add_argument("--baseline", help="Baseline .ama for comparison")
    p_heat.add_argument("--candidate", help="Candidate .ama for comparison")
    p_heat.add_argument("--out", help="Output JSON path")
    p_heat.add_argument("--out-csv", help="Output CSV path")
    p_heat.add_argument("--plot", action="store_true", help="Generate plot")
    p_heat.add_argument("--extent", type=float, default=1.5, help="Sampling extent")
    p_heat.add_argument("--res", type=int, default=24, help="Voxel resolution")
    p_heat.add_argument("--material", default="PLA", help="Material name")
    p_heat.add_argument("--f0", type=float, default=50.0, help="Min frequency Hz")
    p_heat.add_argument("--f1", type=float, default=2500.0, help="Max frequency Hz")
    p_heat.add_argument("--nfreq", type=int, default=100, help="Number of frequency points")
    p_heat.add_argument("--force", type=float, default=1.0, help="Force amplitude (N)")
    p_heat.set_defaults(func=cmd_heat)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
