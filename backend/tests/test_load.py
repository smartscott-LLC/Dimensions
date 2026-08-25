"""Load and performance tests.

Tests latency, throughput, and stress conditions.
"""

from __future__ import annotations

import pytest
import time
import statistics


# ---------------------------------------------------------------------------
# Encoder Performance Tests
# ---------------------------------------------------------------------------


class TestEncoderPerformance:
    """Test encoder performance under load."""

    def test_encode_speed(self):
        """Encoding should be fast."""
        from lib.encoder import encode
        
        texts = [
            "Hello world",
            "This is a longer test message with more words",
            "Short",
            "A" * 1000,
        ]
        
        times = []
        for text in texts:
            start = time.perf_counter()
            encode(text)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        
        # Should be fast (< 10ms per encode)
        assert max(times) < 0.01, f"Encoding too slow: {max(times)*1000:.2f}ms"

    def test_encode_throughput(self):
        """Should handle reasonable throughput."""
        from lib.encoder import encode
        
        start = time.perf_counter()
        for _ in range(100):
            encode("Test message for throughput")
        elapsed = time.perf_counter() - start
        
        # Should handle 100 encodes in < 1 second
        assert elapsed < 1.0, f"Throughput too slow: {100/elapsed:.0f} ops/sec"


# ---------------------------------------------------------------------------
# Polytope Performance Tests
# ---------------------------------------------------------------------------


class TestPolytopePerformance:
    """Test polytope projection performance."""

    def test_projection_speed(self):
        """Projection should be fast."""
        from lib.polytope import project
        
        # Simple polytope
        rows = [[1.0] * 14 for _ in range(10)]
        b = [0.5] * 10
        x = [0.8] * 14
        
        start = time.perf_counter()
        project(rows, b, x)
        elapsed = time.perf_counter() - start
        
        # Should be fast (< 100ms)
        assert elapsed < 0.1, f"Projection too slow: {elapsed*1000:.2f}ms"

    def test_residuals_speed(self):
        """Residual calculation should be fast."""
        from lib.polytope import residuals
        
        rows = [[1.0] * 14 for _ in range(10)]
        b = [0.5] * 10
        x = [0.5] * 14
        
        start = time.perf_counter()
        residuals(rows, b, x)
        elapsed = time.perf_counter() - start
        
        assert elapsed < 0.01, f"Residuals too slow: {elapsed*1000:.2f}ms"


# ---------------------------------------------------------------------------
# Gate Performance Tests
# ---------------------------------------------------------------------------


class TestGatePerformance:
    """Test gate evaluation performance."""

    def test_gate_speed(self):
        """Gate evaluation should be fast."""
        from lib.gatecore import evaluate
        from models.containment import Profile, Constraint, Dimension
        
        # Create simple profile
        constraints = [
            Constraint(label=f"c{i}", coeffs=[0.1] * 14, b=0.5)
            for i in range(5)
        ]
        dimensions = [Dimension(index=i, label=f"d{i}") for i in range(14)]
        profile = Profile(name="Test", dimensions=dimensions, constraints=constraints)
        
        start = time.perf_counter()
        evaluate(profile, "Test message", "", "projection", 3)
        elapsed = time.perf_counter() - start
        
        # Should be fast (< 100ms)
        assert elapsed < 0.1, f"Gate too slow: {elapsed*1000:.2f}ms"


# ---------------------------------------------------------------------------
# Stress Tests
# ---------------------------------------------------------------------------


class TestStress:
    """Stress tests for edge cases."""

    def test_many_concurrent_encodes(self):
        """Should handle many concurrent encodes."""
        from lib.encoder import encode
        
        start = time.perf_counter()
        results = [encode(f"Message {i}") for i in range(100)]
        elapsed = time.perf_counter() - start
        
        assert len(results) == 100
        assert all(len(r) == 14 for r in results)
        assert elapsed < 1.0

    def test_large_input_handling(self):
        """Should handle large inputs gracefully."""
        from lib.encoder import encode
        
        large_inputs = [
            "x" * 10000,
            "y" * 50000,
            "z" * 100000,
        ]
        
        for inp in large_inputs:
            result = encode(inp)
            assert len(result) == 14


# ---------------------------------------------------------------------------
# Latency Benchmark Tests
# ---------------------------------------------------------------------------


class TestLatencyBenchmarks:
    """Latency benchmark tests."""

    def test_encode_latency_p99(self):
        """P99 encode latency should be under threshold."""
        from lib.encoder import encode
        
        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            encode("Benchmark test message")
            latencies.append(time.perf_counter() - start)
        
        latencies.sort()
        p99_idx = int(len(latencies) * 0.99)
        p99 = latencies[min(p99_idx, len(latencies) - 1)]
        
        assert p99 < 0.01, f"P99 latency too high: {p99*1000:.2f}ms"

    def test_projection_latency_p99(self):
        """P99 projection latency should be under threshold."""
        from lib.polytope import project
        
        rows = [[1.0] * 14 for _ in range(5)]
        b = [0.5] * 5
        x = [0.5] * 14
        
        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            project(rows, b, x)
            latencies.append(time.perf_counter() - start)
        
        latencies.sort()
        p99_idx = int(len(latencies) * 0.99)
        p99 = latencies[min(p99_idx, len(latencies) - 1)]
        
        assert p99 < 0.1, f"P99 projection latency too high: {p99*1000:.2f}ms"
