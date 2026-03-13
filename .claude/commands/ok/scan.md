---
name: ok:scan
description: Full codebase scan to recommend what to trace
allowed-tools:
  - Read
  - Bash
  - Write
  - Glob
  - Grep
  - AskUserQuestion
---

# ok:scan

Full codebase analysis to recommend what to trace.

## Steps

1. Ask user for the app folder path (use AskUserQuestion if not provided in arguments)
2. Run `python .claude/scripts/ast_parser.py <path> -o <path>/.analyze/ast_data.json --pretty`
3. Run `python .claude/scripts/entry_detector.py <path>/.analyze/ast_data.json`
4. **USE AskUserQuestion** to ask which entry points to analyze (see example below)
5. Run `python .claude/scripts/call_graph.py <path>/.analyze/ast_data.json`
6. Run `python .claude/scripts/relevance_scorer.py .analyze/call_graph.json --entry <selected>`
7. **USE AskUserQuestion** to ask about medium-relevance modules (multiSelect: true)
8. Run `python .claude/scripts/arg_analyzer.py <path>/.analyze/ast_data.json`
9. **USE AskUserQuestion** to ask how to handle large args for each flagged method
10. Save choices to `<path>/.analyze/choices.json`
11. Suggest running `/ok:plan` to generate YAML

## Interactive Questions - USE AskUserQuestion TOOL

### Entry point selection:
```json
{
  "questions": [{
    "question": "Which entry point should I analyze for tracing?",
    "header": "Entry Point",
    "multiSelect": false,
    "options": [
      {"label": "main.py:main (Recommended)", "description": "CLI entry - reaches 45 methods"},
      {"label": "api/app.py:create_app", "description": "Flask app - reaches 120 methods"},
      {"label": "All entry points", "description": "Analyze all detected entry points"}
    ]
  }]
}
```

### Module relevance (use multiSelect):
```json
{
  "questions": [{
    "question": "Which medium-relevance modules should be included in tracing?",
    "header": "Modules",
    "multiSelect": true,
    "options": [
      {"label": "utils/validation.py", "description": "Called 12x by 5 modules - Pure validation logic"},
      {"label": "helpers/formatting.py", "description": "Called 8x by 3 modules - String formatting"},
      {"label": "Skip all medium modules", "description": "Only trace high-relevance modules"}
    ]
  }]
}
```

### Large argument handling:
```json
{
  "questions": [{
    "question": "How should large arguments be handled for PaymentProcessor.charge()?",
    "header": "Arg Handling",
    "multiSelect": false,
    "options": [
      {"label": "Include full value", "description": "Capture entire argument (may be large)"},
      {"label": "Exclude entirely", "description": "Don't capture this argument"},
      {"label": "Extract specific keys", "description": "Only capture certain keys from dict/object"},
      {"label": "Truncate to 100 chars", "description": "Capture first 100 characters only"}
    ]
  }]
}
```

## Scripts Location

Helper scripts are in `.claude/scripts/`:
- `ast_parser.py` - Extract classes, methods, args from Python code
- `call_graph.py` - Build caller->callee relationships
- `entry_detector.py` - Find main, routes, workers
- `relevance_scorer.py` - Score module importance
- `arg_analyzer.py` - Flag large/useless arguments

Analysis output goes to `.analyze/` folder in the target directory.

## Related Commands

- `/ok:plan` - Generate monocle.yaml from scan results
