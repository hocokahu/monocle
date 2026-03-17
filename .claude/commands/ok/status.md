---
name: ok:status
description: Check session progress and resume where you left off
argument-hint: [app_folder]
allowed-tools:
  - Read
  - Bash
  - Glob
  - AskUserQuestion
---

# ok:status [app_folder]

Resume an instrumentation session by loading `.analyze/SESSION.md`.

**Use this when:**
- Starting a new Claude session
- After `/clear`
- Returning to a project after a break

## Steps

1. If app_folder not provided, search for `.analyze/SESSION.md` in:
   - Current directory
   - Common locations: `./`, `./src/`, `./app/`, `./examples/`
2. If multiple found, **USE AskUserQuestion** to select which session
3. **Read `.analyze/SESSION.md`** and display current status
4. **Read `.analyze/choices.json`** if exists for detailed decisions
5. Show what's been done and what's next
6. **USE AskUserQuestion** to ask what to do next

## Finding Session Files

```bash
# Search for SESSION.md files
find . -name "SESSION.md" -path "*/.analyze/*" 2>/dev/null
```

## Interactive Questions - USE AskUserQuestion TOOL

### Multiple sessions found:
```json
{
  "questions": [{
    "question": "Multiple instrumentation sessions found. Which one to resume?",
    "header": "Session",
    "multiSelect": false,
    "options": [
      {"label": "examples/.analyze/SESSION.md", "description": "Last updated: 2024-03-16 - my_app scanning"},
      {"label": "src/.analyze/SESSION.md", "description": "Last updated: 2024-03-15 - payment service"},
      {"label": "Start new session", "description": "Run /ok:detect on a new folder"}
    ]
  }]
}
```

### What to do next:
```json
{
  "questions": [{
    "question": "What would you like to do?",
    "header": "Next Step",
    "multiSelect": false,
    "options": [
      {"label": "Continue to /ok:instrument", "description": "Add tracing (zero-code or code-based)"},
      {"label": "Run /ok:run", "description": "Execute app with tracing"},
      {"label": "Re-run /ok:scan", "description": "Redo the codebase scan"},
      {"label": "View SESSION.md details", "description": "Show full session history"}
    ]
  }]
}
```

## Output Format

```
=== Okahu Session Status ===

📁 App folder: examples/
📅 Last updated: 2024-03-16 14:30

✅ Completed:
  - Framework detection: No supported frameworks
  - Codebase scan: my_app:main entry point
  - Modules selected: my_app, my_functions, my_class

⏳ Next steps:
  - [ ] Run /ok:instrument to add tracing
  - [ ] Run /ok:run <command> to execute with tracing

📊 Analysis files:
  - .analyze/ast_data.json (71KB)
  - .analyze/call_graph.json (67KB)
  - .analyze/choices.json (2KB)

What would you like to do? [continue/rescan/view details]
```

## Usage Examples

```
/ok:status                    # Auto-find session in current directory
/ok:status examples/          # Resume session in examples folder
/ok:status src/               # Resume session in src folder
```

## Related Commands

- `/ok:detect` - Start a new session
- `/ok:scan` - Re-run codebase scan
- `/ok:instrument` - Continue to generate okahu.yaml
