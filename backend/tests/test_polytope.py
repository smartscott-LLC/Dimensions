"""Unit tests for polytope geometry engine.

Tests residuals, projection, sampling, and edge cases.
"""

from __future__ import annotations

import pytest
from lib.polytope import DIMENSIONS, euclidean, project, residuals, sample_vector


# ---------------------------------------------------------------------------
# Residuals Tests
# ---------------------------------------------------------------------------


class TestResiduals:
    """Test residual calculation: r = Ax - b."""

    def test_simple_residual(self):
        """Basic residual calculation."""
        rows = [[1.0, 0.0], [0.0, 1.0]]
        b = [0.5, 0.5]
        x = [0.3, 0.3]
        result = residuals(rows, b, x)
        assert len(result) == 2
        assert abs(result[0] - (-0.2)) < 1e-10
        assert abs(result[1] - (-0.2)) < 1e-10

    def test_violated_constraint(self):
        """Positive residual means violation."""
        rows = [[1.0]]
        b = [0.5]
        x = [0.8]
        result = residuals(rows, b, x)
        assert result[0] > 0  # Violated

    def test_satisfied_constraint(self):
        """Negative residual means satisfied."""
        rows = [[1.0]]
        b = [0.5]
        x = [0.3]
        result = residuals(rows, b, x)
        assert result[0] < 0  # Satisfied

    def test_zero_residual(self):
        """Exactly on boundary."""
        rows = [[1.0]]
        b = [0.5]
        x = [0.5]
        result = residuals(rows, b, x)
        assert abs(result[0]) < 1e-10


# ---------------------------------------------------------------------------
# Projection Tests
# ---------------------------------------------------------------------------


class TestProjection:
    """Test Dykstra projection onto polytope."""

    def test_projection_inside_polytope(self):
        """Point already inside should not move."""
        rows = [[1.0, 0.0], [0.0, 1.0]]
        b = [1.0, 1.0]
        x = [0.3, 0.3]
        projected, iterations = project(rows, b, x)
        assert abs(projected[0] - x[0]) < 1e-9
        assert abs(projected[1] - x[1]) < 1e-9

    def test_projection_outside_polytope(self):
        """Point outside should be projected inside."""
        rows = [[1.0, 0.0], [0.0, 1.0]]
        b = [1.0, 1.0]
        x = [1.5, 0.5]
        projected, iterations = project(rows, b, x)
        assert projected[0] <= 1.0 + 1e-9
        assert projected[1] <= 1.0 + 1e-9

    def test_projection_multiple_constraints(self):
        """Projection should satisfy all constraints."""
        rows = [
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
        ]
        b = [1.0, 1.0, 1.5]
        x = [0.8, 0.8]
        projected, iterations = project(rows, b, x)
        res = residuals(rows, b, projected)
        assert all(r <= 1e-9 for r in res)

    def test_projection_converges(self):
        """Projection should converge within max iterations."""
        rows = [[1.0, 1.0]]
        b = [0.5]
        x = [1.0, 1.0]
        projected, iterations = project(rows, b, x, max_iter=100)
        assert iterations < 100
        res = residuals(rows, b, projected)
        assert res[0] <= 1e-9


# ---------------------------------------------------------------------------
# Euclidean Distance Tests
# ---------------------------------------------------------------------------


class TestEuclidean:
    """Test Euclidean distance calculation."""

    def test_same_point(self):
        """Distance from point to itself is zero."""
        assert euclidean([1.0, 2.0], [1.0, 2.0]) == 0.0

    def test_known_distance(self):
        """Known Euclidean distance."""
        assert euclidean([0.0, 0.0], [3.0, 4.0]) == 5.0

    def test_symmetry(self):
        """Distance is symmetric."""
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        assert euclidean(a, b) == euclidean(b, a)


# ---------------------------------------------------------------------------
# Sampling Tests
# ---------------------------------------------------------------------------


class TestSampling:
    """Test vector sampling."""

    def test_sample_permit_inside(self):
        """Permitted sample should be inside polytope."""
        rows = [[1.0, 0.0], [0.0, 1.0]]
        b = [1.0, 1.0]
        center = [0.5, 0.5]
        
        import random
        rng = random.Random(42)
        sample = sample_vector(rows, b, center, breach=False, rng=rng)
        
        assert len(sample) == 2
        res = residuals(rows, b, sample)
        assert all(r <= 1e-6 for r in res)

    def test_sample_breach_outside(self):
        """Breach sample may be outside polytope."""
        rows = [[1.0, 0.0], [0.0, 1.0]]
        b = [1.0, 1.0]
        center = [0.5, 0.5]
        
        import random
        rng = random.Random(42)
        sample = sample_vector(rows, b, center, breach=True, rng=rng)
        
        assert len(sample) == 2

    def test_sample_dimension_count(self):
        """Sample should have correct dimension count."""
        rows = [[1.0] * DIMENSIONS] * 5
        b = [0.5] * 5
        center = [0.5] * DIMENSIONS
        
        import random
        rng = random.Random(42)
        sample = sample_vector(rows, b, center, breach=False, rng=rng)
        
        assert len(sample) == DIMENSIONS


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_constraints(self):
        """Empty constraint set should return input."""
        x = [0.5] * DIMENSIONS
        projected, iterations = project([], [], x)
        assert projected == x

    def test_single_dimension(self):
        """Single dimension projection."""
        rows = [[1.0]]
        b = [0.5]
        x = [0.8]
        projected, _ = project(rows, b, x)
        assert abs(projected[0] - 0.5) < 1e-9

    def test_large_values(self):
        """Handle large coordinate values."""
        rows = [[1.0, 1.0]]
        b = [1000.0]
        x = [500.0, 600.0]
        projected, _ = project(rows, b, x)
        res = residuals(rows, b, projected)
        assert res[0] <= 1e-9
