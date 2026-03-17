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

## IMPORTANT: Framework Detection First

**ALWAYS run framework detection FIRST.** If monocle-supported frameworks are found, prioritize using monocle's built-in auto-instrumentation. Do NOT reinvent the wheel.

### Monocle Built-in Support

| Category | Frameworks | Instrumentation |
|----------|------------|-----------------|
| LLM Inference | OpenAI, Anthropic, Azure AI, Bedrock, Gemini, LiteLLM, Mistral, HuggingFace | Auto |
| Agent Frameworks | LangChain, LlamaIndex, LangGraph, CrewAI, Haystack, OpenAI Agents, AutoGen | Auto |
| HTTP Frameworks | Flask, FastAPI, AIOHTTP | Auto + decorators |
| Cloud Functions | Azure Functions, AWS Lambda | Decorators required |
| MCP | FastMCP, MCP SDK | Auto |

If ALL code uses supported frameworks → just use `setup_monocle_telemetry()`, no custom YAML needed.

## SKIP PATTERNS - DO NOT INSTRUMENT

**NEVER instrument these:**
- `__init__.py` files - These are package initializers, not business logic
- `__init__` methods - Constructor setup, not traceable operations
- `__str__`, `__repr__`, `__eq__`, etc. - Dunder/magic methods
- Files in `tests/`, `test_*.py`, `*_test.py` - Test files
- Files in `migrations/`, `alembic/` - Database migrations
- Files in `.venv/`, `venv/`, `site-packages/` - Virtual environments

## Steps

1. Ask user for the app folder path (use AskUserQuestion if not provided in arguments)
2. **FIRST: Run framework detection** - `python .claude/scripts/monocle_detector.py <path>`
3. If supported frameworks found:
   - Show what's auto-instrumented vs needs decorators
   - **USE AskUserQuestion**: "Supported frameworks detected. Use auto-instrumentation or continue with custom scan?"
   - If user chooses auto-instrumentation → suggest setup code and skip to step 11
4. Run `python .claude/scripts/ast_parser.py <path> -o <path>/.analyze/ast_data.json --pretty`
5. Run `python .claude/scripts/entry_detector.py <path>/.analyze/ast_data.json`
6. **USE AskUserQuestion** to ask which entry points to analyze (see example below)
7. Run `python .claude/scripts/call_graph.py <path>/.analyze/ast_data.json`
8. Run `python .claude/scripts/relevance_scorer.py .analyze/call_graph.json --entry <selected>`
9. **USE AskUserQuestion** to ask about medium-relevance modules (multiSelect: true)
10. Run `python .claude/scripts/arg_analyzer.py <path>/.analyze/ast_data.json`
11. **USE AskUserQuestion** to ask how to handle large args for each flagged method
12. Save choices to `<path>/.analyze/choices.json`
13. **Write/update `<path>/.analyze/SESSION.md`** with human-readable summary (see format below)
14. Suggest running `/ok:instrument` to generate YAML

## SESSION.md Format - ALWAYS UPDATE

After each /ok: command, write/append to `.analyze/SESSION.md`:

```markdown
# Okahu Instrumentation Session

## Last Updated
YYYY-MM-DD HH:MM

## Scan Results (/ok:scan)
- **App folder**: examples/
- **Entry point selected**: my_app:main
- **Frameworks detected**: None (custom code)
- **High-relevance modules**: my_app, my_functions, my_class
- **Medium modules included**: [list or "skipped"]
- **Large args handling**:
  - PaymentProcessor.charge.metadata → excluded
  - UserService.create.user_data → truncate 100

## Next Steps
- [ ] Run `/ok:instrument` to add tracing (zero-code or code-based)
- [ ] Run `/ok:run <command>` to execute with tracing
- [ ] Run `/ok:local-trace` to check traces
```

This file persists across `/clear` and session exits.

## Interactive Questions - USE AskUserQuestion TOOL

### Framework detection (if supported frameworks found):
```json
{
  "questions": [{
    "question": "Supported frameworks detected. How would you like to proceed?",
    "header": "Frameworks",
    "multiSelect": false,
    "options": [
      {"label": "Use auto-instrumentation (Recommended)", "description": "Just add setup_monocle_telemetry() - no custom YAML needed"},
      {"label": "Continue with full scan", "description": "Also trace custom code alongside frameworks"},
      {"label": "Show setup code", "description": "Display the setup code to add to your app"}
    ]
  }]
}
```

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

- `/ok:instrument` - Generate okahu.yaml from scan results
