---
name: ok:run
description: Run your app with monocle tracing enabled
argument-hint: [command...]
allowed-tools:
  - Read
  - Bash
  - Glob
  - AskUserQuestion
---

# ok:run [command...]

Smart runner for instrumented apps. Automatically determines how to run based on instrumentation approach.

## Smart Behavior

1. **Check instrumentation approach** from `.analyze/SESSION.md`
2. **Determine run command**:
   - If command provided → use it
   - If only one entry point detected → use it automatically
   - If multiple options → prompt user to choose
3. **Execute**:
   - Zero-code approach → wrap with `okahu-instrument`
   - Code-based approach → run directly

## Steps

### Step 1: Check Prerequisites

1. Read `.analyze/SESSION.md` to determine:
   - Instrumentation approach (zero-code or code-based)
   - Entry points detected during scan
2. If no SESSION.md → tell user: "Run `/ok:instrument` first."

### Step 2: Determine Run Command

**If command provided in arguments:**
- Use it directly

**If no command provided:**

1. Check `.analyze/entry_points.json` for detected entry points
2. **If exactly ONE entry point** → use it automatically, no prompt needed
3. **If MULTIPLE entry points or UNCLEAR** → **USE AskUserQuestion**:

```json
{
  "questions": [{
    "question": "How would you like to run your app?",
    "header": "Run",
    "multiSelect": false,
    "options": [
      {"label": "python main.py", "description": "CLI entry point (detected)"},
      {"label": "flask run -p 8080", "description": "Flask dev server"},
      {"label": "uvicorn app:app --reload", "description": "ASGI server"},
      {"label": "python -m myapp", "description": "Module execution"},
      {"label": "Enter custom command", "description": "Specify your own run command"},
      {"label": "Don't run - exit", "description": "Exit without running"}
    ]
  }]
}
```

Note: Build options dynamically from:
- Detected entry points (`.analyze/entry_points.json`)
- Common patterns based on detected frameworks (Flask, FastAPI, etc.)
- Always include "Enter custom command" and "Don't run - exit"

**If user selects "Don't run - exit":**
- Say "Okay, not running. You can run manually or use `/ok:run <command>` later."
- Exit without running anything

**If user selects "Enter custom command":**
- Ask: "Enter your run command (e.g., `flask run -p 8080`):"

### Step 3: Execute

**If Zero-code approach (okahu.yaml exists):**
```bash
python .claude/scripts/okahu_instrument.py <command>
```

**If Code-based approach (setup code injected):**
```bash
<command>
```
Run the command directly - tracing is already enabled via injected code.

### Step 4: Handle Long-Running Processes

For servers/workers that listen on ports:
- Run the command normally (it will block and listen)
- User can Ctrl+C to stop
- Traces are flushed on shutdown

**Important:** Do NOT use `run_in_background` for servers - they need to run in foreground so user can see output and Ctrl+C to stop.

### Step 5: Update SESSION.md

After running (or if user exits), append to `.analyze/SESSION.md`:

```markdown
## Run (/ok:run)
- **Command**: flask run -p 8080
- **Approach**: Zero-code (via okahu-instrument) / Code-based (direct)
- **Status**: Completed / User exited / Error
- **Next**: Run `/ok:local-trace` to inspect traces
```

## Examples

```bash
# Explicit command
/ok:run python app.py
/ok:run flask run -p 8080
/ok:run uvicorn app:app --host 0.0.0.0 --port 8000
/ok:run celery -A myapp worker --loglevel=info

# Auto-detect (will prompt if multiple options)
/ok:run
```

## Environment Variables

These are passed through to the app:

```bash
MONOCLE_STRICT=true       # Fail if instrumentation breaks (default: false)
MONOCLE_SILENT=true       # Suppress warnings (default: false)
OKAHU_INGESTION_ENDPOINT  # Okahu cloud endpoint
OKAHU_API_KEY             # Okahu API key
```

## Related Commands

- `/ok:instrument` - Must run first to set up tracing
- `/ok:local-trace` - View traces after running
