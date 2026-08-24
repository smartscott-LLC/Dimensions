# Polytope Containment Console

**Government-Grade AI Safety Containment System**  
**Classification**: Safety-Critical | **TRL**: 7 (Tested on Silicon)  
**Patents Pending**: 5+ USPTO applications filed

---

## Overview

A 14-dimensional geometric constraint engine that guarantees AI outputs remain within defined ethical/safety bounds. The system implements a convex polytope `P = { x ∈ ℝ¹⁴ : Ax ≤ b }` where every AI state vector is verified and projected to the nearest feasible point.

### Core Components

| Component | Description |
|-----------|-------------|
| **Polytope Engine** | Pure Python Dykstra projection, no external math dependencies |
| **Deterministic Encoder** | Text→14D encoding ported from SageMath (no LLM, no randomness) |
| **Dual-Mode Enforcement** | Projection (corrects) or Refusal (reflects/withholds) |
| **Coaching Chat** | Gated LLM sessions with real-time safety inspection |
| **Operations Console** | Web UI for monitoring, configuration, and administration |

### Security Architecture

- **Dual Authentication**: Custom JWT (12h TTL) + Supabase JWT (JWKS verification)
- **Rate Limiting**: IP-based (5 attempts/15min) + Account lockout (5 failures→1hr)
- **Token Revocation**: MongoDB denylist with JTI tracking
- **CSRF Protection**: Token validation on state-changing operations
- **Replay Attack Prevention**: `nbf` claims + single-use nonces
- **API Key Security**: Format validation (`pk_` + 40 hex chars) + SHA-256 hashing

---

## Quick Start

### Prerequisites

- Python 3.12+ with virtual environment
- MongoDB (cloud Atlas connection string required)
- Node.js 24.x for frontend

### Installation

```bash
# Backend
cd backend
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
pnpm install
```

### Configuration

Create `backend/.env` with the following variables:

```bash
MONGO_URL=mongodb://user:pass@cluster.mongodb.net/dbname
DB_NAME=DP3
CORS_ORIGINS="*"
JWT_SECRET=<64-char-hex-secret>
ADMIN_EMAIL=admin@polytope.console
ADMIN_PASSWORD=<strong-password>
MODEL_API_KEY=<openai-compatible-key>
MODEL_API_URL=https://api.example.com/v1
MODEL_NAME=agnes-2.5-flash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_JWKS_URL=https://xxx.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_SECRET_KEY=sb_secret_xxx
```

### Running

```bash
# Backend (port 8001)
cd backend && uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Frontend (port 3000)
cd frontend && pnpm dev

# Reseed demo data
cd backend && python seed.py
```

### Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@polytope.console` | `Prussian#42Blue` |
| Operator | `ops@polytope.console` | `Khaki#514Ops` |

**⚠️ IMPORTANT**: Change these credentials before production use.

---

## Architecture

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Backend** | FastAPI + Motor (async MongoDB) + Pydantic v2 |
| **Frontend** | Vite + React 19 + TypeScript + Tailwind v4 |
| **Database** | MongoDB (Atlas cloud) |
| **Auth** | JWT (HS256) + Supabase (JWKS) |
| **Security** | bcrypt, SHA-256, CSRF tokens, Nonces |

### Directory Structure

```
Dimensions/
├── backend/                    # FastAPI application
│   ├── server.py              # FastAPI app bootstrap
│   ├── lib/
│   │   ├── auth.py            # JWT, revocation, Supabase verification
│   │   ├── csrf.py            # CSRF token management
│   │   ├── encoder.py         # Text→14D deterministic encoding
│   │   ├── gatecore.py        # Dual-mode enforcement logic
│   │   ├── polytope.py        # Dykstra projection, sampling
│   │   └── ratelimit.py       # Sliding window rate limiting
│   ├── models/                # Pydantic schemas
│   ├── routers/               # API route handlers
│   ├── tests/                 # pytest test suite
│   └── seed.py                # Demo data seeding
├── frontend/                   # React + TypeScript
│   └── src/
│       ├── lib/
│       │   ├── api.ts         # Typed fetch layer
│       │   ├── auth.tsx       # Auth provider/hooks
│       │   └── types.ts       # TypeScript interfaces
│       └── components/
└── memory/                     # Documentation
    ├── SPEC.md               # Living specification
    ├── EXECUTIVE_REVIEW.md   # Security audit report
    └── HANDOFF.md            # Operational handoff
```

### MongoDB Collections

| Collection | Purpose |
|------------|---------|
| `profiles` | Polytope configurations (constraints, dimensions) |
| `events` | Verification telemetry (vectors, residuals, decisions) |
| `audit` | Configuration change log |
| `clients` | API key management |
| `users` | Console accounts |
| `login_attempts` | IP rate limiting tracking |
| `account_lockouts` | Account lockout records |
| `jwt_denylist` | Revoked tokens |
| `csrf_tokens` | CSRF token storage |
| `auth_nonces` | Single-use nonce storage |

---

## API Reference

### Engine API (Machine Clients)

Requires `X-API-Key` header. All endpoints under `/api`.

```bash
# Verify a 14D vector
POST /api/contain
Body: { "vector": [0.5, 0.3, ...], "source": "system", "label": "test" }

# Encode text to 14D vector
POST /api/encode
Body: { "text": "AI response text", "context": "classification" }

# Gate text with enforcement
POST /api/gate
Body: { "text": "...", "mode": "refusal", "max_reflections": 3 }

# Create chat session
POST /api/chat/sessions
Body: { "title": "Safety Discussion", "mode": "projection" }

# Send message to chat session
POST /api/chat/sessions/{id}/message
Body: { "text": "User question" }
```

