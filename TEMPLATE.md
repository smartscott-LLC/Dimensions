# Polytope Containment Console — Development Guide

**For Developers**: This document contains implementation details, conventions, and patterns for working with the codebase.

---

## 1. Backend Development

### 1.1 Project Structure

```
backend/
├── server.py              # FastAPI app bootstrap
├── lib/
│   ├── db.py             # MongoDB client + .env loader
│   ├── auth.py           # JWT, revocation, Supabase verification
│   ├── csrf.py           # CSRF token management
│   ├── encoder.py        # Text→14D deterministic encoding
│   ├── gatecore.py       # Dual-mode enforcement logic
│   ├── polytope.py       # Dykstra projection, sampling
│   └── ratelimit.py      # Sliding window rate limiting
├── models/
│   ├── auth.py           # User schemas
│   ├── clients.py        # Client/API key schemas
│   ├── containment.py    # Event schemas
│   ├── gate.py           # Gate request/response schemas
│   └── chat.py           # Chat session/turn schemas
├── routers/
│   ├── auth.py           # Authentication endpoints
│   ├── clients.py        # Client management
│   ├── containment.py    # Core containment API
│   ├── gate.py           # Gate enforcement API
│   └── chat.py           # Chat coach API
├── tests/
│   ├── conftest.py       # pytest fixtures
│   └── test_auth_security.py  # Security test suite
└── seed.py               # Demo data generation
```

### 1.2 Adding New Routes

1. **Create Pydantic models** in `models/`
2. **Create router** in `routers/` with `APIRouter`
3. **Mount in server.py**:
   ```python
   from routers.new import router as new_router
   api_router.include_router(new_router)
   ```
4. **Add TypeScript interface** in `frontend/src/lib/types.ts`
5. **Add API function** in `frontend/src/lib/api.ts`
6. **Update this spec** and `memory/SPEC.md`

### 1.3 MongoDB Patterns

```python
from lib.db import db

# Insert
doc = await db.events.insert_one(event_dict)
event_id = str(doc.inserted_id)

# Find
event = await db.events.find_one({"id": event_id})

# Update
await db.events.update_one(
    {"id": event_id},
    {"$set": {"status": "corrected"}}
)

# Delete
await db.events.delete_one({"id": event_id})

# Aggregate
results = await db.events.aggregate([
    {"$match": {"profile_id": profile_id}},
    {"$group": {"_id": "$status", "count": {"$sum": 1}}}
]).to_list(None)
```

### 1.4 Error Handling

```python
from fastapi import HTTPException

# Client errors (4xx)
raise HTTPException(status_code=404, detail="Resource not found")
raise HTTPException(status_code=401, detail="Invalid credentials")
raise HTTPException(status_code=422, detail="Validation error")

# Server errors (5xx)
raise HTTPException(status_code=500, detail="Internal error")
```

### 1.5 Security Patterns

```python
# Rate limiting check
if await is_rate_limited(client_id):
    raise HTTPException(status_code=429, detail="Rate limited")

# API key validation
api_key = request.headers.get("X-API-Key")
if not validate_api_key_format(api_key):
    raise HTTPException(status_code=401, detail="Invalid key format")

# JWT authentication
user = await get_current_user(token)
if not user.active:
    raise HTTPException(status_code=403, detail="Account deactivated")

# CSRF validation
csrf_token = request.headers.get("X-CSRF-Token")
if not await validate_csrf_token(csrf_token, user.email):
    raise HTTPException(status_code=403, detail="Invalid CSRF token")
```

---

## 2. Frontend Development

### 2.1 Project Structure

```
frontend/src/
├── main.tsx              # App entry point
├── App.tsx               # Route definitions
├── lib/
│   ├── api.ts            # Typed fetch layer
│   ├── auth.tsx          # Auth provider/hooks
│   ├── types.ts          # TypeScript interfaces
│   └── queries.ts        # TanStack Query hooks
├── pages/
│   ├── Login.tsx         # Login page
│   └── Dashboard.tsx     # Main dashboard
└── components/
    ├── ui/               # shadcn/ui components
    ├── GatePanel.tsx     # Gate enforcement UI
    ├── ChatCoach.tsx     # Chat interface
    └── ...
```

