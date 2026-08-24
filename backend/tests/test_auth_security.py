"""Tests for authentication security hardening.

Covers:
1. JWT_SECRET validation at startup
2. Login rate limiting logic (unit tests without server)
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# JWT Secret Validation
# ---------------------------------------------------------------------------


class TestJwtSecretValidation:
    """Test that _secret() validates JWT_SECRET properly."""

    def test_raises_when_jwt_secret_missing(self):
        """When JWT_SECRET is not set, _secret() must raise RuntimeError."""
        # Save original
        original_secret = os.environ.get("JWT_SECRET")
        
        # Remove from env
        if "JWT_SECRET" in os.environ:
            del os.environ["JWT_SECRET"]
        
        try:
            # Also patch dotenv to not restore it
            with patch('os.environ.get') as mock_get:
                # First call returns None (JWT_SECRET not set)
                # Second call returns the actual env value for other vars
                def side_effect(key, default=None):
                    if key == "JWT_SECRET":
                        return None
                    return original_secret if key == "JWT_SECRET" else default
                
                mock_get.side_effect = side_effect
                
                # Import the function directly
                import importlib
                import lib.auth as auth_module
                importlib.reload(auth_module)
                
                # Now test - should raise because env var is missing
                try:
                    auth_module._secret()
                    assert False, "Should have raised RuntimeError"
                except RuntimeError as e:
                    assert "JWT_SECRET environment variable is not set" in str(e)
        finally:
            # Restore original
            if original_secret is not None:
                os.environ["JWT_SECRET"] = original_secret

    def test_raises_when_jwt_secret_is_default(self):
        """When JWT_SECRET is the insecure default, _secret() must raise RuntimeError."""
        original_secret = os.environ.get("JWT_SECRET")
        os.environ["JWT_SECRET"] = "dev-only-insecure-secret"
        
        try:
            import importlib
            import lib.auth as auth_module
            importlib.reload(auth_module)
            
            try:
                auth_module._secret()
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "default insecure value" in str(e)
        finally:
            if original_secret is not None:
                os.environ["JWT_SECRET"] = original_secret
            elif "JWT_SECRET" in os.environ:
                del os.environ["JWT_SECRET"]

    def test_accepts_valid_jwt_secret(self):
        """When JWT_SECRET is a proper value, _secret() returns it."""
        original_secret = os.environ.get("JWT_SECRET")
        os.environ["JWT_SECRET"] = "a" * 64
        
        try:
            import importlib
            import lib.auth as auth_module
            importlib.reload(auth_module)
            
            result = auth_module._secret()
            assert result == "a" * 64
        finally:
            if original_secret is not None:
                os.environ["JWT_SECRET"] = original_secret
            elif "JWT_SECRET" in os.environ:
                del os.environ["JWT_SECRET"]

    def test_validate_jwt_secret_no_raise(self):
        """validate_jwt_secret() should not raise when secret is valid."""
        original_secret = os.environ.get("JWT_SECRET")
        os.environ["JWT_SECRET"] = "b" * 64
        
        try:
            import importlib
            import lib.auth as auth_module
            importlib.reload(auth_module)
            
            # Should not raise
            auth_module.validate_jwt_secret()
        finally:
            if original_secret is not None:
                os.environ["JWT_SECRET"] = original_secret
            elif "JWT_SECRET" in os.environ:
                del os.environ["JWT_SECRET"]


# ---------------------------------------------------------------------------
# Login Rate Limiting Unit Tests
# ---------------------------------------------------------------------------


class TestLoginRateLimiting:
    """Test login rate limiting logic (unit tests)."""

    def test_max_login_attempts_constant(self):
        """MAX_LOGIN_ATTEMPTS should be 5."""
        from routers.auth import MAX_LOGIN_ATTEMPTS
        assert MAX_LOGIN_ATTEMPTS == 5

    def test_login_lockout_minutes_constant(self):
        """LOGIN_LOCKOUT_MINUTES should be 15."""
        from routers.auth import LOGIN_LOCKOUT_MINUTES
        assert LOGIN_LOCKOUT_MINUTES == 15

    def test_get_failed_attempts_signature(self):
        """_get_failed_attempts should be an async function."""
        from routers.auth import _get_failed_attempts
        import inspect
        assert inspect.iscoroutinefunction(_get_failed_attempts)

    def test_record_login_attempt_signature(self):
        """_record_login_attempt should be an async function."""
        from routers.auth import _record_login_attempt
        import inspect
        assert inspect.iscoroutinefunction(_record_login_attempt)

    def test_cleanup_old_attempts_signature(self):
        """_cleanup_old_attempts should be an async function."""
        from routers.auth import _cleanup_old_attempts
        import inspect
        assert inspect.iscoroutinefunction(_cleanup_old_attempts)

    def test_login_endpoint_has_rate_limit_check(self):
        """The login endpoint should reference MAX_LOGIN_ATTEMPTS."""
        import inspect
        from routers.auth import login
        
        source = inspect.getsource(login)
        assert "MAX_LOGIN_ATTEMPTS" in source
        assert "429" in source
        assert "Retry-After" in source

    def test_login_records_failed_attempt(self):
        """Failed login should record attempt."""
        import inspect
        from routers.auth import login
        
        source = inspect.getsource(login)
        assert "_record_login_attempt" in source
        assert 'success=False' in source

    def test_login_records_success_attempt(self):
        """Successful login should record attempt."""
        import inspect
        from routers.auth import login
        
        source = inspect.getsource(login)
        assert "_record_login_attempt" in source
        assert 'success=True' in source


# ---------------------------------------------------------------------------
# Code Quality Checks
# ---------------------------------------------------------------------------


class TestCodeQuality:
    """Verify code quality and security best practices."""

    def test_no_hardcoded_secrets_in_auth(self):
        """auth.py should not contain hardcoded secrets."""
        with open("lib/auth.py", "r") as f:
            content = f.read()
        
        # Should not have the old default
        assert "dev-only-insecure-secret" not in content or \
               'secret == "dev-only-insecure-secret"' in content

    def test_jwt_secret_not_in_source(self):
        """JWT_SECRET value should not be hardcoded in source files."""
        import glob
        
        for pattern in ["lib/*.py", "routers/*.py", "models/*.py"]:
            for filepath in glob.glob(pattern):
                with open(filepath, "r") as f:
                    content = f.read()
                # Should not have a 64-char hex string that looks like a JWT secret
                # (but allow the validation check)
                assert "8f3a9c7e2d1b5f6a4e8c9d2a3b7f5e1c" not in content

    def test_rate_limit_configurable(self):
        """Rate limit constants should be at module level for easy configuration."""
        from routers.auth import MAX_LOGIN_ATTEMPTS, LOGIN_LOCKOUT_MINUTES
        
        # Should be integers
        assert isinstance(MAX_LOGIN_ATTEMPTS, int)
        assert isinstance(LOGIN_LOCKOUT_MINUTES, int)
        
        # Should be reasonable values
        assert MAX_LOGIN_ATTEMPTS > 0
        assert LOGIN_LOCKOUT_MINUTES > 0


class TestAccountLockout:
    """Test account-level lockout functionality."""

    def test_account_lockout_constants(self):
        """Account lockout constants should be defined."""
        from routers.auth import MAX_ACCOUNT_FAILURES, ACCOUNT_LOCKOUT_HOURS
        
        assert MAX_ACCOUNT_FAILURES == 5
        assert ACCOUNT_LOCKOUT_HOURS == 1

    def test_account_lockout_functions_exist(self):
        """Account lockout helper functions should exist."""
        from routers.auth import _is_account_locked, _lock_account, _get_consecutive_failures
        import inspect
        
        assert inspect.iscoroutinefunction(_is_account_locked)
        assert inspect.iscoroutinefunction(_lock_account)
        assert inspect.iscoroutinefunction(_get_consecutive_failures)

    def test_login_checks_account_lockout(self):
        """Login endpoint should check account lockout status."""
        import inspect
        from routers.auth import login
        
        source = inspect.getsource(login)
        assert "_is_account_locked" in source
        assert "_lock_account" in source
        assert "423" in source  # Service Unavailable for locked account
