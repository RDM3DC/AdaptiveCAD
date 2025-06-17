import math
from adaptivecad.nd_math import pi_a_over_pi, stable_pi_a_over_pi


def test_pi_a_over_pi_basic():
    """Test the pi_a_over_pi function with basic values."""
    # Test Euclidean case (κ = 0)
    assert abs(pi_a_over_pi(0.5, 0.0) - 1.0) < 1e-12
    assert abs(pi_a_over_pi(1.0, 0.0) - 1.0) < 1e-12
    
    # Test hyperbolic case (κ > 0) - expected value from demo
    assert abs(pi_a_over_pi(0.5, 1.0) - 1.04219) < 1e-5
    
    # Test spherical case (κ < 0)
    assert abs(pi_a_over_pi(0.5, -1.0) - 0.958851) < 1e-5
    
    # Test edge case: r → 0
    assert abs(pi_a_over_pi(1e-15, 1.0) - 1.0) < 1e-12
    assert abs(pi_a_over_pi(1e-15, -1.0) - 1.0) < 1e-12


def test_pi_a_over_pi_edge_cases():
    """Test edge cases for pi_a_over_pi function."""
    # Zero radius
    assert pi_a_over_pi(0.0, 1.0) == 1.0
    assert pi_a_over_pi(0.0, -1.0) == 1.0
    assert pi_a_over_pi(0.0, 0.0) == 1.0
    
    # Very small curvature
    assert abs(pi_a_over_pi(1.0, 1e-15) - 1.0) < 1e-12


def test_pi_a_over_pi_mathematical_properties():
    """Test mathematical properties of the function."""
    r = 0.3
    kappa = 2.0
    
    # For positive κ (hyperbolic): πₐ/π > 1
    ratio_hyp = pi_a_over_pi(r, kappa)
    assert ratio_hyp > 1.0
    
    # For negative κ (spherical): πₐ/π < 1  
    ratio_sph = pi_a_over_pi(r, -kappa)
    assert ratio_sph < 1.0
    
    # Verify the mathematical relationship
    root = math.sqrt(kappa) * r
    expected_hyp = math.sinh(root) / root
    assert abs(ratio_hyp - expected_hyp) < 1e-12
    
    root_sph = math.sqrt(kappa) * r
    expected_sph = math.sin(root_sph) / root_sph
    assert abs(ratio_sph - expected_sph) < 1e-12


def test_stable_pi_a_over_pi_bounds():
    """Ensure the stable version stays within expected limits."""
    for val in [-200, -10, -1, 0, 1, 10, 200]:
        scale = stable_pi_a_over_pi(val)
        assert 0.5 <= scale <= 1.5


if __name__ == "__main__":
    test_pi_a_over_pi_basic()
    test_pi_a_over_pi_edge_cases()
    test_pi_a_over_pi_mathematical_properties()
    print("✅ All pi_a_over_pi tests passed!")