### Console API (Human Operators)

Requires JWT Bearer token. Admin-only endpoints return 403 for operators.

```bash
# Login
POST /api/auth/login
Body: { "email": "...", "password": "..." }

# Get current user
GET /api/auth/me

# Change password
POST /api/auth/password
Headers: { "X-CSRF-Token": "..." }
Body: { "current_password": "...", "new_password": "..." }

# List users (admin)
GET /api/auth/users

# Create user (admin)
POST /api/auth/users
Headers: { "X-CSRF-Token": "..." }
Body: { "email": "...", "password": "...", "role": "operator" }
```

### Telemetry & Management

```bash
# Get telemetry summary
GET /api/telemetry/summary

# List events
GET /api/events?limit=100&status=corrected

# List audit entries
GET /api/audit?limit=50

# Manage profiles
GET /api/profiles
POST /api/profiles
PUT /api/profiles/{id}
POST /api/profiles/{id}/activate

# Manage clients
GET /api/clients
POST /api/clients
PATCH /api/clients/{id}
POST /api/clients/{id}/rotate
POST /api/clients/{id}/revoke
```

---

## Security Features

### JWT Security

- **Secret Rotation**: Validation on startup, fails if missing or too short
- **Token Revocation**: MongoDB denylist with JTI (JWT ID) tracking
- **Not Before Claim**: All tokens include `nbf` to prevent replay of old tokens
- **Short TTL**: 12-hour expiration for console sessions

### Rate Limiting

- **IP-Based**: 5 login attempts per 15 minutes → 429 Too Many Requests
- **Account Lockout**: 5 consecutive failures → 1 hour lockout → 423 Service Unavailable
- **Auto-Cleanup**: Old attempts purged every 24 hours

### API Key Security

- **Format Validation**: Regex `^pk_[0-9a-f]{40}$` rejects malformed keys
- **Random Generation**: `seed.py` generates unique keys per run
- **Secure Storage**: SHA-256 hashed, never serialized in responses

### CSRF Protection

- **Token Endpoint**: `GET /auth/csrf-token` provides fresh tokens
- **Validation**: Required on password changes and user management
- **Single-Use**: Tokens consumed after validation, 12-hour expiry

### Replay Attack Prevention

- **Nonces**: `GET /auth/nonce` provides single-use tokens
- **5-Minute Expiry**: Nonces auto-expire
- **Defense-in-Depth**: Combined with JWT `nbf` claim

---

## Testing

### Run Security Tests

```bash
cd backend
pytest tests/test_auth_security.py -v
```

**Current Status**: 33/33 tests passing

### Test Categories

| Suite | Count | Coverage |
|-------|-------|----------|
| Token Revocation | 5 | JWT denylist, JTI tracking |
| JWT Validation | 4 | Secret validation, startup checks |
| Login Rate Limiting | 8 | IP limits, lockout mechanics |
| Account Lockout | 3 | Consecutive failure tracking |
| CSRF Protection | 5 | Token generation, validation |
| Code Quality | 3 | No hardcoded secrets, config checks |

### Verification Commands

```bash
# Syntax check
python -m py_compile lib/auth.py lib/csrf.py routers/auth.py

# Run all tests
pytest tests/test_auth_security.py -v

# Verify no secrets in git
git log --all --full-history -- backend/.env
```

---

## Operations

### Monitoring

```bash
# Check service status
sudo supervisorctl status

# View logs
tail -f /var/log/supervisor/backend.err.log

# Health check
curl http://localhost:8001/api/health
```

### Maintenance

```bash
# Reseed demo data (destructive)
cd backend && python seed.py

# Type check frontend
cd frontend && pnpm typecheck

# Restart services
sudo supervisorctl restart backend frontend
```

### Backup Strategy

- MongoDB Atlas provides automated backups
- Export profiles via `/api/profiles` endpoint
- Audit logs retained for compliance

---

## Known Limitations

1. **Non-Streaming Chat**: Replies are non-streaming by design; full draft required before gating
2. **Reflection Limits**: Deterministic rewrite repairs tone-level breaches, not deeply unsafe content
3. **Password Reset**: Email flow not implemented; admin issues temporary passwords
4. **Refusal Analytics**: Aggregated data in event log but not charted

---

## Phase 2 Roadmap

### High Priority
- [ ] ReDoS protection in encoder
- [ ] Chat draft length validation
- [ ] Complete audit attribution
- [ ] Password complexity requirements

### Medium Priority
- [ ] Health check endpoint
- [ ] MongoDB read/write concerns
- [ ] React error boundaries
- [ ] Automated type sync check

---

## Patents & Intellectual Property

This system implements patented technology:

- **Lina/DHP**: Dynamic Hyperplane Parameterization (Nonprovisional #19/749,671)
- **SPECTRE N0L**: Asynchronous Frequency Communication (Provisional #64/058,323)
- **SHIMMERS**: High-Frequency Pulse Generation (Provisional #64/058,434)
- **EIDOLON**: Dragoncache Architecture (Provisional #64/058,589)

All rights reserved. This software is proprietary to Scott Slater / SmartScott LLC.

---

## Support

- **Documentation**: See `memory/SPEC.md` for detailed architecture
- **Security Issues**: Report privately to security@smartscott.com
- **Commercial Licensing**: Contact for government/enterprise deployment

---

**Version**: 1.0.0  
**Last Updated**: 2026-08-24  
**Security Classification**: Safety-Critical
