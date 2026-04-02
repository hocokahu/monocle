#!/bin/bash
# Wrapper script to run monocle_hook.py with environment variables
# This script sources the .env file before running the hook

REPO_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"

# Source environment variables if .env exists
if [ -f "$REPO_DIR/.env" ]; then
    source "$REPO_DIR/.env"
fi

# Run the hook
python3 "$REPO_DIR/examples/scripts/claude_code_hook/monocle_hook.py"
