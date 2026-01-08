"""Material definitions for vibration simulation.

Contains common 3D printing filament materials and metals.
Values are typical/nominal - actual properties depend heavily
on print parameters, infill, etc.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IsotropicMaterial:
    """Isotropic material properties."""
    name: str
    density: float           # kg/m³
    youngs_modulus: float    # Pa
    poissons_ratio: float    # dimensionless
    loss_factor: float = 0.05  # Structural damping (η)

    def __str__(self) -> str:
        return f"{self.name} (E={self.youngs_modulus/1e9:.1f} GPa, ρ={self.density:.0f} kg/m³)"


# ============================================
# 3D Printing Filaments
# ============================================

PLA = IsotropicMaterial(
    name="PLA",
    density=1240.0,
    youngs_modulus=3.5e9,
    poissons_ratio=0.36,
    loss_factor=0.04,
)

ABS = IsotropicMaterial(
    name="ABS",
    density=1040.0,
    youngs_modulus=2.1e9,
    poissons_ratio=0.35,
    loss_factor=0.05,
)

PETG = IsotropicMaterial(
    name="PETG",
    density=1270.0,
    youngs_modulus=2.2e9,
    poissons_ratio=0.38,
    loss_factor=0.04,
)

TPU = IsotropicMaterial(
    name="TPU",
    density=1200.0,
    youngs_modulus=0.05e9,  # 50 MPa - very flexible
    poissons_ratio=0.48,
    loss_factor=0.15,  # High damping
)

NYLON = IsotropicMaterial(
    name="Nylon",
    density=1150.0,
    youngs_modulus=1.7e9,
    poissons_ratio=0.40,
    loss_factor=0.06,
)

# ============================================
# Metals (for reference/comparison)
# ============================================

STEEL = IsotropicMaterial(
    name="Steel",
    density=7850.0,
    youngs_modulus=200e9,
    poissons_ratio=0.30,
    loss_factor=0.002,
)

ALUMINUM = IsotropicMaterial(
    name="Aluminum",
    density=2700.0,
    youngs_modulus=70e9,
    poissons_ratio=0.33,
    loss_factor=0.003,
)

TITANIUM = IsotropicMaterial(
    name="Titanium",
    density=4500.0,
    youngs_modulus=110e9,
    poissons_ratio=0.34,
    loss_factor=0.004,
)

# ============================================
# Convenience dict for CLI lookup
# ============================================

MATERIALS = {
    "PLA": PLA,
    "ABS": ABS,
    "PETG": PETG,
    "TPU": TPU,
    "NYLON": NYLON,
    "STEEL": STEEL,
    "ALUMINUM": ALUMINUM,
    "TITANIUM": TITANIUM,
}

__all__ = [
    "IsotropicMaterial",
    "PLA", "ABS", "PETG", "TPU", "NYLON",
    "STEEL", "ALUMINUM", "TITANIUM",
    "MATERIALS",
]
