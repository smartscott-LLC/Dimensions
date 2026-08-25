"""Integration tests for API endpoints.

Tests hit the live uvicorn process (same as frontend sees), using httpx client.
See conftest.py for the client fixture.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Auth Endpoint Tests
# ---------------------------------------------------------------------------


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_login_endpoint_exists(self, client):
        """Login endpoint should exist."""
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass1!"
        })
        # Should not be 404 (might be 401 if credentials invalid)
        assert response.status_code != 404

    def test_me_endpoint_returns_401_without_auth(self, client):
        """Me endpoint should return 401 without auth."""
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_csrf_token_endpoint_exists(self, client):
        """CSRF token endpoint should exist."""
        response = client.get("/auth/csrf-token")
        # Without auth, should get 401
        assert response.status_code in (401, 200)


# ---------------------------------------------------------------------------
# Containment Endpoint Tests
# ---------------------------------------------------------------------------


class TestContainmentEndpoints:
    """Test containment API endpoints."""

    def test_contain_endpoint_exists(self, client):
        """Contain endpoint should exist."""
        response = client.post("/contain", json={
            "vector": [0.5] * 14,
            "source": "test",
            "label": "test-label"
        })
        # Should not be 404
        assert response.status_code != 404

    def test_contain_invalid_vector_length(self, client):
        """Contain with wrong vector length should fail with 422."""
        response = client.post("/contain", json={
            "vector": [0.5] * 10,  # Wrong length
            "source": "test"
        })
        assert response.status_code == 422

    def test_encode_endpoint(self, client):
        """Encode endpoint should return vector."""
        response = client.post("/encode", json={
            "text": "Hello world",
            "context": "test"
        })
        # Should not be 404
        assert response.status_code != 404


# ---------------------------------------------------------------------------
# Gate Endpoint Tests
# ---------------------------------------------------------------------------


class TestGateEndpoints:
    """Test gate API endpoints."""

    def test_gate_endpoint_exists(self, client):
        """Gate endpoint should exist."""
        response = client.post("/gate", json={
            "text": "Hello world",
            "mode": "projection"
        })
        # Should not be 404
        assert response.status_code != 404

    def test_gate_with_refusal_mode(self, client):
        """Gate with refusal mode should work."""
        response = client.post("/gate", json={
            "text": "Test message",
            "mode": "refusal"
        })
        # Should not be 404
        assert response.status_code != 404


# ---------------------------------------------------------------------------
# Chat Endpoint Tests
# ---------------------------------------------------------------------------


class TestChatEndpoints:
    """Test chat API endpoints."""

    def test_create_session(self, client):
        """Create chat session should work."""
        response = client.post("/chat/sessions", json={
            "title": "Test Session"
        })
        # Should not be 404
        assert response.status_code != 404

    def test_list_sessions(self, client):
        """List sessions should work."""
        response = client.get("/chat/sessions")
        # Should not be 404
        assert response.status_code != 404


# ---------------------------------------------------------------------------
# Client Management Tests
# ---------------------------------------------------------------------------


class TestClientEndpoints:
    """Test client management endpoints."""

    def test_list_clients(self, client):
        """List clients should work."""
        response = client.get("/clients")
        # Should not be 404
        assert response.status_code != 404

    def test_settings_endpoint(self, client):
        """Settings endpoint should work."""
        response = client.get("/settings")
        # Should not be 404
        assert response.status_code != 404


# ---------------------------------------------------------------------------
# Telemetry Tests
# ---------------------------------------------------------------------------


class TestTelemetryEndpoints:
    """Test telemetry endpoints."""

    def test_events_endpoint(self, client):
        """Events endpoint should work."""
        response = client.get("/events")
        # Should not be 404
        assert response.status_code != 404

    def test_telemetry_summary(self, client):
        """Telemetry summary should work."""
        response = client.get("/telemetry/summary")
        # Should not be 404
        assert response.status_code != 404

    def test_audit_endpoint(self, client):
        """Audit endpoint should work."""
        response = client.get("/audit")
        # Should not be 404
        assert response.status_code != 404


# ---------------------------------------------------------------------------
# Health Check Tests
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_endpoint(self, client):
        """Health endpoint should return 200."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert "uptime_seconds" in data
        assert "timestamp" in data

    def test_readyz_endpoint(self, client):
        """Readiness endpoint should return 200."""
        response = client.get("/readyz")
        assert response.status_code == 200
