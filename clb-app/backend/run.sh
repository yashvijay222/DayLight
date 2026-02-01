#!/bin/bash
# DayLight Backend - Docker Management Script
# Usage: ./run.sh [up|down|logs|status|rebuild]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

case "${1:-help}" in
    up)
        echo "Starting DayLight backend services..."
        docker-compose up -d --build
        echo ""
        echo "Services started!"
        echo "  API:  http://localhost:8000"
        echo "  Docs: http://localhost:8000/docs"
        echo ""
        echo "Run './run.sh logs' to view logs"
        ;;
    
    down)
        echo "Stopping DayLight backend services..."
        docker-compose down
        echo "Services stopped."
        ;;
    
    logs)
        docker-compose logs -f ${2:-}
        ;;
    
    status)
        docker-compose ps
        ;;
    
    rebuild)
        echo "Rebuilding and restarting services..."
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        echo "Services rebuilt and started!"
        ;;
    
    shell)
        SERVICE="${2:-backend}"
        echo "Opening shell in $SERVICE..."
        docker-compose exec "$SERVICE" /bin/bash
        ;;
    
    help|--help|-h|*)
        echo "DayLight Backend - Docker Management"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  up        Build and start all services"
        echo "  down      Stop all services"
        echo "  logs      View logs (optionally: logs [service])"
        echo "  status    Show service status"
        echo "  rebuild   Rebuild and restart all services"
        echo "  shell     Open shell in container (default: backend)"
        echo "  help      Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 up              # Start everything"
        echo "  $0 logs backend    # View backend logs"
        echo "  $0 shell presage   # Shell into presage container"
        ;;
esac
