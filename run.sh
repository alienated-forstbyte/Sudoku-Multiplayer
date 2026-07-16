#!/usr/bin/env bash
#
# Portable bootstrap for the Multiplayer Sudoku MLOps demo, for environments
# without `make`. It creates a virtualenv, trains the model, and launches the
# Docker Compose stack.
#
# Usage:
#   ./run.sh              # full pipeline: install -> train -> up
#   ./run.sh train        # only (re)train and place the model artifact
#   ./run.sh test         # install deps and run the test suite
#   ./run.sh up           # build and start the stack (trains if model missing)
#   ./run.sh down         # stop the stack
#   ./run.sh clean        # stop stack, drop volumes, remove artifacts

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-.venv}"
MODEL="sudoku_model.pkl"

log() { printf '\n\033[36m==> %s\033[0m\n' "$*"; }

ensure_venv() {
    if [ ! -d "$VENV" ]; then
        log "Creating virtualenv in $VENV"
        "$PYTHON" -m venv "$VENV"
    fi
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
}

install() {
    ensure_venv
    log "Installing dependencies"
    pip install --upgrade pip
    pip install -r requirements.txt
}

train() {
    install
    log "Generating dataset"
    python -m ml.dataset
    log "Training model"
    python -m ml.train
    cp "$MODEL" "ml_service/$MODEL"
    log "Model written to ./$MODEL and ml_service/$MODEL"
}

ensure_model() {
    if [ ! -f "$MODEL" ] || [ ! -f "ml_service/$MODEL" ]; then
        train
    fi
}

run_tests() {
    install
    log "Running tests"
    python -m pytest -q
}

up() {
    ensure_model
    log "Building and starting the stack"
    docker compose up --build
}

case "${1:-all}" in
    all)   train; up ;;
    install) install ;;
    train) train ;;
    test)  run_tests ;;
    up)    up ;;
    down)  docker compose down ;;
    clean)
        docker compose down -v || true
        rm -f "$MODEL" "ml_service/$MODEL" sudoku_dataset.csv
        find . -type d -name __pycache__ -prune -exec rm -rf {} +
        ;;
    *)
        echo "Unknown command: $1" >&2
        echo "Use: all | install | train | test | up | down | clean" >&2
        exit 1
        ;;
esac
