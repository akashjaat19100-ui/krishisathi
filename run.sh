#!/usr/bin/env bash
# KrishiSathi One-Command Local Launcher
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON_EXEC="python3"
else
    echo "Python 3 is required to run KrishiSathi."
    exit 1
fi

export PYTHONPATH="$SCRIPT_DIR"
exec "$PYTHON_EXEC" "$SCRIPT_DIR/run.py" "$@"
