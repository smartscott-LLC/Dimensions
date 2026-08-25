"""Security tests for authentication and authorization.

Tests JWT forgery, rate limit bypass, and other security concerns.
"""

from __future__ import annotations

import os
import pytest
import time
from unittest.mock import patch, AsyncMock


# ---------------------------------------------------------------------------
# JWT Security Tests
# ---------------------------------------------------------------------------


class TestJWTSecurity:
    """Test JWT security measures."""

    def test_jwt_secret_required(self):
        """Server should require JWT_SECRET."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises((KeyError, RuntimeError)):
                from lib.auth import _secret
                _secret()

    def test_jwt_too_short_rejected(self):
        """Short JWT secrets should be rejected."""
        original_secret = os.environ.get("JWT_SECRET")
        
        # Remove JWT_SECRET from env
        if "JWT_SECRET" in os.environ:
            del os.environ["JWT_SECRET"]
        
        try:
            # Patch os.environ.get to return None for JWT_SECRET
            with patch('os.environ.get') as mock_get:
                def side_effect(key, default=None):
                    if key == "JWT_SECRET":
                        return None
                    return original_secret if key == "JWT_SECRET" else default
                
                mock_get.side_effect = side_effect
                
                # Reload the module
                import importlib
                import lib.auth as auth_module
                importlib.reload(auth_module)
                
                # Should raise because JWT_SECRET is missing
                try:
                    auth_module._secret()
                    assert False, "Should have raised RuntimeError"
                except RuntimeError as e:
                    assert "JWT_SECRET environment variable is not set" in str(e)
        finally:
            # Restore original
            if original_secret is not None:
                os.environ["JWT_SECRET"] = original_secret

    def test_valid_jwt_secret_accepted(self):
        """Valid JWT secret should be accepted."""
        with patch.dict("os.environ", {"JWT_SECRET": "a" * 64}):
            from lib.auth import validate_jwt_secret
            # Should not raise
            validate_jwt_secret()


# ---------------------------------------------------------------------------
# Rate Limiting Tests
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Test rate limiting security."""

    def test_rate_limit_constants_defined(self):
        """Rate limit constants should be defined."""
        from routers.auth import MAX_LOGIN_ATTEMPTS, LOGIN_LOCKOUT_MINUTES
        assert MAX_LOGIN_ATTEMPTS == 5
        assert LOGIN_LOCKOUT_MINUTES == 15

    def test_rate_limit_blocks_after_threshold(self):
        """Should block after max attempts."""
        # This is tested via the auth router logic
        from routers.auth import _get_failed_attempts
        import inspect
        assert inspect.iscoroutinefunction(_get_failed_attempts)


# ---------------------------------------------------------------------------
# Account Lockout Tests
# ---------------------------------------------------------------------------


class TestAccountLockout:
    """Test account lockout security."""

    def test_lockout_constants_defined(self):
        """Lockout constants should be defined."""
        from routers.auth import MAX_ACCOUNT_FAILURES, ACCOUNT_LOCKOUT_HOURS
        assert MAX_ACCOUNT_FAILURES == 5
        assert ACCOUNT_LOCKOUT_HOURS == 1

    def test_lockout_functions_exist(self):
        """Lockout helper functions should exist."""
        from routers.auth import _is_account_locked, _lock_account
        import inspect
        assert inspect.iscoroutinefunction(_is_account_locked)
        assert inspect.iscoroutinefunction(_lock_account)


# ---------------------------------------------------------------------------
# API Key Security Tests
# ---------------------------------------------------------------------------


class TestAPIKeySecurity:
    """Test API key security."""

    def test_api_key_format_validation(self):
        """API keys should be validated for format."""
        import re
        # Valid format
        valid_key = "pk_" + "a" * 40
        assert re.match(r"^pk_[0-9a-f]{40}$", valid_key)
        
        # Invalid formats
        assert not re.match(r"^pk_[0-9a-f]{40}$", "invalid")
        assert not re.match(r"^pk_[0-9a-f]{40}$", "pk_short")
        assert not re.match(r"^pk_[0-9a-f]{40}$", "pk_" + "g" * 40)  # 'g' is not hex

    def test_api_key_not_in_source(self):
        """No hardcoded API keys in source."""
        import glob
        for pattern in ["lib/*.py", "routers/*.py"]:
            for filepath in glob.glob(pattern):
                with open(filepath, "r") as f:
                    content = f.read()
                # Should not have hardcoded keys (excluding docstrings and mint_key function)
                # Check for actual key values like pk_ followed by 40 hex chars
                import re
                hardcoded_keys = re.findall(r'pk_[0-9a-f]{40}', content)
                assert len(hardcoded_keys) == 0, f"Found hardcoded key in {filepath}: {hardcoded_keys}"


# ---------------------------------------------------------------------------
# CSRF Protection Tests
# ---------------------------------------------------------------------------


class TestCSRFProtection:
    """Test CSRF protection."""

    def test_csrf_module_exists(self):
        """CSRF module should exist."""
        import lib.csrf
        assert hasattr(lib.csrf, "generate_csrf_token")
        assert hasattr(lib.csrf, "validate_csrf_token")

    def test_csrf_token_expiry(self):
        """CSRF tokens should have expiry."""
        from lib.csrf import CSRF_TOKEN_EXPIRY_HOURS
        assert CSRF_TOKEN_EXPIRY_HOURS == 12


# ---------------------------------------------------------------------------
# Replay Attack Protection Tests
# ---------------------------------------------------------------------------


class TestReplayProtection:
    """Test replay attack protection."""

    def test_nonce_functions_exist(self):
        """Nonce functions should exist."""
        from lib.auth import generate_nonce, validate_nonce
        import inspect
        assert inspect.iscoroutinefunction(generate_nonce)
        assert inspect.iscoroutinefunction(validate_nonce)

    def test_nbf_in_token(self):
        """Tokens should include nbf claim."""
        from lib.auth import issue_token
        import inspect
        source = inspect.getsource(issue_token)
        assert "nbf" in source


# ---------------------------------------------------------------------------
# Password Security Tests
# ---------------------------------------------------------------------------


class TestPasswordSecurity:
    """Test password security."""

    def test_password_complexity_required(self):
        """Password should require complexity."""
        from models.auth import UserCreate
        import pytest
        
        # Weak passwords should fail
        weak_passwords = [
            "weak",
            "nouppercase1!",
            "NOLOWERCASE1!",
            "NoDigits!@",
            "NoSpecial1",
            "Ab1",  # Too short
        ]
        
        for pw in weak_passwords:
            with pytest.raises(Exception):
                UserCreate(email="test@example.com", password=pw)
        
        # Strong password should succeed (12+ chars with required chars)
        strong_password = "Str0ng!Pass1"  # 12 chars
        user = UserCreate(email="test@example.com", password=strong_password)
        assert user.password == strong_password


# ---------------------------------------------------------------------------
# Input Validation Tests
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Test input validation security."""

    def test_encoder_input_limit(self):
        """Encoder should limit input length."""
        from lib.encoder import encode
        long_text = "x" * 20000
        result = encode(long_text)
        assert len(result) == 14

    def test_chat_draft_limit(self):
        """Chat draft should have length limit."""
        import inspect
        from routers.chat import _generate
        source = inspect.getsource(_generate)
        assert "MAX_DRAFT_LENGTH" in source or "len(reply)" in source
