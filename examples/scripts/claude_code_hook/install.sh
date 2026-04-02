#!/bin/bash
#
# Install Monocle hook for Claude Code
#
# Usage:
#   ./install.sh              # Install hook
#   ./install.sh --uninstall  # Remove hook
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_DIR="$HOME/.claude/hooks"
STATE_DIR="$HOME/.claude/state"
SETTINGS="$HOME/.claude/settings.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

install_hook() {
    info "Installing Monocle Claude Code hook..."

    # Create directories
    mkdir -p "$HOOK_DIR"
    mkdir -p "$STATE_DIR"

    # Copy hook script
    cp "$SCRIPT_DIR/monocle_hook.py" "$HOOK_DIR/"
    chmod +x "$HOOK_DIR/monocle_hook.py"
    info "Copied monocle_hook.py to $HOOK_DIR/"

    # Update Claude Code settings
    if [ -f "$SETTINGS" ]; then
        # Check if hook already configured
        if grep -q "monocle_hook.py" "$SETTINGS" 2>/dev/null; then
            info "Hook already configured in settings.json"
        else
            # Backup existing settings
            cp "$SETTINGS" "$SETTINGS.bak"
            info "Backed up settings.json to settings.json.bak"

            # Add hook using Python (handles JSON properly)
            python3 << 'PYTHON'
import json
import sys
from pathlib import Path

settings_path = Path.home() / ".claude" / "settings.json"

try:
    with open(settings_path, "r") as f:
        settings = json.load(f)
except Exception:
    settings = {}

# Ensure hooks structure exists
settings.setdefault("hooks", {})
settings["hooks"].setdefault("Stop", [])

# Check if already added
hook_cmd = "python3 ~/.claude/hooks/monocle_hook.py"
already_added = any(
    isinstance(h, dict) and h.get("command") == hook_cmd
    for h in settings["hooks"]["Stop"]
)

if not already_added:
    settings["hooks"]["Stop"].append({
        "type": "command",
        "command": hook_cmd
    })
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    print("Hook added to settings.json")
else:
    print("Hook already in settings.json")
PYTHON
        fi
    else
        # Create new settings file
        cat > "$SETTINGS" << 'JSON'
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "python3 ~/.claude/hooks/monocle_hook.py"
      }
    ]
  }
}
JSON
        info "Created settings.json with hook configuration"
    fi

    # Check dependencies
    if python3 -c "import monocle_apptrace" 2>/dev/null; then
        info "monocle_apptrace is installed"
    else
        warn "monocle_apptrace not found. Install with: pip install monocle_apptrace"
    fi

    # Check environment variables
    if [ -z "$OKAHU_API_KEY" ]; then
        warn "OKAHU_API_KEY not set. Export it in your shell profile."
    fi

    echo ""
    info "Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Set environment variables in your shell profile:"
    echo "     export OKAHU_API_KEY=\"your-key\""
    echo "     export OKAHU_INGESTION_ENDPOINT=\"https://ingest.okahu.co/api/v1/trace/ingest\""
    echo "     export MONOCLE_EXPORTER=\"okahu\""
    echo ""
    echo "  2. Restart Claude Code to pick up the new hook"
    echo ""
    echo "  3. Check logs at: ~/.claude/state/monocle_hook.log"
}

uninstall_hook() {
    info "Uninstalling Monocle Claude Code hook..."

    # Remove hook script
    if [ -f "$HOOK_DIR/monocle_hook.py" ]; then
        rm "$HOOK_DIR/monocle_hook.py"
        info "Removed monocle_hook.py"
    fi

    # Remove from settings
    if [ -f "$SETTINGS" ]; then
        python3 << 'PYTHON'
import json
from pathlib import Path

settings_path = Path.home() / ".claude" / "settings.json"

try:
    with open(settings_path, "r") as f:
        settings = json.load(f)
except Exception:
    settings = {}

if "hooks" in settings and "Stop" in settings["hooks"]:
    settings["hooks"]["Stop"] = [
        h for h in settings["hooks"]["Stop"]
        if not (isinstance(h, dict) and "monocle_hook" in h.get("command", ""))
    ]
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    print("Hook removed from settings.json")
PYTHON
    fi

    info "Uninstallation complete!"
}

# Main
case "${1:-}" in
    --uninstall|-u)
        uninstall_hook
        ;;
    --help|-h)
        echo "Usage: $0 [--uninstall]"
        echo ""
        echo "Install or remove Monocle hook for Claude Code"
        echo ""
        echo "Options:"
        echo "  --uninstall, -u    Remove the hook"
        echo "  --help, -h         Show this help"
        ;;
    *)
        install_hook
        ;;
esac
