---
name: ok:trace
description: Find all execution paths to a specific method
argument-hint: [class.method]
allowed-tools:
  - Read
  - Bash
  - Write
  - Glob
  - Grep
  - AskUserQuestion
---

# ok:trace [class.method]

Find all execution paths to a specific method.

## Steps

1. If no method specified, **USE AskUserQuestion** to ask for it
2. Run ast_parser and call_graph if needed
3. Find all callers (reverse call graph)
4. Trace back to entry points
5. Present all paths in text output: "Found N paths to <method>..."
6. **USE AskUserQuestion** to select which path(s) to instrument
7. Save to `.analyze/choices.json`
8. Suggest `/ok:plan`

## Interactive Questions - USE AskUserQuestion TOOL

### Ask for method name (if not provided):
```json
{
  "questions": [{
    "question": "Which method do you want to trace? Enter the full class.method name.",
    "header": "Method",
    "multiSelect": false,
    "options": [
      {"label": "db.UserRepo.save", "description": "Database user save operation"},
      {"label": "services.PaymentService.charge", "description": "Payment processing"},
      {"label": "auth.TokenValidator.validate", "description": "Authentication token validation"}
    ]
  }]
}
```
Note: Build options dynamically from ast_data.json based on common patterns.

### Path selection:
```json
{
  "questions": [{
    "question": "Which execution path(s) should be instrumented?",
    "header": "Paths",
    "multiSelect": true,
    "options": [
      {"label": "Path A (Recommended)", "description": "main:main -> cli.import_users -> [target]"},
      {"label": "Path B", "description": "api.routes:create_user -> services.UserService.create -> [target]"},
      {"label": "Path C", "description": "api.routes:update_user -> services.UserService.update -> [target]"},
      {"label": "All paths", "description": "Instrument all execution paths to this method"}
    ]
  }]
}
```

## Usage Examples

```
/ok:trace db.UserRepo.save
/ok:trace PaymentService.charge
/ok:trace auth.validate_token
```

## Related Commands

- `/ok:find` - Search for methods if you don't know the exact name
- `/ok:plan` - Generate monocle.yaml from selected paths
