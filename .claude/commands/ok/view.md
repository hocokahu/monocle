---
name: ok:view
description: View recent traces with trace_minify
argument-hint: [--last 5m | --errors | --trace-id X]
allowed-tools:
  - Read
  - Bash
  - AskUserQuestion
---

# ok:view

View recent traces.

## Options

- `--last 5m` - Show traces from last 5 minutes
- `--errors` - Only show errors
- `--flat` - Flat list (no tree)
- `--trace-id X` - Specific trace

## Steps

1. If no options provided, **USE AskUserQuestion** to ask what to view
2. Run: `python .claude/scripts/trace_minify.py [options]`
3. Display formatted output

## Interactive Questions - USE AskUserQuestion TOOL

### Ask what to view (if no options provided):
```json
{
  "questions": [{
    "question": "What traces would you like to view?",
    "header": "View Mode",
    "multiSelect": false,
    "options": [
      {"label": "Recent traces (Recommended)", "description": "Show traces from the last 5 minutes"},
      {"label": "Errors only", "description": "Only show traces with errors"},
      {"label": "All traces (flat)", "description": "Show all traces in a flat list"},
      {"label": "Specific trace ID", "description": "View a specific trace by ID"}
    ]
  }]
}
```

### Ask for trace ID (if specific trace selected):
```json
{
  "questions": [{
    "question": "Which trace would you like to view?",
    "header": "Trace ID",
    "multiSelect": false,
    "options": [
      {"label": "abc123 (latest)", "description": "Most recent trace - 2 minutes ago"},
      {"label": "def456", "description": "Previous trace - 5 minutes ago"},
      {"label": "ghi789", "description": "Earlier trace - 10 minutes ago"}
    ]
  }]
}
```
Note: Build options dynamically from available traces in .monocle/ folder.

## Usage Examples

```
/ok:view
/ok:view --last 5m
/ok:view --errors
/ok:view --trace-id abc123
```

## Related Commands

- `/ok:instrument` - Run app to generate traces first
