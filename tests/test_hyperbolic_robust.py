"""
Comprehensive tests for robust hyperbolic geometry implementation.

Tests the numerical stability and edge case handling of the adaptive pi
ratio calculation and related hyperbolic geometry functions.
"""

import pytest
import numpy as np
import math
from adaptivecad.geom.hyperbolic import pi_a_over_pi, full_turn_deg, rotate_cmd


class TestPiAOverPiRobust:
    """Test the robust pi_a_over_pi implementation."""
    
    def test_edge_case_zero_radius(self):
        """Test r ≈ 0 returns Euclidean limit."""
        assert abs(pi_a_over_pi(1e-12, 1.0) - 1.0) < 1e-6
        assert abs(pi_a_over_pi(0.0, 1.0) - 1.0) < 1e-6
        
    def test_edge_case_zero_curvature(self):
        """Test kappa ≈ 0 returns Euclidean limit."""
        assert abs(pi_a_over_pi(1.0, 1e-12) - 1.0) < 1e-6
        assert abs(pi_a_over_pi(1.0, 0.0) - 1.0) < 1e-6
        
    def test_both_zero(self):
        """Test both r and kappa ≈ 0."""
        assert abs(pi_a_over_pi(1e-12, 1e-12) - 1.0) < 1e-6
        assert abs(pi_a_over_pi(0.0, 0.0) - 1.0) < 1e-6
        
    def test_regular_case(self):
        """Test regular case with known result."""
        # For r=1, kappa=1: sinh(1)/1 ≈ 1.175201
        result = pi_a_over_pi(1.0, 1.0)
        expected = math.sinh(1.0)  # ≈ 1.175201
        assert abs(result - expected) < 1e-6
        
    def test_small_ratio_taylor_expansion(self):
        """Test small r/kappa uses Taylor expansion correctly."""
        # When r/kappa is small, should use Taylor: sinh(x) ≈ x + x³/6
        r, kappa = 0.01, 1.0
        x = r / kappa  # = 0.01
        
        # Manual Taylor calculation
        expected_sinh = x * (1 + x*x * (1/6 + x*x / 120))
        expected_ratio = (kappa * expected_sinh) / r
        
        result = pi_a_over_pi(r, kappa)
        assert abs(result - expected_ratio) < 1e-10
        
    def test_large_ratio_overflow_protection(self):
        """Test large r/kappa values don't cause overflow."""
        # These values would normally cause overflow
        result1 = pi_a_over_pi(1000.0, 1.0)  # r/kappa = 1000
        result2 = pi_a_over_pi(10000.0, 1.0)  # r/kappa = 10000
        
        # Should return finite, positive values
        assert np.isfinite(result1)
        assert result1 > 0
        assert np.isfinite(result2)
        assert result2 > 0
        
    def test_negative_curvature(self):
        """Test negative curvature handling."""
        # Negative kappa should work (hyperbolic geometry)
        result = pi_a_over_pi(1.0, -1.0)
        assert np.isfinite(result)
        assert result > 0
        
    def test_negative_radius(self):
        """Test negative radius handling."""
        # Should handle negative radius gracefully
        result = pi_a_over_pi(-1.0, 1.0)
        assert np.isfinite(result)
        assert result > 0
        
    def test_very_small_values(self):
        """Test very small but non-zero values."""
        result = pi_a_over_pi(1e-15, 1e-15)
        assert result == 1.0  # Should fall back to Euclidean
        
    def test_very_large_values(self):
        """Test very large values don't break."""
        result = pi_a_over_pi(1e10, 1e10)
        assert np.isfinite(result)
        assert result > 0
        
    def test_nan_inf_protection(self):
        """Test protection against NaN and Inf."""
        # These extreme cases should fall back to 1.0
        result1 = pi_a_over_pi(float('inf'), 1.0)
        result2 = pi_a_over_pi(1.0, float('inf'))
        
        # Should not be NaN or Inf
        assert np.isfinite(result1)
        assert np.isfinite(result2)
        
    def test_symmetry_properties(self):
        """Test expected symmetry properties."""
        # π_a/π should be symmetric in certain cases
        r, kappa = 2.0, 3.0
        result1 = pi_a_over_pi(r, kappa)
        result2 = pi_a_over_pi(-r, -kappa)  # Both negative
        
        # Should give same result for both negative
        assert abs(result1 - result2) < 1e-10
        
    def test_monotonicity(self):
        """Test monotonicity properties."""
        kappa = 1.0
        radii = [0.1, 0.5, 1.0, 2.0, 5.0]
        results = [pi_a_over_pi(r, kappa) for r in radii]
        
        # For positive curvature, ratio should increase with radius
        for i in range(len(results) - 1):
            assert results[i] <= results[i + 1], f"Non-monotonic at {radii[i]}"