### 2.2 API Client Pattern

```typescript
// frontend/src/lib/api.ts
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!response.ok) throw new ApiError(response);
  return response.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const csrf = await getCsrfToken();
  const response = await fetch(`/api${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      'X-CSRF-Token': csrf,
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new ApiError(response);
  return response.json();
}
```

### 2.3 Type Safety

Always keep Pydantic models and TypeScript interfaces in sync:

```typescript
// backend/models/containment.py
class Event(BaseModel):
    id: str
    status: str
    vector: list[float]

// frontend/src/lib/types.ts
interface Event {
  id: string;
  status: string;
  vector: number[];
}
```

### 2.4 React Patterns

```typescript
// Use TanStack Query for data fetching
const { data, isLoading } = useQuery({
  queryKey: ['events'],
  queryFn: () => apiGet<Event[]>('/events'),
});

// Use mutations for state changes
const mutation = useMutation({
  mutationFn: (data) => apiPost('/clients', data),
  onSuccess: () => queryClient.invalidateQueries(['clients']),
});
```

---

## 3. Testing

### 3.1 Backend Tests

```bash
# Run all security tests
cd backend && pytest tests/test_auth_security.py -v

# Run with coverage
cd backend && pytest --cov=lib --cov=routers tests/

# Run specific test
cd backend && pytest tests/test_auth_security.py::TestJwtSecretValidation -v
```

### 3.2 Frontend Tests

```bash
cd frontend && pnpm typecheck
cd frontend && pnpm lint
```

### 3.3 Test Patterns

```python
# Unit test pattern
async def test_function_name():
    # Arrange
    input_data = {...}
    
    # Act
    result = await function(input_data)
    
    # Assert
    assert result == expected
```

---

## 4. Build & Deploy

### 4.1 Local Development

```bash
# Backend
cd backend
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Frontend
cd frontend
pnpm dev
```

### 4.2 Supervisor Configuration

```ini
[supervisord]
nodaemon=true

[program:backend]
command=/app/backend/.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001
directory=/app/backend
autostart=true
autorestart=true

[program:frontend]
command=pnpm dev
directory=/app/frontend
autostart=true
autorestart=true
```

### 4.3 Environment Variables

Required in `backend/.env`:
```bash
MONGO_URL=mongodb://user:pass@cluster.mongodb.net/dbname
DB_NAME=DP3
JWT_SECRET=<64-char-hex>
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<strong-password>
MODEL_API_KEY=<openai-key>
MODEL_API_URL=https://api.example.com/v1
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_JWKS_URL=https://xxx.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_SECRET_KEY=sb_secret_xxx
```

---

## 5. Code Conventions

### 5.1 Python Style

- Use type hints everywhere
- Async/await for all I/O
- Pydantic v2 models for request/response
- f-strings for logging
- Docstrings for public functions

### 5.2 TypeScript Style

- Strict mode enabled
- Interface over type for object shapes
- const assertions for literals
- Error boundaries for graceful failures

### 5.3 Git Workflow

```bash
# Commit message format
git commit -m "feat: add rate limiting to login endpoint

- Added IP-based rate limiting (5 attempts/15min)
- Added account lockout (5 failures → 1hr)
- Added MongoDB collections for tracking"
```

---

## 6. Debugging

### 6.1 Common Issues

**Import errors**:
```bash
cd backend && python -c 'import server'
```

**Type errors**:
```bash
cd frontend && pnpm typecheck
```

**MongoDB connection**:
```bash
mongo "MONGO_URL" --eval "db.adminCommand('ping')"
```

### 6.2 Logging

Backend logs to `/var/log/supervisor/backend.err.log`. Enable debug mode:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 7. Security Checklist

Before merging any change:

- [ ] Input validation on all endpoints
- [ ] Rate limiting on sensitive operations
- [ ] Audit logging for state changes
- [ ] No hardcoded secrets
- [ ] Proper error handling (no info leakage)
- [ ] CSRF protection on form submissions
- [ ] Security tests updated

---

**Last Updated**: 2026-08-24  
**Maintained by**: Development Team
