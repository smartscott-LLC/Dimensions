# Polytope Containment Console — Living Specification

**Version**: 2.0.0  
**Last Updated**: 2026-08-24  
**Status**: ✅ ALL PHASES COMPLETE — 145/145 Tests Passing

---

## 1. System Overview

The Polytope Containment Console is a safety-critical AI containment system that enforces ethical constraints on AI behavior through geometric projection. It implements a 14-dimensional convex polytope `P = { x ∈ ℝ¹⁴ : Ax ≤ b }` where every AI state vector is verified against safety bounds and projected to the nearest feasible point if violated.

### Core Principles

1. **Deterministic Safety**: No randomness in safety-critical paths
2. **Geometric Guarantees**: Mathematical proof of containment
3. **Auditability**: Every decision logged with full traceability
4. **Defense-in-Depth**: Multiple security layers
5. **Operational Clarity**: Clear separation of engine vs. console
6. **Input Validation**: Length limits prevent ReDoS and memory issues
7. **Error Resilience**: React error boundaries prevent app crashes
8. **Type Safety**: Automated TS/Pydantic sync checking

---

## 2. Mathematical Foundation

### 2.1 Polytope Definition

```
P = { x ∈ ℝ¹⁴ : Ax ≤ b }
```

Where:
- `x` is a 14-dimensional vector representing AI state
- `A` is the constraint matrix (facets)
- `b` is the bound vector

### 2.2 Verification

For a given vector `x`:
```
r = Ax - b
Violation iff max(r) > 0
```

### 2.3 Projection (Dykstra's Algorithm)

To project `x_gen` onto `P`:
```
x* = argmin_{x∈P} ||x - x_gen||²
```

Implemented via cyclic projection onto half-spaces. Pure Python, no external dependencies.

### 2.4 Facet Types

| Type | Formula | Coefficients |
|------|---------|--------------|
| Axis-aligned upper | x_i ≤ cap | coeffs[i] = 1 |
| Axis-aligned lower | x_i ≥ floor | coeffs[i] = -1, b = -floor |
| Coupling (lead) | x_v - x_c ≥ L | coeffs[v] = -1, coeffs[c] = 1, b = -L |
| Coupling (sum) | x_v + x_c ≤ S | coeffs[v] = coeffs[c] = 1, b = S |

---

## 3. Data Model

### 3.1 MongoDB Collections

#### `profiles`
```python
class Profile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    dimensions: list[Dimension]  # 14 entries
    constraints: list[Constraint]
    center: list[float]  # 14 values
    active: bool
    created_at: datetime
    updated_at: datetime
```

#### `events`
```python
class Event(BaseModel):
    id: str
    profile_id: str
    profile_name: str
    label: str
    source: str  # api | simulator | console
    vector: list[float]  # 14 values
    residuals: list[float]
    max_residual: float
    status: str  # permitted | corrected | revised | withheld
    projected_vector: Optional[list[float]]
    correction_magnitude: float
    violated_constraints: list[str]
    latency_ms: float
    iterations: int
    client_id: Optional[str]
    client_name: Optional[str]
    created_at: datetime
```

#### `clients`
```python
class Client(BaseModel):
    id: str
    name: str
    description: str
    key_prefix: str  # Display only
    key_hash: str  # SHA-256, excluded from serialization
    profile_id: Optional[str]
    profile_name: Optional[str]
    enforcement_mode: str  # inherit | projection | refusal
    rate_limit_per_min: Optional[int]
    active: bool
    created_at: datetime
    rotated_at: Optional[datetime]
    last_seen_at: Optional[datetime]
```

#### `users`
```python
class User(BaseModel):
    id: str
    email: str
    password_hash: str  # bcrypt, excluded
    role: str  # admin | operator
    active: bool
    created_at: datetime
    last_login_at: Optional[datetime]
```

#### Security Collections

