#!/usr/bin/env bash
# Polytope Containment Console — Docker Operations Helper
# Usage: ./docker.sh [command]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Polytope Containment Console — Docker Operations"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  up              Start all services in detached mode"
    echo "  down            Stop all services"
    echo "  restart         Restart all services"
    echo "  logs [service]  Show logs (optional: backend|frontend|all)"
    echo "  status          Show service status"
    echo "  health          Check health of all services"
    echo "  seed            Run seed.py to populate database"
    echo "  exec [service]  Execute command in container"
    echo "  build           Rebuild all images"
    echo "  clean           Remove containers, images, volumes"
    echo ""
    echo "Examples:"
    echo "  $0 up"
    echo "  $0 logs backend"
    echo "  $0 exec backend python -c 'import lib.polytope; print(lib.polytope.DIMENSIONS)'"
}

check_env() {
    if [ ! -f "backend/.env" ]; then
        echo -e "${YELLOW}[WARN]${NC} backend/.env not found"
        echo "       Creating from .env.example..."
        cp backend/.env.example backend/.env
        echo -e "${YELLOW}[WARN]${NC} Please edit backend/.env and set your values"
        echo "       At minimum: MONGO_URL, JWT_SECRET, ADMIN_PASSWORD"
        return 1
    fi
    return 0
}

cmd_up() {
    check_env || return 1
    echo "Starting Polytope Containment Console..."
    docker-compose up -d
    echo -e "${GREEN}[OK]${NC} Services started"
    echo ""
    echo "  Backend:  http://localhost:8001/api/health"
    echo "  Frontend: http://localhost:3000"
    echo ""
    echo "Use '$0 logs' to view logs"
}

cmd_down() {
    echo "Stopping services..."
    docker-compose down
    echo -e "${GREEN}[OK]${NC} Services stopped"
}

cmd_restart() {
    docker-compose restart
    echo -e "${GREEN}[OK]${NC} Services restarted"
}

cmd_logs() {
    local service="${1:-all}"
    if [ "$service" = "all" ]; then
        docker-compose logs -f --tail=100
    else
        docker-compose logs -f --tail=100 "$service"
    fi
}

cmd_status() {
    docker-compose ps
}

cmd_health() {
    echo "Checking service health..."
    echo ""
    
    echo -n "Backend health:  "
    curl -sf http://localhost:8001/api/health | grep -q '"status":"healthy"' && echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}DEGRADED${NC}"
    
    echo -n "Frontend:        "
    curl -sf http://localhost:3000 > /dev/null && echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}DOWN${NC}"
    
    echo ""
    docker-compose ps
}

cmd_seed() {
    check_env || return 1
    echo "Running seed script..."
    docker-compose exec -T backend python seed.py
    echo -e "${GREEN}[OK]${NC} Database seeded"
}

cmd_exec() {
    local service="${1:-backend}"
    shift || true
    docker-compose exec -it "$service" "$@"
}

cmd_build() {
    echo "Building images..."
    docker-compose build --no-cache
    echo -e "${GREEN}[OK]${NC} Images built"
}

cmd_clean() {
    echo "Cleaning up..."
    docker-compose down -v --remove-orphans
    echo -e "${YELLOW}[INFO]${NC} To remove images, run: docker image prune -f"
}

# Main
case "${1:-}" in
    up) cmd_up ;;
    down) cmd_down ;;
    restart) cmd_restart ;;
    logs) cmd_logs "${2:-}" ;;
    status) cmd_status ;;
    health) cmd_health ;;
    seed) cmd_seed ;;
    exec) cmd_exec "${2:-}" "${@:3}" ;;
    build) cmd_build ;;
    clean) cmd_clean ;;
    help|--help|-h) usage ;;
    *) usage ;;
esac
