#!/usr/bin/env bash
set -euo pipefail

# workflow.sh — Local test runner for simple-edge-tts
# Usage: ./workflow.sh [all|test|lint|typecheck|frontend|t1|t2|t3|t4]

# Color output if tty
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    GREEN=''
    RED=''
    BOLD=''
    RESET=''
fi

pass() {
    echo -e "${GREEN}✓ PASS${RESET}: $1"
}

fail() {
    echo -e "${RED}✗ FAIL${RESET}: $1"
    exit 1
}

run_step() {
    local name="$1"
    shift
    echo -e "${BOLD}▶ ${name}${RESET}"
    if "$@"; then
        pass "$name"
    else
        fail "$name"
    fi
    echo
}

step_lint() {
    run_step "t1: lint (ruff)" uv run ruff check src/ tests/
}

step_typecheck() {
    run_step "t2: typecheck (mypy)" uv run mypy src/ --ignore-missing-imports
}

step_test() {
    run_step "t3: test (pytest)" uv run pytest tests/ -v
}

step_frontend_build() {
    run_step "t4: frontend build" bash -c "cd frontend && npm run build"
}

CMD="${1:-all}"

case "$CMD" in
    all)
        step_lint
        step_typecheck
        step_test
        step_frontend_build
        ;;
    lint|t1)
        step_lint
        ;;
    typecheck|t2)
        step_typecheck
        ;;
    test|t3)
        step_test
        ;;
    frontend|t4)
        step_frontend_build
        ;;
    *)
        echo "Usage: $0 [all|test|lint|typecheck|frontend|t1|t2|t3|t4]"
        exit 1
        ;;
esac

echo -e "${GREEN}${BOLD}All requested steps passed.${RESET}"