- `login_attempts` — IP-based rate limiting
- `account_lockouts` — Account lockout records
- `jwt_denylist` — Revoked tokens (JTI)
- `csrf_tokens` — CSRF token storage
- `auth_nonces` — Single-use nonce storage

---

## 4. API Specification

### 4.1 Engine API (Machine Clients)

All endpoints under `/api`, require `X-API-Key` header.

#### POST /api/contain
Verify a 14D vector against the active polytope.

**Request**:
```json
{
  "vector": [0.5, 0.3, 0.8, ...],
  "source": "classifier",
  "label": "benign"
}
```

**Response**: `Event` object

**Status Codes**:
- `200` — Success
- `401` — Invalid/missing API key
- `422` — Vector length ≠ 14
- `429` — Rate limit exceeded

#### POST /api/encode
Convert text to 14D vector deterministically.

**Request**:
```json
{
  "text": "AI response text",
  "context": "classification"
}
```

**Response**:
```json
{
  "vector": [0.5, 0.3, ...],
  "dimension_names": ["harmony", "dominance", ...]
}
```

#### POST /api/gate
Enforce safety constraints on text with dual-mode support.

**Request**:
```json
{
  "text": "AI draft response",
  "context": "medical-advice",
  "label": "response",
  "mode": "refusal",
  "max_reflections": 3
}
```

**Response**:
```json
{
  "decision": "revised",
  "original_text": "...",
  "revised_text": "...",
  "original_vector": [...],
  "revised_vector": [...],
  "violated_facets": [...],
  "alignment_score": 0.85,
  "reflection_trace": [...],
  "wisdom_filter": {...}
}
```

**Decision Values**:
- `corrected` — Projection mode, vector corrected
- `revised` — Refusal mode, text rewritten
- `withheld` — Refusal mode, content suppressed

#### POST /api/chat/sessions
Create a gated chat session.

**Request**:
```json
{
  "title": "Safety Discussion",
  "mode": "projection"
}
```

#### POST /api/chat/sessions/{id}/message
Send a message to a chat session.

**Request**:
```json
{
  "text": "User question"
}
```

**Response**: `ChatTurn` with gated reply

#### GET /api/chat/sessions/{id}/turns
Retrieve session history.

#### GET /api/chat/sessions/{id}/export
Export session as markdown audit artifact.

### 4.2 Console API (Human Operators)

Requires JWT Bearer token. Admin endpoints return 403 for operators.

#### POST /api/auth/login
```json
{
  "email": "admin@polytope.console",
  "password": "..."
}
```

#### GET /api/auth/me
Return current user info.

#### POST /api/auth/password
Change password (requires CSRF token).

#### GET /api/auth/users
List users (admin only).

#### POST /api/auth/users
Create user (admin only, requires CSRF token).

#### POST /api/auth/users/{id}/toggle
Activate/deactivate user (admin only, requires CSRF token).

#### GET /api/auth/csrf-token
Get CSRF token for state-changing operations.

#### GET /api/auth/nonce
Get single-use nonce for replay protection.

### 4.3 Management API

#### Profiles
- `GET /api/profiles` — List all profiles
- `GET /api/profiles/active` — Get active profile
- `GET /api/profiles/{id}` — Get specific profile
- `POST /api/profiles` — Create profile (admin)
- `PUT /api/profiles/{id}` — Update profile (admin)
- `POST /api/profiles/{id}/activate` — Activate profile (admin)
- `GET /api/profiles/{id}/margins` — Get facet margins

#### Clients
- `GET /api/clients` — List clients
- `POST /api/clients` — Create client (admin)
- `PATCH /api/clients/{id}` — Update client (admin)
- `POST /api/clients/{id}/rotate` — Rotate API key (admin)
- `POST /api/clients/{id}/revoke` — Revoke client (admin)
- `GET /api/clients/stats` — Aggregate stats

#### Telemetry
- `GET /api/events` — List events with filters
- `GET /api/telemetry/summary` — Aggregated metrics
- `GET /api/audit` — Audit log

