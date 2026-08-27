# PRD: Single Container Deployment Consolidation

**Issue**: #001
**Author**: Scott
**Date**: 2026-08-26
**Status**: Draft

---

## 1. Problem Statement

The Polytope Containment Console currently requires multiple Dockerfiles and nginx configuration for a single-container deployment. The deleted Dockerfiles in `ref_files/` show attempts at this consolidation, but none are currently active. We need a clean, production-ready single Dockerfile that serves both the FastAPI backend and React frontend without external reverse proxies.

## 2. Goals

1. **Simplify deployment**: One Dockerfile, one container, one process
2. **Eliminate Nginx dependency**: Backend serves static frontend files directly
3. **Preserve security**: All existing security headers, CORS, CSRF protection remain intact
4. **Maintain test coverage**: All 145 tests must pass
5. **Production-ready**: Health checks, resource limits, non-root execution

## 3. Proposed Solution: Backend-Served Frontend

### Architecture

```
┌─────────────────────────────────────────┐
│         Single Docker Container         │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │      FastAPI (uvicorn)          │   │
│  │                                 │   │
│  │  /api/*        → API endpoints  │   │
│  │  /              → Static files  │   │
│  │  /*            → index.html     │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Static files: ./frontend/dist/       │
└─────────────────────────────────────────┘
           ↓
     Port 8001
```

### Why This Approach?

| Factor | Backend-Served | Caddy | Nginx + Supervisor |
|--------|----------------|-------|---------------------|
| Processes | 1 | 2 | 2+ |
| Config files | Minimal | Caddyfile | nginx.conf + supervisord |
| Path mapping | None needed | Proxy passes | sw.js path issues |
| Security model | Existing headers | Additional proxy | Dual server |
| Image size | Smaller | Larger | Largest |

## 4. Technical Requirements

### 4.1 Dockerfile Structure

```dockerfile
FROM python:3.12-slim

# Install Node.js for frontend build
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y nodejs

WORKDIR /app

# Backend dependencies
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY backend/ ./backend/

# Frontend build
COPY frontend/package.json frontend/pnpm-lock.yaml ./frontend/
RUN npm install -g pnpm && cd frontend && pnpm install --frozen-lockfile
COPY frontend/ ./frontend/
RUN cd frontend && pnpm build

# No Nginx needed - backend serves static files
EXPOSE 8001

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
```

### 4.2 FastAPI Static File Configuration

In `backend/server.py`, add:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist" / "index.html"

# Mount static files
app.mount("/", StaticFiles(directory=str(FRONTEND_DIST.parent), html=True), name="frontend")

# SPA fallback - catch-all for client-side routing
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    return FileResponse(str(FRONTEND_DIST))
```

### 4.3 docker-compose.yml

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: polytope-app
    restart: unless-stopped
    ports:
      - "8001:8001"
    env_file:
      - path: ./backend/.env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    networks:
      - polytope-network

networks:
  polytope-network:
    driver: bridge
```

## 5. Security Considerations

### 5.1 Preserved Security Measures

- **CSP Headers**: Already in `server.py` middleware
- **JWT Auth**: Unchanged
- **Rate Limiting**: Unchanged
- **CSRF Protection**: Unchanged
- **API Key Validation**: Unchanged

### 5.2 New Security Measures

- **Non-root user**: Add in Dockerfile
- **Read-only filesystem**: Optional, for production
- **Resource limits**: In docker-compose

### 5.3 Removed Attack Surface

- No Nginx = no nginx-specific vulnerabilities
- No Supervisor = no supervisor-specific attack vector
- Single process = simpler security audit

## 6. Migration Plan

### Phase 1: Implementation
1. Create new `Dockerfile` at root
2. Update `server.py` to serve static files
3. Create new `docker-compose.yml`
4. Update `docker.sh` script

### Phase 2: Testing
1. Build Docker image
2. Run full test suite
3. Verify frontend loads correctly
4. Verify API endpoints work
5. Test health check

### Phase 3: Cleanup
1. Remove `ref_files/` directory
2. Update `README.md`
3. Update `DOCKER.md`
4. Commit changes

## 7. Success Metrics

- [ ] Single Dockerfile at root (not in ref_files/)
- [ ] `docker compose up` brings up both services
- [ ] Frontend loads at http://localhost:8001
- [ ] API accessible at http://localhost:8001/api/*
- [ ] All 145 tests pass
- [ ] Health check returns 200
- [ ] Image size < 500MB (optimization goal)
- [ ] No hardcoded secrets in image

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SPA routing conflicts | Medium | High | Proper fallback handler in server.py |
| Static file caching issues | Low | Medium | Cache headers in middleware |
| Larger image size | Medium | Low | Multi-stage build optimization |
| Test failures | Low | High | Run full suite before merge |

## 9. Open Questions

1. Should we use multi-stage build to further reduce image size?
2. Do we need to update CORS origins for single-port deployment?
3. Should we add a health check for the frontend?

---

**Next Steps**: Approve PRD, then implement.
