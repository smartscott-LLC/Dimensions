# Polytope Containment Console — Single Container Dockerfile
# Runs both backend (uvicorn) and frontend (nginx) in one container

FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies including Node.js 24.x
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nginx \
    supervisor \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend code and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY backend/ ./backend/

# Copy frontend code and build
COPY frontend/package.json frontend/pnpm-lock.yaml ./frontend/
RUN npm install -g pnpm && cd frontend && pnpm install --frozen-lockfile
COPY frontend/ ./frontend/
RUN cd frontend && pnpm build

FROM nginx:alpine AS production

ENV BACKEND_URL=http://backend:8001

# Configure nginx
COPY nginx.single-container.conf /etc/nginx/conf.d/default.conf

EXPOSE 8081

# Configure supervisor
RUN mkdir -p /var/log/app

USER root

CMD ["nginx", "-g", "daemon off;"]