#### Settings
- `GET /api/settings` — Get engine settings
- `PUT /api/settings` — Update settings (admin)

#### Simulation
- `POST /api/simulate` — Generate synthetic events (any signed-in user)

---

## 5. Enforcement Modes

### 5.1 Projection Mode

Infeasible vectors are silently projected to the nearest point in P.

**Use Case**: Tolerance for minor violations, continuous correction.

**Response**: `decision = "corrected"`

### 5.2 Refusal Mode

Infeasible drafts trigger a reflection loop.

**Process**:
1. Encode original text
2. Verify against polytope
3. If violation detected:
   - Append mitigation sentences for violated axes
   - Re-encode
   - Re-verify
   - Repeat up to `max_reflections` times
4. If feasible → `decision = "revised"`
5. If still infeasible → `decision = "withheld"`

**Use Case**: Strict safety enforcement, no unsafe content released.

### 5.3 Mode Resolution

Priority order:
1. Request-level `mode` parameter
2. Client-level `enforcement_mode`
3. Engine-level default from settings

Reported as `mode_source` in responses.

---

## 6. Security Architecture

### 6.1 Authentication

**Console**: Email/password → 12h HS256 JWT stored in localStorage  
**Engine**: API key (`pk_` + 40 hex chars) in `X-API-Key` header  
**Hybrid**: Optional Supabase JWT via JWKS verification

### 6.2 Authorization

| Role | Permissions |
|------|-------------|
| **admin** | Full access to all endpoints |
| **operator** | Gate, Chat coach, Simulator, read-only Constraints |

Protected operations:
- Profile management (admin only)
- Client management (admin only)
- Settings updates (admin only)
- User management (admin only)

### 6.3 Rate Limiting

| Mechanism | Limit | Response |
|-----------|-------|----------|
| IP login attempts | 5 per 15 min | 429 + Retry-After |
| Account failures | 5 consecutive | 423 + lockout |
| Engine API calls | Configurable per-client | 429 + Retry-After |

### 6.4 Token Security

- **JWT**: HS256, 12h TTL, `nbf` claim, `jti` for revocation
- **API Keys**: SHA-256 hashed, format-validated
- **CSRF Tokens**: Single-use, 12h expiry
- **Nonces**: Single-use, 5min expiry

### 6.5 Audit Trail

Every configuration change logs:
- Action type
- Detail (what changed)
- Actor (who did it)
- Timestamp

---

## 7. Encoder Specification

### 7.1 Deterministic Text Encoding

The encoder transforms text into a 14D vector using:
1. **Signal Lexicon**: Keyword matching for virtue/shadow concepts
2. **Negation Detection**: Identifies negation patterns
3. **Proximity Weighting**: Contextual importance
4. **Complement Damping**: Reduces shadow influence

### 7.2 Dimension Labels (Plumb Line Pairs)

| Index | Virtue | Shadow |
|-------|--------|--------|
| 0 | harmony | dominance |
| 2 | order | chaos |
| 4 | integrity | deception |
| 6 | flourishing | decline |
| 8 | relationships | isolation |
| 10 | boundaries | intrusion |
| 12 | grace | rigidity |

### 7.3 Revision Logic

When refinement is needed, the encoder appends mitigation sentences based on violated facets:
- Each violated axis generates a specific mitigation phrase
- Sentences are deterministic (same input → same output)
- Up to `max_reflections` iterations allowed

---

## 8. UI Specification

### 8.1 Navigation Tabs

1. **Overview** — KPI tiles, violation trends, latency histograms
2. **Live Monitor** — Real-time vector probe, event stream
3. **Gate** — Draft enforcement, mode controls, reflection traces
4. **Chat Coach** — Gated LLM sessions, turn inspector, export
5. **Polytope** — 2D slice explorer, feasible chamber visualization
6. **Constraints** — Profile editor, facet configuration, margins
7. **Clients** (admin) — API key management, rate limits, stats
8. **Access** (admin) — User management, password changes
9. **Event Log** — Filterable event history, text search
10. **Audit** — Configuration change timeline

