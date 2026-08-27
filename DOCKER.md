# Polytope Containment Console — Docker Quickstart

## Prerequisites

- Docker Desktop installed and running
- MongoDB Atlas connection string
- Supabase project (optional, for hybrid auth)
- OpenAI-compatible API key (for chat coach)

## Setup

### 1. Verify Environment

Your `backend/.env` is already configured. Verify it exists:

```bash
ls -la backend/.env
```

**Required variables (already set in your .env):**
- `MONGO_URL` — MongoDB Atlas connection string
- `JWT_SECRET` — 64-character hex secret
- `ADMIN_PASSWORD` — Admin password
- `SUPABASE_URL`, `SUPABASE_JWKS_URL`, `SUPABASE_SECRET_KEY` — For hybrid auth

### 2. Start Services

```bash
# Build and start the single container
./docker.sh up

# Or using docker-compose directly
docker compose up -d --build
```

### 3. Verify Installation

```bash
# Check service status
./docker.sh status

# Check health
./docker.sh health

# View logs
./docker.sh logs
```

## Access Points

| Service | URL |
|---------|-----|
| Frontend + Backend | http://localhost:8001 |
| API Docs | http://localhost:8001/docs |
| Health Check | http://localhost:8001/api/health |

## Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | `s.slater@smartscott.com` | `smartscott` |

**⚠️ Change these credentials immediately after first login.**

## Common Operations

```bash
# View logs
./docker.sh logs app    # App logs
./docker.sh logs        # All logs

# Restart services
./docker.sh restart

# Stop services
./docker.sh down

# Rebuild after code changes
./docker.sh build
./docker.sh up

# Seed demo data
./docker.sh seed

# Execute commands in container
./docker.sh exec app python -c "import lib.polytope; print(lib.polytope.DIMENSIONS)"
./docker.sh exec app sh

# Clean up (removes containers and volumes)
./docker.sh clean
```

## Architecture

```
┌─────────────────────────────────────────┐
│         Single Docker Container         │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │      FastAPI (uvicorn)          │   │
│  │                                 │   │
│  │  /              → React UI      │   │
│  │  /api/*       → API endpoints   │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Static files: ./frontend/dist/       │
└─────────────────────────────────────────┘
           ↓
     Port 8001
           ↓
     MongoDB Atlas (Cloud)
```

## Files Created

- `Dockerfile` — Single container with Python + Node.js
- `docker-compose.yml` — Single service orchestration
- `.dockerignore` — Build optimization
- `docker.sh` — Operations helper script
- `backend/.env.example` — Environment template
