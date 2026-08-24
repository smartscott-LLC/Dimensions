# Security Documentation

**Classification**: Internal Use Only  
**Last Updated**: 2026-08-24

---

## 1. Security Architecture

### 1.1 Defense-in-Depth Layers

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| **Network** | TLS for MongoDB, CORS policy | Encrypt data in transit |
| **Authentication** | JWT + Supabase hybrid | Verify identity |
| **Authorization** | Role-based (admin/operator) | Enforce access controls |
| **Rate Limiting** | IP-based + account lockout | Prevent brute force |
| **Input Validation** | Pydantic + regex | Prevent injection |
| **Audit Trail** | MongoDB collections | Track all changes |
| **Token Security** | Revocation + nonces | Prevent replay |

### 1.2 Cryptographic Standards

| Component | Algorithm | Key Size | Notes |
|-----------|-----------|----------|-------|
| **JWT Signing** | HS256 | 256-bit | HMAC-SHA256 |
| **Password Hashing** | bcrypt | N/A | Cost factor 12 |
| **API Key Hashing** | SHA-256 | 256-bit | One-way hash |
| **Token Revocation** | MongoDB denylist | N/A | JTI-based |

---

## 2. Authentication System

### 2.1 JWT Token Structure

```json
{
  "sub": "user@example.com",
  "role": "admin",
  "jti": "550e8400-e29b-41d4-a716-446655440000",
  "iat": 1697000000,
  "exp": 1697043200,
  "nbf": 1697000000
}
```

- **sub**: User email
- **role**: admin or operator
- **jti**: Unique token ID for revocation
- **exp**: Expiration (12 hours)
- **nbf**: Not before (prevents replay)

### 2.2 API Key Format

```
pk_[40 hex characters]
```

Example: `pk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0`

- Generated via `secrets.token_hex(20)`
- Hashed with SHA-256 before storage
- Returned plaintext only at creation/rotation

### 2.3 Supabase Integration

Supports hybrid authentication:
- Custom JWT (primary)
- Supabase JWT (optional, via JWKS)

Environment variables:
```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_JWKS_URL=https://xxx.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_SECRET_KEY=sb_secret_xxx
```

---

## 3. Rate Limiting

### 3.1 Login Rate Limiting

| Parameter | Value |
|-----------|-------|
| **Window** | 15 minutes |
| **Max Attempts** | 5 per IP |
| **Response** | 429 Too Many Requests |
| **Header** | `Retry-After: 900` |

### 3.2 Account Lockout

| Parameter | Value |
|-----------|-------|
| **Threshold** | 5 consecutive failures |
| **Lockout Duration** | 1 hour |
| **Response** | 423 Service Unavailable |
| **Tracking** | MongoDB `account_lockouts` collection |

### 3.3 Engine API Rate Limiting

| Parameter | Value |
|-----------|-------|
| **Window** | 60 seconds |
| **Default** | Configurable in EngineSettings |
| **Per-Client** | Override via client configuration |
| **Response** | 429 with `X-RateLimit-*` headers |

---

## 4. CSRF Protection

### 4.1 Token Flow

1. Frontend requests token: `GET /api/auth/csrf-token`
2. Token stored in memory (not localStorage)
3. Token sent with state-changing requests: `POST /api/auth/password`, etc.
4. Backend validates and consumes token

### 4.2 Token Properties

- Single-use (consumed after validation)
- 12-hour expiry
- Bound to user session
- Stored in MongoDB `csrf_tokens` collection

---

## 5. Nonce System

### 5.1 Purpose

Prevents replay attacks by requiring fresh tokens for sensitive operations.

### 5.2 Flow

1. Request nonce: `GET /api/auth/nonce`
2. Use nonce in request header: `X-Nonce: <value>`
3. Backend validates and consumes nonce
4. Nonce cannot be reused

### 5.3 Properties

- 5-minute expiry
- Single-use
- Stored in MongoDB `auth_nonces` collection

---

## 6. Data Protection

### 6.1 Secrets Management