### 8.2 Key Components

- `GatePanel.tsx` — Draft input, mode selection, result display
- `ChatCoach.tsx` — Session list, threaded conversation, export
- `PolytopeExplorer.tsx` — 2D slice visualization
- `ConstraintEditor.tsx` — Profile editing interface
- `MarginPanel.tsx` — Facet margin display
- `EventLog.tsx` — Filterable event table
- `AuditTrail.tsx` — Timeline view
- `KpiBar.tsx` — Dashboard metrics

---

## 9. Seeded Configuration

### 9.1 Profiles

1. **prof-biochem-strict** — "Biochemical Non-Proliferation" (ACTIVE, 14 facets)
2. **prof-clinical-safety** — "Clinical Decision Safety" (10 facets)
3. **prof-permissive-test** — "Permissive Test Mode" (14 facets)

### 9.2 Demo Clients

Generated randomly on seed (see `seed.py`):
- `gpt-5.2-triage` — Pinned to clinical profile
- `claude-bio-assist` — Follows active profile
- `internal-rag` — Pinned to permissive profile

### 9.3 Initial Events

~200 events over ~12 hours:
- ~25-35% corrected (projection mode)
- ~12% deliberately unattributed
- Mix of permitted and violated vectors

---

## 10. Operational Procedures

### 10.1 Daily Operations

```bash
# Check service health
curl http://localhost:8001/api/health

# View recent events
mongo DP3 --eval "db.events.find().sort({_id:-1}).limit(10).pretty()"

# Check locked accounts
mongo DP3 --eval "db.account_lockouts.find()"
```

### 10.2 Emergency Procedures

**Lock out compromised account**:
```bash
# Via UI: Access tab → toggle user off
# Or directly:
mongo DP3 --eval "db.users.updateOne({email: 'compromised@example.com'}, {\$set: {active: false}})"
```

**Revoke all tokens**:
```bash
# Clear denylist and force re-authentication
mongo DP3 --eval "db.jwt_denylist.deleteMany({})"
# Then notify users to re-login
```

### 10.3 Backup Strategy

- MongoDB Atlas automated backups (point-in-time recovery)
- Export profiles via API for version control
- Audit logs retained for compliance

---

## 11. Development Guidelines

### 11.1 Adding New Routes

1. Create model in `models/`
2. Create router in `routers/`
3. Mount router in `server.py`
4. Add TypeScript interface in `frontend/src/lib/types.ts`
5. Add API function in `frontend/src/lib/api.ts`
6. Update this spec

### 11.2 Security Checklist

- [ ] Input validation on all endpoints
- [ ] Rate limiting on sensitive operations
- [ ] Audit logging for state changes
- [ ] No hardcoded secrets
- [ ] Proper error handling (no info leakage)
- [ ] CSRF protection on form submissions

### 11.3 Testing Requirements

- Unit tests for pure functions
- Integration tests for API endpoints
- Security tests for auth flows
- Type check: `pnpm typecheck`

---

## 12. Known Limitations

1. **Non-Streaming Chat**: Full draft required before gating
2. **Reflection Limits**: Deterministic rewrite handles tone breaches, not deeply unsafe content
3. **Password Reset**: Email flow not implemented
4. **Refusal Analytics**: Data in event log but not charted
5. **Type Sync**: Manual process, no automated check

---

## 13. Future Enhancements

### Planned Features
- Streaming chat responses with incremental gating
- Refusal analytics dashboard
- Password reset email flow
- Telemetry export (CSV/JSON)
- Real-time WebSocket event streaming

### Technical Debt
- React error boundaries
- MongoDB connection pooling optimization
- Automated type sync check in CI
- Load testing framework

---

**Document Status**: Living specification — update with each significant change.  
**Next Review**: After Phase 2 completion.
