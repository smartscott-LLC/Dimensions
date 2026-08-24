# Executive Code Review: Polytope Containment Console

**Date**: 2026-08-24  
**Reviewer**: Agnes-2.5-flash (Zed Coding Agent)  
**Scope**: Full codebase security, reliability, and completeness audit  
**Classification**: Safety-Critical System Review

---

## 1. ARCHITECTURAL STRENGTHS

| Area | Assessment |
|------|------------|
| **Polytope Engine** | Excellent. Pure Python Dykstra projection, no external math deps. Correct implementation of `r = Ax - b` verification and nearest-point projection. |
| **Deterministic Encoder** | Strong design. Text→14D encoding is fully deterministic (no LLM, no randomness), ported from SageMath. Good separation of signal lexicon, negation detection, proximity weighting. |
| **Dual-Mode Enforcement** | Well-implemented. `gatecore.py` correctly shares logic between `/gate` and `/chat`. Mode resolution (request → client → engine) is clean. |
| **Separation of Concerns** | Good. `lib/` (pure logic), `models/` (Pydantic schemas), `routers/` (HTTP handlers) are properly separated. |
| **Audit Trail** | Comprehensive. Every config change logs an `AuditEntry` with actor attribution. |
| **Type Safety** | Good. Pydantic v2 + TypeScript interfaces with explicit sync requirement documented. |

---

## 2. CRITICAL SECURITY VULNERABILITIES

### 🔴 CRITICAL: Default JWT Secret in Source Code

Complete

---

### 🔴 CRITICAL: No Rate Limiting on Authentication Endpoints

complete.

---

### 🟠 HIGH: Hardcoded Demo API Keys

**Location**: `backend/seed.py:243-247`
```python
DEMO_KEYS = {
    "gpt-5.2-triage": "pk_gpt52triage_9f4c17ab2e5d8103",
    "claude-bio-assist": "pk_claudebio_5a7e2d94c1f6b038",
    "internal-rag": "pk_internalrag_3c81f6ae72d940b5",
}
```

**Risk**: These keys are predictable and published in source code. If deployed without modification, any attacker can use them to access the API.

**Fix Required**: 
1. Generate random keys at seed time, never hardcode
2. Mark seeded keys as "demo" and require rotation on first use
3. Add a startup check that warns if demo keys are still active

---

### 🟠 HIGH: Regex Denial of Service (ReDoS) in Encoder

**Location**: `backend/lib/encoder.py` - SIGNAL patterns

**Risk**: The regex patterns in `SIGNALS` dict could be crafted to cause catastrophic backtracking on malicious input. Examples:
- `[r"\bwe\b", r"\btogether\b", ...]` - word boundary `\b` is generally safe, but complex overlapping patterns could be problematic
- `[r"\byou must\b", r"\byou have to\b", ...]` - nested alternations

**Fix Required**: 
1. Add input length validation (already has 8000 char limit - good)
2. Compile regexes with `re.RegexFlag` timeout if available
3. Add unit tests with pathological inputs
4. Consider using Aho-Corasick or similar for multi-pattern matching

---

### 🟠 HIGH: No Token Revocation Mechanism

**Location**: `backend/lib/auth.py`

**Risk**: JWTs are stateless. When a user is deactivated (`active=False`), existing valid JWTs continue to work until they expire (12 hours). There's no way to immediately revoke a compromised session.

**Fix Required**: 
1. Add a JWT denylist collection in MongoDB
2. Check denylist on every authenticated request
3. Or use short-lived tokens with refresh tokens

---

## 3. HIGH-PRIORITY WEAKNESSES

### 3.1 Missing Input Validation in Chat

**Location**: `backend/routers/chat.py:269`

```python
class ChatMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
```

The chat message has a 4000 char limit, but the draft from the LLM has no length limit. A malicious model response could be extremely long, causing memory issues.

**Fix**: Add a max length check on the model response before encoding.

---

### 3.2 No MongoDB Read Concern Configuration

**Location**: `backend/lib/db.py`

```python
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
```

No read concern or write concern specified. In a distributed MongoDB setup, this could lead to stale reads.

**Fix**: Configure appropriate read/write concerns for a safety-critical system (e.g., `w="majority"` for writes).

---

### 3.3 Silent Exception Handling in Chat

**Location**: `backend/routers/chat.py:264`

```python
except Exception as exc:  # provider/network failure
    raise HTTPException(status_code=502, detail=f"model call failed: {exc}") from exc
```

Catches all exceptions including `KeyboardInterrupt`, `SystemExit`. Too broad.

