---
name: ok:instrument
description: Run the app with monocle instrumentation
argument-hint: [script.py]
allowed-tools:
  - Read
  - Bash
  - Write
  - AskUserQuestion
---

# ok:instrument

Run the app with monocle instrumentation.

## Steps

1. Check monocle.yaml exists
2. If no script provided, **USE AskUserQuestion** to ask for it
3. Run: `python .claude/scripts/instrument.py --config monocle.yaml <script>`
4. Show output
5. Traces saved to `.monocle/`

## Interactive Questions - USE AskUserQuestion TOOL

### Ask for script to run (if not provided):
```json
{
  "questions": [{
    "question": "Which script should be run with instrumentation?",
    "header": "Script",
    "multiSelect": false,
    "options": [
      {"label": "main.py (Recommended)", "description": "Main application entry point"},
      {"label": "app.py", "description": "Flask/FastAPI application"},
      {"label": "cli.py", "description": "Command-line interface"}
    ]
  }]
}
```
Note: Build options dynamically from detected entry points.

## Usage Examples

```
/ok:instrument app.py
/ok:instrument main.py --args "serve --port 8080"
```

## Related Commands

- `/ok:plan` - Generate monocle.yaml first if needed
- `/ok:view` - View traces after running
