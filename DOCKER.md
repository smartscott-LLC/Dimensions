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
# Build and start all services
./docker.sh up

# Or using docker-compose directly
docker-compose up -d --build
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
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8001/api/health |
| API Docs | http://localhost:8001/docs |

## Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | `s.slater@smartscott.com` | `smartscott` |

**⚠️ Change these credentials immediately after first login.**

## Common Operations

```bash
# View logs
./docker.sh logs backend    # Backend logs
./docker.sh logs frontend   # Frontend logs
./docker.sh logs            # All logs

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
./docker.sh exec backend python -c "import lib.polytope; print(lib.polytope.DIMENSIONS)"
./docker.sh exec frontend sh

# Clean up (removes containers and volumes)
./docker.sh clean
```

## Production Considerations

1. **Secrets Management**: Use Docker secrets or a vault for production
2. **CORS**: Set `CORS_ORIGINS` to your production domain
3. **JWT Secret**: Generate a strong, unique secret
4. **Passwords**: Change default admin/operator passwords
5. **Backups**: Ensure MongoDB Atlas backups are configured
6. **Monitoring**: Set up log aggregation and alerting

## Troubleshooting

### Backend won't start
```bash
# Check logs
./docker.sh logs backend

# Verify environment
docker-compose exec backend env | grep MONGO
```

### Frontend shows blank page
```bash
# Check build logs
./docker.sh logs frontend

# Rebuild
./docker.sh build
./docker.sh up
```

### Database connection failed
```bash
# Test MongoDB connectivity from backend container
./docker.sh exec backend bash -c "python -c 'from lib.db import db; print(db.name)'"
```

### Rate limiting too aggressive
```bash
# Check MongoDB connection
./docker.sh exec backend bash -c "mongo 'MONGO_URL' --eval 'db.adminCommand(\"ping\")'"
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│    Backend      │────▶│  MongoDB Atlas  │
│   (Nginx:80)    │     │  (FastAPI:8001) │     │   (Cloud)       │
│   Port 3000     │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │
         │                       ▼
         │                 ┌─────────────────┐
         │                 │   Supabase      │
         │                 │   (Cloud)       │
         │                 └─────────────────┘
         │
         ▼
   Browser
```

## Files Created

- `Dockerfile.backend` — Multi-stage Python build
- `Dockerfile.frontend` — Multi-stage Node.js + Nginx build
- `docker-compose.yml` — Service orchestration
- `nginx.conf` — Nginx configuration with API proxy
- `.dockerignore` — Build optimization
- `docker.sh` — Operations helper script
- `backend/.env.example` — Environment template
