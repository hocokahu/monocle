#!/bin/bash
#
# Install Monocle hook for Claude Code
#
# Usage:
#   ./install.sh              # Interactive install (prompts for location)
#   ./install.sh --global     # Install to ~/.claude/settings.json
#   ./install.sh --project    # Install to .claude/settings.local.json
#   ./install.sh --uninstall  # Remove hook from all locations
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_DIR="$HOME/.claude/hooks"
STATE_DIR="$HOME/.claude/state"
GLOBAL_SETTINGS="$HOME/.claude/settings.json"
PROJECT_SETTINGS=".claude/settings.local.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# --- Interactive location picker (radio-style like npx) ---
prompt_install_location() {
    echo ""
    echo -e "${BOLD}${CYAN}Monocle Claude Code Hook Installer${NC}"
    echo ""
    echo -e "  ${BOLD}Installation scope${NC}"

    local options=("project" "global")
    local labels=("Project" "Global")
    local descs=("Install in current directory (committed with your project)" "Install in ~/.claude/settings.json (applies to all projects)")
    local selected=0

    # Check if terminal supports cursor movement
    if [ -t 0 ] && command -v tput &>/dev/null; then
        # Interactive radio selector
        tput civis 2>/dev/null  # hide cursor
        trap 'tput cnorm 2>/dev/null' EXIT

        while true; do
            # Draw options
            for i in "${!options[@]}"; do
                if [ "$i" -eq "$selected" ]; then
                    echo -e "  │  ${GREEN}●${NC} ${BOLD}${labels[$i]}${NC} ${DIM}(${descs[$i]})${NC}"
                else
                    echo -e "  │  ○ ${labels[$i]} ${DIM}(${descs[$i]})${NC}"
                fi
            done

            # Read single keypress
            IFS= read -rsn1 key
            if [[ "$key" == $'\x1b' ]]; then
                read -rsn2 key
                case "$key" in
                    '[A') selected=$(( (selected - 1 + ${#options[@]}) % ${#options[@]} )) ;;  # Up
                    '[B') selected=$(( (selected + 1) % ${#options[@]} )) ;;  # Down
                esac
                # Move cursor back up to redraw
                tput cuu ${#options[@]} 2>/dev/null
            elif [[ "$key" == "" ]]; then
                # Enter pressed
                break
            fi
        done

        tput cnorm 2>/dev/null  # restore cursor
    else
        # Fallback: simple numbered prompt
        for i in "${!options[@]}"; do
            echo -e "  │  $((i+1))) ${labels[$i]} ${DIM}(${descs[$i]})${NC}"
        done
        echo ""
        while true; do
            echo -ne "  ${BOLD}Choose [1/2]:${NC} "
            read -r choice
            case "$choice" in
                1) selected=0; break ;;
                2) selected=1; break ;;
                *) echo -e "  ${RED}Invalid choice.${NC}" ;;
            esac
        done
    fi

    INSTALL_TARGET="${options[$selected]}"
    echo ""
}

# --- Add hook to a settings file using Python ---
add_hook_to_settings() {
    local settings_path="$1"
    local hook_cmd="$2"
    local label="$3"

    python3 << PYTHON
import json, sys
from pathlib import Path

settings_path = Path("$settings_path")

try:
    with open(settings_path, "r") as f:
        settings = json.load(f)
except Exception:
    settings = {}

settings.setdefault("hooks", {})
settings["hooks"].setdefault("Stop", [])

hook_cmd = """$hook_cmd"""

# Claude Code expects hooks wrapped in a "hooks" array
already_added = False
for entry in settings["hooks"]["Stop"]:
    hooks_list = entry.get("hooks", []) if isinstance(entry, dict) else []
    for h in hooks_list:
        if isinstance(h, dict) and "monocle_hook" in h.get("command", ""):
            already_added = True
            break
    # Also check flat format
    if isinstance(entry, dict) and "monocle_hook" in entry.get("command", ""):
        already_added = True
    if already_added:
        break

if not already_added:
    settings["hooks"]["Stop"].append({
        "hooks": [{"type": "command", "command": hook_cmd}]
    })
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"Hook added to {settings_path}")
else:
    print(f"Hook already configured in {settings_path}")
PYTHON
}

# --- Remove hook from a settings file ---
remove_hook_from_settings() {
    local settings_path="$1"

    [ -f "$settings_path" ] || return 0

    python3 << PYTHON
import json
from pathlib import Path

settings_path = Path("$settings_path")
try:
    with open(settings_path, "r") as f:
        settings = json.load(f)
except Exception:
    exit(0)

if "hooks" not in settings or "Stop" not in settings["hooks"]:
    exit(0)

filtered = []
for entry in settings["hooks"]["Stop"]:
    if isinstance(entry, dict):
        # Handle wrapped format {"hooks": [{"command": "..."}]}
        hooks_list = entry.get("hooks", [])
        clean_hooks = [h for h in hooks_list if not (isinstance(h, dict) and "monocle_hook" in h.get("command", ""))]
        if clean_hooks:
            entry["hooks"] = clean_hooks
            filtered.append(entry)
        elif not hooks_list:
            # Flat format {"command": "..."}
            if "monocle_hook" not in entry.get("command", ""):
                filtered.append(entry)
    else:
        filtered.append(entry)

settings["hooks"]["Stop"] = filtered
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
print(f"Hook removed from {settings_path}")
PYTHON
}

# --- Core install logic ---
install_hook() {
    local target="$1"

    info "Installing Monocle Claude Code hook..."
    echo ""

    # Create directories
    mkdir -p "$HOOK_DIR"
    mkdir -p "$STATE_DIR"

    # Copy hook script
    cp "$SCRIPT_DIR/monocle_hook.py" "$HOOK_DIR/"
    chmod +x "$HOOK_DIR/monocle_hook.py"
    info "Copied monocle_hook.py to $HOOK_DIR/"

    # Build the hook command
    HOOK_CMD="bash -c 'set -a && source \"\$(git rev-parse --show-toplevel 2>/dev/null)/.env\" 2>/dev/null && set +a && python3 $HOOK_DIR/monocle_hook.py'"

    # Install to selected target
    case "$target" in
        global)
            [ -f "$GLOBAL_SETTINGS" ] && cp "$GLOBAL_SETTINGS" "$GLOBAL_SETTINGS.bak" && info "Backed up settings.json"
            add_hook_to_settings "$GLOBAL_SETTINGS" "$HOOK_CMD" "global"
            ;;
        project)
            [ -f "$PROJECT_SETTINGS" ] && cp "$PROJECT_SETTINGS" "$PROJECT_SETTINGS.bak" && info "Backed up settings.local.json"
            add_hook_to_settings "$PROJECT_SETTINGS" "$HOOK_CMD" "project"
            ;;
    esac

    echo ""

    # Check dependencies
    if python3 -c "import monocle_apptrace" 2>/dev/null; then
        info "monocle_apptrace is installed"
    else
        warn "monocle_apptrace not found. Install with: pip install monocle_apptrace"
    fi

    # Check environment variables
    if [ -z "$OKAHU_API_KEY" ]; then
        if [ -f ".env" ] && grep -q "OKAHU_API_KEY" .env 2>/dev/null; then
            info "OKAHU_API_KEY found in .env file"
        else
            warn "OKAHU_API_KEY not set. Add it to your .env file."
        fi
    else
        info "OKAHU_API_KEY is set"
    fi

    echo ""
    echo -e "${GREEN}${BOLD}Installation complete!${NC}"
    echo ""
    echo "  Installed to:"
    case "$target" in
        global)  echo -e "    ${CYAN}~/.claude/settings.json${NC} (global)" ;;
        project) echo -e "    ${CYAN}.claude/settings.local.json${NC} (this project)" ;;
    esac
    echo ""
    echo "  Next steps:"
    echo "    1. Create a .env file in your project root (if not already):"
    echo "       export OKAHU_API_KEY=\"your-key\""
    echo "       export OKAHU_INGESTION_ENDPOINT=\"https://ingest.okahu.co/api/v1/trace/ingest\""
    echo "       export MONOCLE_EXPORTER=\"okahu\""
    echo ""
    echo "    2. Restart Claude Code to pick up the new hook"
    echo ""
    echo "    3. Check logs at: ~/.claude/state/monocle_hook.log"
    echo ""
}