class TestFullTurnDegRobust:
    """Test full_turn_deg with robust pi_a_over_pi."""
    
    def test_zero_radius(self):
        """Test zero radius case."""
        result = full_turn_deg(0.0, 1.0)
        assert result == 360.0  # Should be standard 360 degrees
        
    def test_small_radius(self):
        """Test very small radius."""
        result = full_turn_deg(1e-10, 1.0)
        assert abs(result - 360.0) < 1e-6  # Should approach 360
        
    def test_regular_case(self):
        """Test regular case."""
        result = full_turn_deg(1.0, 1.0)
        expected = 360.0 * math.sinh(1.0)  # ≈ 423.07 degrees
        assert abs(result - expected) < 1e-6


class TestRotateCmdRobust:
    """Test rotate_cmd with robust foundation."""
    
    def test_zero_radius(self):
        """Test zero radius case."""
        result = rotate_cmd(90.0, 0.0, 1.0)  # 90 degrees
        expected = math.pi / 2  # Should be π/2 radians
        assert abs(result - expected) < 1e-6
        
    def test_small_radius(self):
        """Test very small radius."""
        result = rotate_cmd(90.0, 1e-10, 1.0)
        expected = math.pi / 2  # Should approach π/2
        assert abs(result - expected) < 1e-6


class TestNumericalStability:
    """Test numerical stability across parameter ranges."""
    
    def test_stress_test_parameter_space(self):
        """Stress test across wide parameter ranges."""
        # Test ranges spanning many orders of magnitude
        radii = [1e-12, 1e-6, 1e-3, 1e-1, 1, 10, 100, 1000]
        kappas = [1e-12, 1e-6, 1e-3, 1e-1, 1, 10, 100, 1000]
        
        failures = []
        for r in radii:
            for k in kappas:
                try:
                    result = pi_a_over_pi(r, k)
                    if not (np.isfinite(result) and result > 0):
                        failures.append((r, k, result))
                except Exception as e:
                    failures.append((r, k, f"Exception: {e}"))
        
        if failures:
            pytest.fail(f"Numerical failures: {failures[:5]}...")  # Show first 5
            
    def test_boundary_conditions(self):
        """Test at numerical boundaries."""
        eps = 1e-10
        
        # Test just above and below the epsilon threshold
        just_above = eps * 1.1
        just_below = eps * 0.9
        
        result1 = pi_a_over_pi(just_above, 1.0)
        result2 = pi_a_over_pi(just_below, 1.0)
        
        # just_below should trigger the eps fallback
        assert result2 == 1.0
        # just_above should compute normally
        assert result1 != 1.0


class TestPerformanceBenchmark:
    """Performance benchmarks for the robust implementation."""
    
    def test_performance_vs_naive(self):
        """Compare performance against naive implementation."""
        import time
        
        # Naive implementation (original)
        def naive_pi_a_over_pi(r, kappa):
            if r == 0:
                return 1.0
            return (kappa * math.sinh(r / kappa)) / r
        
        # Test data
        test_cases = [(1.0, 1.0), (0.5, 2.0), (2.0, 0.5), (10.0, 10.0)] * 1000
        
        # Time robust implementation
        start = time.time()
        for r, k in test_cases:
            pi_a_over_pi(r, k)
        robust_time = time.time() - start
        
        # Time naive implementation (but catch errors)
        start = time.time()
        for r, k in test_cases:
            try:
                naive_pi_a_over_pi(r, k)
            except:
                pass  # Ignore errors in naive version
        naive_time = time.time() - start
        
        # Robust version should be reasonable (within 5x of naive)
        assert robust_time < naive_time * 5, f"Too slow: {robust_time:.4f}s vs {naive_time:.4f}s"


def test_integration_with_existing_code():
    """Test that the robust implementation integrates with existing code."""
    # These should all work without errors
    result1 = full_turn_deg(1.0, 1.0)
    result2 = rotate_cmd(90.0, 1.0, 1.0)
    
    assert np.isfinite(result1)
    assert np.isfinite(result2)
    assert result1 > 0
    assert result2 > 0


if __name__ == "__main__":
    # Quick self-test
    print("Running basic tests...")
    
    # Test edge cases
    assert abs(pi_a_over_pi(1e-12, 1.0) - 1.0) < 1e-6  # r ≈ 0
    assert abs(pi_a_over_pi(1.0, 1e-12) - 1.0) < 1e-6  # kappa ≈ 0
    assert abs(pi_a_over_pi(1.0, 1.0) - math.sinh(1.0)) < 1e-6  # Regular
    
    print("✓ Edge cases pass")
    
    # Test stability
    result = pi_a_over_pi(1000.0, 1.0)  # Large ratio
    assert np.isfinite(result) and result > 0
    
    print("✓ Stability tests pass")
    
    # Test integration
    deg = full_turn_deg(1.0, 1.0)
    rad = rotate_cmd(90.0, 1.0, 1.0)
    assert np.isfinite(deg) and np.isfinite(rad)
    
    print("✓ Integration tests pass")
    print("All basic tests passed!")