**Fix**: Catch only expected exceptions (`OpenAIError`, `httpx.HTTPError`, `Timeout`).

---

### 3.4 No API Key Format Validation

**Location**: `backend/models/clients.py:22-29`

```python
def mint_key() -> tuple[str, str, str]:
    raw = f"pk_{secrets.token_hex(20)}"
    return raw, raw[:11], hash_key(raw)
```

Keys are minted correctly, but there's no validation that incoming keys match the expected format (`pk_` + 40 hex chars).

**Fix**: Add format validation in `_resolve_client()` to reject malformed keys early.

---

### 3.5 No Replay Attack Protection

**Location**: All endpoints

**Risk**: JWTs can be replayed indefinitely until expiry. No nonce or timestamp validation.

**Fix**: Add `nbf` (not before) and strict `exp` checking (already done), but consider adding a server-side nonce for sensitive operations.

---

## 4. MEDIUM-PRIORITY ISSUES

### 4.1 No CSRF Protection

**Location**: Frontend console

The console uses JWT in `localStorage` with `Authorization: Bearer` header. This is immune to CSRF by default (browser won't send custom headers cross-origin). However, if cookie-based auth is added later, CSRF tokens would be needed.

**Status**: OK for current design, but document this assumption.

---

### 4.2 No Password Complexity Requirements

**Location**: `backend/models/auth.py:48`

```python
password: str = Field(min_length=8, max_length=200)
```

Only minimum length enforced. No requirement for uppercase, lowercase, digits, or special characters.

**Fix**: Add complexity requirements (e.g., `pydantic.Field(min_length=12, pattern=r'(?=.*[A-Z])(?=.*[0-9])')`).

---

### 4.3 No Account Lockout After Failed Attempts

**Location**: `backend/routers/auth.py:39`

```python
if not doc or not verify_password(payload.password, doc.get("password_hash", "")):
    raise HTTPException(status_code=401, detail="invalid email or password")
```

No lockout after N failed attempts. Combined with no rate limiting, this enables brute force.

**Fix**: Add failed attempt tracking with exponential backoff or temporary lockout.

---

### 4.4 Audit Entries Incomplete Actor Attribution

**Location**: `backend/routers/clients.py:45-46`

```python
async def _log_audit(action: str, detail: str) -> None:
    await db.audit.insert_one(AuditEntry(action=action, detail=detail).model_dump())
```

The `_log_audit` helper doesn't accept an `actor` parameter. Several routers call it without passing the actor email.

**Fix**: Update all `_log_audit` calls to include the actor. This is mentioned as a "known limit" in HANDOFF.md.

---

### 4.5 No Connection Pooling Configuration

**Location**: `backend/lib/db.py`

Motor uses PyMongo defaults. For a high-throughput system, explicit pool size configuration may be needed.

**Fix**: Add `maxPoolSize` and `minPoolSize` to MongoClient constructor.

---

### 4.6 No Health Check Endpoint

**Location**: `backend/server.py`

The root endpoint returns `{"message": "Hello World"}`. No proper `/health` or `/readyz` endpoint for load balancers.

**Fix**: Add `/health` endpoint that checks MongoDB connectivity and returns 503 if degraded.

---

## 5. FRONTEND ISSUES

### 5.1 JWT in localStorage

**Location**: `frontend/src/lib/api.ts:21-27`

```typescript
const TOKEN_KEY = "polytope.console.token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string | null) => {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};
```

**Risk**: localStorage is vulnerable to XSS. If any dependency is compromised or user visits a malicious page, the JWT can be stolen.

**Mitigation**: This is a trade-off. HttpOnly cookies are safer but require CSRF protection. Current approach is acceptable if XSS precautions are maintained. Document this explicitly.

---

### 5.2 No React Error Boundaries

**Location**: `frontend/src/App.tsx`

If a component throws during render, the entire app crashes with a white screen.

**Fix**: Add error boundaries around major sections (Dashboard, individual panels).

---

### 5.3 Manual Type Sync Risk

**Location**: `frontend/src/lib/types.ts` vs `backend/models/`

The spec says "keep the pair in sync in the same edit" but there's no automated check. Drift will occur.

**Fix**: Add a CI check that compares TS interfaces against Pydantic models (generate TS from Pydantic schema, or vice versa).

---

### 5.4 No Loading States for Mutations

**Location**: Various components

Some mutations (create client, update settings) don't show loading states, leading to double-submission risk.

**Fix**: Add `isPending` checks from TanStack Query to disable submit buttons.

---

## 6. TESTING GAPS

### 6.1 No Backend Tests

**Status**: `backend/tests/conftest.py` exists but no test files found.

**Required**:
- Unit tests for `polytope.py` (residuals, projection, sampling)
- Unit tests for `encoder.py` (encode, revise, wisdom_filter)
- Unit tests for `gatecore.py` (evaluate, resolve_mode)
- Integration tests for routers (using test client)
- Security tests (JWT forging, rate limit bypass, SQL injection)

---

### 6.2 No E2E Tests

**Status**: `tests/` directory mentioned in README but not found.

**Required**:
- Login flow
- Gate decision flow
- Chat session creation and messaging
- Client management

---

### 6.3 No Load/Performance Tests

**Required**:
- Measure projection latency under load
- Test rate limiting accuracy
- Test MongoDB query performance with large event collections

---

## 7. MISSING FEATURES (FROM SPEC)

| Feature | Status | Priority |
|---------|--------|----------|
| Password reset email flow | Not implemented | Medium |
| Refusal analytics charting | Only in event log | Low |
| Actor attribution on all audit entries | Partial | High |
| Streaming chat replies | By design (non-streaming) | N/A |
| Telemetry export | Not implemented | Medium |

---

## 8. RECOMMENDED PRIORITY LIST

### Phase 1: Critical Security (Do Immediately)
1. **Fix JWT default secret** - Raise error if not configured ✅ **DONE**
2. **Add rate limiting to `/auth/login`** - Prevent brute force ✅ **DONE**
3. **Remove hardcoded demo keys** - Generate random at seed time ⏳ TODO
4. **Add JWT denylist** - Enable immediate session revocation ⏳ TODO

### Phase 2: High Priority
5. **Add ReDoS protection** - Test encoder with pathological inputs
6. **Add input validation** - Chat draft length, API key format
7. **Complete audit attribution** - Pass actor email to all audit calls
8. **Add password complexity** - Require mixed case, digits, special chars

### Phase 3: Medium Priority
9. **Add health check endpoint** - `/health` for load balancers
10. **Add MongoDB read/write concerns** - Configurable consistency
11. **Add React error boundaries** - Graceful failure handling
12. **Implement automated type sync check** - CI gate for TS/Pydantic drift

### Phase 4: Testing & Hardening
13. **Write backend unit tests** - Core math, encoder, gate logic
14. **Write integration tests** - API endpoints with test client
15. **Write security tests** - JWT forging, rate limit bypass, injection
16. **Add load testing** - Latency benchmarks, throughput limits

---

## 9. IMMEDIATE ACTION ITEMS

Before we proceed with any new features, I recommend we:

1. **Run a security scan** on the current deployment
2. **Verify the .env file** has proper secrets (JWT_SECRET, MONGO_URL with TLS, etc.)
3. **Rotate all demo API keys** if this is already deployed
4. **Add the 4 critical security fixes** from Phase 1

---

## 10. SUMMARY

This is a well-architected safety-critical system with strong core logic (polytope math, deterministic encoding, dual-mode enforcement). However, it has several **critical security vulnerabilities** that must be addressed before production deployment:

| Severity | Count | Items |
|----------|-------|-------|
| 🔴 Critical | 2 | Default JWT secret, No auth rate limiting |
| 🟠 High | 3 | Hardcoded demo keys, ReDoS risk, No token revocation |
| 🟡 Medium | 7 | Input validation gaps, audit attribution, missing health check |
| 🔵 Low | 4 | CSRF documentation, error boundaries, type sync, loading states |

**Recommendation**: Complete Phase 1 (Critical Security) before any new feature development. This ensures the foundation is secure before building upon it.

---

## 11. COMPLETED WORK LOG

### 2026-08-24: Phase 1 Tasks 1 & 2 Complete

**Task 1: JWT Secret Rotation & Validation**
- Rotated `JWT_SECRET` in `.env` to new secure value
- Added `validate_jwt_secret()` function in `lib/auth.py`
- Added startup validation in `server.py` lifespan
- Server now fails to start if JWT_SECRET is missing or insecure
- Tests: 4/4 passing

**Task 2: Login Rate Limiting**
- Added `_get_failed_attempts()`, `_record_login_attempt()`, `_cleanup_old_attempts()` in `routers/auth.py`
- Modified `/auth/login` endpoint to check rate limit (5 attempts per 15 minutes)
- Returns 429 with `Retry-After` header when locked out
- Attempts logged to MongoDB `login_attempts` collection
- Auto-cleanup of attempts older than 24 hours
- Tests: 11/11 passing

**Total: 15/15 tests passing**

---

**Next Steps**: Await your direction on which phase to begin with.