uninstall_hook() {
    info "Uninstalling Monocle Claude Code hook..."

    # Remove hook script
    if [ -f "$HOOK_DIR/monocle_hook.py" ]; then
        rm "$HOOK_DIR/monocle_hook.py"
        info "Removed monocle_hook.py"
    fi

    # Remove from both settings locations
    remove_hook_from_settings "$GLOBAL_SETTINGS"
    remove_hook_from_settings "$PROJECT_SETTINGS"

    echo ""
    info "Uninstallation complete!"
}

# --- Main ---
case "${1:-}" in
    --uninstall|-u)
        uninstall_hook
        ;;
    --global|-g)
        install_hook "global"
        ;;
    --project|-p)
        install_hook "project"
        ;;
    --help|-h)
        echo ""
        echo "Usage: $0 [option]"
        echo ""
        echo "Install or remove Monocle hook for Claude Code"
        echo ""
        echo "Options:"
        echo "  (none)             Interactive install — prompts for location"
        echo "  --global, -g       Install to ~/.claude/settings.json"
        echo "  --project, -p      Install to .claude/settings.local.json"
        echo "  --uninstall, -u    Remove the hook from all locations"
        echo "  --help, -h         Show this help"
        echo ""
        ;;
    *)
        prompt_install_location
        install_hook "$INSTALL_TARGET"
        ;;
esac
