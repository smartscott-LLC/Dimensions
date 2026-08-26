# Polytope Containment Console — Single Container Dockerfile for SnapDeploy
# Runs both backend (uvicorn) and frontend (nginx) in one container

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend code and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY backend/ ./

# Copy frontend code and build
COPY frontend/package.json frontend/pnpm-lock.yaml ./frontend/
RUN corepack enable && corepack prepare pnpm@latest --activate
RUN cd frontend && pnpm install --frozen-lockfile
COPY frontend/ ./frontend/
RUN cd frontend && pnpm build

FROM nginx:alpine AS serving

COPY nginx.app.conf /etc/nginx/sites-available/default

# Remove the default Nginx static assets if you aren't using them
RUN rm -rf /usr/share/nginx/html/*

# Copy your custom configuration directly to overwrite the default
COPY default.conf /etc/nginx/conf.d/default.conf

# Copy your website files
COPY . /usr/share/nginx/html

# Copy supervisor configuration
RUN cat > /etc/supervisor/conf.d/app.conf << 'EOF'
[supervisord]
nodaemon=true
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid

[program:nginx]
command=nginx -g "daemon off;"
autostart=true
autorestart=true
priority=10

[program:backend]
command=uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
directory=/app
autostart=true
autorestart=true
priority=20
EOF

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /var/log/supervisor && \
    chown -R appuser:appuser /var/run && \
    chown -R appuser:appuser /etc/nginx

USER appuser

# Expose ports
EXPOSE 80 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Start supervisor (manages both nginx and backend)
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
