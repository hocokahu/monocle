---
name: ok:detect
description: Detect monocle-supported frameworks and suggest instrumentation setup
allowed-tools:
  - Read
  - Bash
  - Write
  - Glob
  - Grep
  - AskUserQuestion
---

# ok:detect

Check what monocle already supports out-of-the-box before custom instrumentation.

## Steps

1. **USE AskUserQuestion** to ask for app folder path (or use current directory if obvious)
2. Run `python .claude/scripts/monocle_detector.py <path>` to scan imports
3. Show what's auto-instrumented vs needs decorators
4. If all supported: suggest setup code and done
5. If custom code found: **USE AskUserQuestion** to ask next step

## Interactive Questions - USE AskUserQuestion TOOL

### Ask for app folder (if not obvious):
```json
{
  "questions": [{
    "question": "Which folder contains your application code?",
    "header": "App Folder",
    "multiSelect": false,
    "options": [
      {"label": "Current directory (Recommended)", "description": "Use the current working directory"},
      {"label": "src/", "description": "Source code in src folder"},
      {"label": "app/", "description": "Application code in app folder"}
    ]
  }]
}
```

### Next steps after detection:
```json
{
  "questions": [{
    "question": "Custom code detected that needs manual instrumentation. What would you like to do?",
    "header": "Next Step",
    "multiSelect": false,
    "options": [
      {"label": "Run /ok:scan (Recommended)", "description": "Full codebase analysis to find what to trace"},
      {"label": "Run /ok:find", "description": "Search for specific methods by description"},
      {"label": "Just use auto-instrumentation", "description": "Skip custom code, only trace supported frameworks"}
    ]
  }]
}
```

## Monocle Built-in Support

| Category | Frameworks | Instrumentation |
|----------|------------|-----------------|
| LLM Inference | OpenAI, Anthropic, Azure AI, Bedrock, Gemini, LiteLLM, Mistral, HuggingFace | Auto |
| Agent Frameworks | LangChain, LlamaIndex, LangGraph, CrewAI, Haystack, OpenAI Agents, AutoGen | Auto |
| HTTP Frameworks | Flask, FastAPI, AIOHTTP | Auto + decorators |
| Cloud Functions | Azure Functions, AWS Lambda | Decorators required |
| MCP | FastMCP, MCP SDK | Auto |

## Output Format

```
=== Monocle Framework Detection ===

Detected in your codebase:

  [x] OpenAI (openai) - AUTO-INSTRUMENTED
     Found in: services/llm_client.py
     Action: Just call setup_monocle_telemetry()

  [!] Custom code needs manual instrumentation:
     - services/payment.py (no framework detected)

Suggested setup:
  from monocle_apptrace import setup_monocle_telemetry
  setup_monocle_telemetry(workflow_name="my_app")
```

## Related Commands

- `/ok:scan` - Full codebase scan if custom code detected
- `/ok:find` - Search for specific methods to trace
