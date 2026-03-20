#!/bin/bash
# ============================================================
# Amplify AI — Start backend + frontend with a single command
# Usage:  ./scripts/run.sh      (from project root)
#         ./run.sh              (if you add a symlink at root)
# ============================================================

# Colour helpers
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║       🏗️  Amplify AI System           ║"
echo "  ║   Floor Plan → 3D BIM (RVT + glTF)  ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── Pre-flight checks ──────────────────────────────────────────────────────────

# Check Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo -e "${RED}✗ Python not found. Install Python 3.9+${NC}"
    exit 1
fi
PYTHON=$(command -v python3 || command -v python)

# Check Node / npm
if ! command -v npm &>/dev/null; then
    echo -e "${RED}✗ npm not found. Install Node.js 18+${NC}"
    exit 1
fi

# Install frontend dependencies if missing
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "${YELLOW}⚙  Installing frontend dependencies (first run)…${NC}"
    cd "$FRONTEND_DIR" && npm install --silent
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
fi

# ── Kill both child processes on Ctrl+C ───────────────────────────────────────
cleanup() {
    echo -e "\n${YELLOW}Shutting down Amplify AI…${NC}"
    [ -n "$BACKEND_PID" ]  && kill "$BACKEND_PID"  2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
    echo -e "${GREEN}Goodbye.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── Start Backend ─────────────────────────────────────────────────────────────
echo -e "${GREEN}▶  Starting backend  →  http://localhost:8000${NC}"
cd "$BACKEND_DIR"

# Activate virtualenv if present
if [ -d "venv" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

$PYTHON app.py &
BACKEND_PID=$!

# Wait for the backend to actually be ready before launching the frontend
echo -e "${YELLOW}⏳ Waiting for backend to be ready…${NC}"
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1 || \
       curl -sf http://localhost:8000/api/health >/dev/null 2>&1 || \
       curl -sf http://localhost:8000/ >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
sleep 1  # one extra second for WS listeners to settle

# ── Start Frontend ────────────────────────────────────────────────────────────
echo -e "${GREEN}▶  Starting frontend →  http://localhost:5173${NC}"
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

# ── Ready ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}  ✓ Amplify AI is running${NC}"
echo -e "${GREEN}    Frontend:  http://localhost:5173${NC}"
echo -e "${GREEN}    Backend:   http://localhost:8000${NC}"
echo -e "${GREEN}    API docs:  http://localhost:8000/api/docs${NC}"
echo -e "${YELLOW}    Press Ctrl+C to stop both services.${NC}"
echo ""

# Wait for either process to exit
wait "$BACKEND_PID" "$FRONTEND_PID"
