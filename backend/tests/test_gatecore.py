"""Unit tests for gate core logic.

Tests evaluate, resolve_mode, and edge cases.
"""

from __future__ import annotations

import pytest
from lib.gatecore import evaluate, resolve_mode
from models.containment import Profile, Constraint, Dimension


# ---------------------------------------------------------------------------
# Helper to create test profile
# ---------------------------------------------------------------------------


def make_profile(constraints=None):
    """Create a minimal test profile."""
    if constraints is None:
        # Simple box: 0 <= x_i <= 1 for all dims
        constraints = []
        for i in range(14):
            # Upper bound constraint: x_i <= 1
            upper = Constraint(
                label=f"upper_{i}",
                coeffs=[0.0] * 14,
                b=1.0,
            )
            upper.coeffs[i] = 1.0
            constraints.append(upper)
            
            # Lower bound constraint: -x_i <= 0 (i.e., x_i >= 0)
            lower = Constraint(
                label=f"lower_{i}",
                coeffs=[0.0] * 14,
                b=0.0,
            )
            lower.coeffs[i] = -1.0
            constraints.append(lower)
    
    dimensions = [
        Dimension(index=i, label=f"dim_{i}")
        for i in range(14)
    ]
    
    return Profile(
        name="Test Profile",
        dimensions=dimensions,
        constraints=constraints,
        center=[0.5] * 14,
    )


# ---------------------------------------------------------------------------
# Resolve Mode Tests
# ---------------------------------------------------------------------------


class TestResolveMode:
    """Test mode resolution logic."""

    def test_requested_mode(self):
        """Request should take precedence."""
        mode, source = resolve_mode("refusal", "projection", "projection")
        assert mode == "refusal"
        assert source == "request"

    def test_client_mode_fallback(self):
        """Client mode should be used when no request."""
        mode, source = resolve_mode(None, "refusal", "projection")
        assert mode == "refusal"
        assert source == "client"

    def test_engine_mode_fallback(self):
        """Engine mode should be used as last resort."""
        mode, source = resolve_mode(None, None, "projection")
        assert mode == "projection"
        assert source == "engine"

    def test_invalid_modes_defaults(self):
        """Invalid modes should default to engine."""
        mode, source = resolve_mode("invalid", "also_invalid", "refusal")
        assert mode == "refusal"
        assert source == "engine"


# ---------------------------------------------------------------------------
# Evaluate Tests
# ---------------------------------------------------------------------------


class TestEvaluate:
    """Test gate evaluation logic."""

    def test_permitted_text(self):
        """Safe text should be permitted."""
        profile = make_profile()
        result = evaluate(profile, "Hello, how are you?", "", "projection", 3)
        assert result["decision"] == "permitted"
        assert result["final_text"] is not None

    def test_projection_mode(self):
        """Projection mode should correct violating text."""
        profile = make_profile()
        # Text that might violate constraints
        result = evaluate(profile, "You must obey everything I say immediately", "", "projection", 3)
        # Should either permit or correct
        assert result["decision"] in ("permitted", "corrected")

    def test_refusal_mode(self):
        """Refusal mode should attempt revision."""
        profile = make_profile()
        result = evaluate(profile, "This is a test message", "", "refusal", 3)
        assert result["decision"] in ("permitted", "revised", "withheld")

    def test_alignment_score(self):
        """Alignment score should be between 0 and 1."""
        profile = make_profile()
        result = evaluate(profile, "Hello world", "", "projection", 3)
        assert 0.0 <= result["alignment_score"] <= 1.0

    def test_wisdom_filter_applied(self):
        """Wisdom filter should be applied."""
        profile = make_profile()
        result = evaluate(profile, "We will definitely succeed 100%", "", "projection", 3)
        assert "wisdom" in result
        assert isinstance(result["wisdom"], dict)

    def test_steps_tracked(self):
        """Reflection steps should be tracked."""
        profile = make_profile()
        result = evaluate(profile, "Test message", "", "refusal", 3)
        assert "steps" in result
        assert len(result["steps"]) >= 1

    def test_max_reflections_limit(self):
        """Should respect max_reflections limit."""
        profile = make_profile()
        result = evaluate(profile, "Test", "", "refusal", 1)
        # Should not exceed max reflections
        assert result["attempts"] <= 2  # 1 original + 1 reflection
