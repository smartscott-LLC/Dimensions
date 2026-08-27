# Issue: Single Container Deployment Consolidation

**Title**: Consolidate to Single Container with Backend-Served Frontend
**Status**: Open
**Created**: 2026-08-26
**Labels**: docker, infrastructure, deployment

## Description

Create a single deployable Docker container that runs both the FastAPI backend and serves the React frontend, eliminating Nginx and Supervisor.

## Context

Current state:
- Multiple Dockerfiles in `ref_files/` (deleted from root)
- No active `Dockerfile` or `docker-compose.yml` at root
- Backend runs on port 8001 (FastAPI/uvicorn)
- Frontend builds to `frontend/dist/` (Vite/React)
- Security-critical system with CSP headers, JWT auth, rate limiting

## Proposed Approach

**Option A: Single Process (Recommended)**
- Build frontend → copy dist/ to backend static files
- Configure FastAPI to serve static files via `StaticFiles`
- Single uvicorn process handles everything
- No Nginx, no Supervisor, no sw.js path mismatches
- Port: 8001 for both API and frontend

**Option B: Caddy Reverse Proxy**
- Keep separate processes, add Caddy
- Simpler config than Nginx
- Automatic HTTPS
- Still two processes in one container

## Acceptance Criteria

- [ ] Single Dockerfile builds and runs both services
- [ ] Frontend accessible at http://localhost:8001
- [ ] Backend API accessible at http://localhost:8001/api/*
- [ ] Health check endpoint works
- [ ] All 145 tests pass
- [ ] docker-compose.yml supports single service
- [ ] Security headers preserved
- [ ] No hardcoded secrets in image

## Constraints

- Must maintain all security invariants (JWT, CSRF, rate limiting)
- Must preserve existing test suite
- Must be production-ready (health checks, resource limits)
