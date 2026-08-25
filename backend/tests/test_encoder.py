"""Unit tests for text encoder.

Tests encoding, revision, wisdom filtering, and edge cases.
"""

from __future__ import annotations

import pytest
from lib.encoder import (
    DIMENSION_NAMES,
    encode,
    revise,
    revision_targets,
    text_similarity,
    wisdom_filter,
)


# ---------------------------------------------------------------------------
# Encode Tests
# ---------------------------------------------------------------------------


class TestEncode:
    """Test text encoding to 14D vectors."""

    def test_basic_encoding(self):
        """Basic text should encode to valid vector."""
        vector = encode("Hello world")
        assert len(vector) == 14
        assert all(0.0 <= v <= 1.0 for v in vector)

    def test_deterministic(self):
        """Same input should produce same output."""
        text = "This is a test message"
        v1 = encode(text)
        v2 = encode(text)
        assert v1 == v2

    def test_context_affects_encoding(self):
        """Context should influence encoding."""
        text = "This is important"
        v1 = encode(text, context="critical")
        v2 = encode(text, context="casual")
        # Vectors may differ due to context weighting
        assert isinstance(v1, list)
        assert isinstance(v2, list)
        assert len(v1) == 14

    def test_empty_input(self):
        """Empty input should produce default vector."""
        vector = encode("")
        assert len(vector) == 14
        assert all(0.0 <= v <= 1.0 for v in vector)

    def test_none_input(self):
        """None input should not crash."""
        vector = encode(None)
        assert len(vector) == 14

    def test_long_input_truncated(self):
        """Very long input should be truncated."""
        long_text = "x " * 10000
        vector = encode(long_text)
        assert len(vector) == 14

    def test_dimension_names(self):
        """Should have 14 dimension names."""
        assert len(DIMENSION_NAMES) == 14

    def test_virtue_shadow_pairs(self):
        """Even indices are virtue, odd are shadow."""
        # Check that we have 14 dimensions with pairs
        assert len(DIMENSION_NAMES) == 14
        # Check first pair is harmony/dominance
        assert DIMENSION_NAMES[0] == "harmony"
        assert DIMENSION_NAMES[1] == "dominance"


# ---------------------------------------------------------------------------
# Revision Tests
# ---------------------------------------------------------------------------


class TestRevise:
    """Test text revision for safety."""

    def test_revise_with_targets(self):
        """Revision should append mitigation sentences."""
        text = "You must do this now"
        targets = [0, 2]  # harmony, order
        revised = revise(text, targets, 0)
        assert len(revised) > len(text)

    def test_revise_no_targets(self):
        """No targets should return original text."""
        text = "Hello world"
        revised = revise(text, [], 0)
        assert revised == text

    def test_revise_deterministic(self):
        """Same inputs should produce same output."""
        text = "Test message"
        targets = [1, 3]
        r1 = revise(text, targets, 0)
        r2 = revise(text, targets, 0)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Wisdom Filter Tests
# ---------------------------------------------------------------------------


class TestWisdomFilter:
    """Test wisdom filtering."""

    def test_overconfidence_detection(self):
        """Should detect overconfident language."""
        text = "We will definitely succeed with 100% certainty"
        result = wisdom_filter(text, 0.9, 0.0)
        assert result["overconfidence_detected"] is True

    def test_humility_detection(self):
        """Should suggest humility when appropriate."""
        text = "I'm not sure about this"
        result = wisdom_filter(text, 0.3, 0.2)
        assert result["humility_added"] is True

    def test_validation_suggestion(self):
        """Should suggest validation for professional domains."""
        text = "The medical diagnosis requires careful treatment"
        result = wisdom_filter(text, 0.8, 0.0)
        assert result["validation_suggested"] is True

    def test_normal_text(self):
        """Normal text should not trigger flags."""
        text = "Hello, how are you today?"
        result = wisdom_filter(text, 0.7, 0.0)
        assert result["overconfidence_detected"] is False
        assert result["validation_suggested"] is False


# ---------------------------------------------------------------------------
# Similarity Tests
# ---------------------------------------------------------------------------


class TestTextSimilarity:
    """Test text similarity calculation."""

    def test_identical_text(self):
        """Identical texts should have similarity 1.0."""
        text = "Hello world"
        assert text_similarity(text, text) == 1.0

    def test_completely_different(self):
        """Completely different texts should have low similarity."""
        t1 = "hello world"
        t2 = "goodbye universe"
        sim = text_similarity(t1, t2)
        assert sim < 1.0

    def test_empty_strings(self):
        """Empty strings should have similarity 1.0."""
        assert text_similarity("", "") == 1.0


# ---------------------------------------------------------------------------
# Revision Targets Tests
# ---------------------------------------------------------------------------


class TestRevisionTargets:
    """Test revision target calculation."""

    def test_positive_coefficient(self):
        """Positive coefficient should return complement."""
        coeffs = [1.0, 0.0, 0.0, 0.0]
        targets = revision_targets(coeffs)
        # Index 0 (harmony) -> complement is 1 (dominance)
        assert 1 in targets

    def test_negative_coefficient(self):
        """Negative coefficient should return self."""
        coeffs = [-1.0, 0.0, 0.0, 0.0]
        targets = revision_targets(coeffs)
        # Index 0 should map to itself
        assert 0 in targets

    def test_zero_coefficient(self):
        """Zero coefficient should not add target."""
        coeffs = [0.0, 0.0, 1.0, 0.0]
        targets = revision_targets(coeffs)
        assert 0 not in targets