| Secret | Storage | Rotation |
|--------|---------|----------|
| **JWT_SECRET** | `.env` file | Manual rotation |
| **MongoDB Password** | `.env` file | Atlas console |
| **API Keys** | SHA-256 hash | Via API |
| **Passwords** | bcrypt hash | Via password change |

### 6.2 Sensitive Data Handling

- **Passwords**: Never logged, never returned in responses
- **API Keys**: Only shown at creation/rotation
- **Token Secrets**: Never logged
- **Audit Logs**: Retain for compliance

---

## 7. Security Testing

### 7.1 Test Suite

Run security tests:
```bash
cd backend && pytest tests/test_auth_security.py -v
```

**Current Status**: 33/33 tests passing

### 7.2 Test Coverage

| Category | Tests | Coverage |
|----------|-------|----------|
| Token Revocation | 5 | ✅ |
| JWT Validation | 4 | ✅ |
| Rate Limiting | 8 | ✅ |
| Account Lockout | 3 | ✅ |
| CSRF Protection | 5 | ✅ |
| Code Quality | 3 | ✅ |

### 7.3 Security Scanning

```bash
# Check for hardcoded secrets
grep -r "password\|secret\|key" --include="*.py" | grep -v ".env" | grep -v "test_"

# Verify .env not in git
git log --all --full-history -- backend/.env

# Check for TODO security items
grep -r "TODO.*security\|FIXME.*security" --include="*.py"
```

---

## 8. Incident Response

### 8.1 Compromised Account

1. Disable account immediately
2. Revoke all active tokens
3. Review audit log for suspicious activity
4. Reset password
5. Notify affected user

### 8.2 Brute Force Attack

1. Block offending IPs via firewall
2. Review `login_attempts` collection
3. Check for locked accounts
4. Monitor for distributed attacks

### 8.3 API Key Leak

1. Revoke compromised key immediately
2. Generate new key for client
3. Review associated events
4. Assess scope of exposure

---

## 9. Compliance

### 9.1 Audit Requirements

All system changes are logged:
- Who made the change
- What changed
- When it changed
- Previous/new values

### 9.2 Retention Policies

| Data | Retention |
|------|-----------|
| **Audit Logs** | Indefinite |
| **Event Logs** | 90 days |
| **Login Attempts** | 24 hours |
| **Account Lockouts** | Auto-expiry |
| **CSRF Tokens** | 12 hours |
| **Nonces** | 5 minutes |

### 9.3 Data Privacy

- No PII in event logs
- Email addresses stored for authentication only
- API keys hashed, not encrypted
- Session tokens have automatic expiry

---

## 10. Known Security Considerations

### 10.1 JWT in localStorage

**Risk**: XSS could steal tokens  
**Mitigation**: 
- HttpOnly cookies recommended for future
- CSRF protection added as defense-in-depth
- Short token lifetime (12 hours)

### 10.2 Supabase JWT Verification

**Status**: Implemented but optional  
**Prerequisites**: 
- Supabase project configured
- JWKS endpoint accessible
- RLS enabled

### 10.3 MongoDB Connection

**Risk**: Connection string in `.env`  
**Mitigation**:
- TLS enforced in connection string
- Never commit `.env` to git
- Use secret management in production

---

## 11. Security Roadmap

### Completed (Phase 1)
- [x] JWT secret validation
- [x] Rate limiting on authentication
- [x] Account lockout
- [x] Token revocation
- [x] API key format validation
- [x] CSRF protection
- [x] Replay attack prevention
- [x] Random demo key generation

### Planned (Phase 2)
- [ ] Password complexity requirements
- [ ] ReDoS protection in encoder
- [ ] Comprehensive input validation
- [ ] Complete audit attribution

### Future Considerations
- [ ] HttpOnly cookie authentication
- [ ] MFA support
- [ ] IP allowlisting
- [ ] Security event monitoring/alerting
- [ ] Automated security scanning in CI

---

**Document Status**: Current as of Phase 1 completion  
**Review Cycle**: Quarterly or after significant changes
