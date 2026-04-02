# Monocle Claude Code Hook

Observe Claude Code CLI sessions with Monocle tracing. Captures prompts, responses, tool calls, and subagent activity with proper span hierarchy.

## Features

- **Session correlation** - All spans grouped under `agentic.session` scope
- **Turn tracking** - Each user→assistant cycle as `agentic.turn` span
- **Inference spans** - LLM calls with model, tokens, and cache usage
- **Tool spans** - Read, Write, Bash, etc. with input/output
- **Subagent tracking** - Agent tool spawns linked to child traces
- **MCP tool support** - MCP server calls as `agentic.mcp.invocation`

## Quick Start

### 1. Install Dependencies

```bash
pip install monocle_apptrace
```

### 2. Set Environment Variables

```bash
# Required for Okahu export
export OKAHU_API_KEY="your-api-key"
export OKAHU_INGESTION_ENDPOINT="https://ingest.okahu.co/api/v1/trace/ingest"
export MONOCLE_EXPORTER="okahu"

# Optional
export MONOCLE_SERVICE_NAME="claude-cli"
export MONOCLE_CLAUDE_DEBUG="true"
```

### 3. Install Hook

**Option A: Run install script**

```bash
cd examples/scripts/claude_code_hook
./install.sh
```

**Option B: Manual installation**

```bash
# Create hooks directory
mkdir -p ~/.claude/hooks

# Copy hook script
cp monocle_hook.py ~/.claude/hooks/

# Add to Claude Code settings
cat >> ~/.claude/settings.json << 'EOF'
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
EOF
```

### 4. Verify

Start a Claude Code session and check logs:

```bash
tail -f ~/.claude/state/monocle_hook.log
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONOCLE_CLAUDE_ENABLED` | Enable/disable hook | `true` |
| `MONOCLE_EXPORTER` | Exporter(s): okahu, file, console, otlp | `okahu` |
| `OKAHU_INGESTION_ENDPOINT` | Okahu endpoint URL | - |
| `OKAHU_API_KEY` | Okahu API key | - |
| `MONOCLE_SERVICE_NAME` | Service name in spans | `claude-cli` |
| `MONOCLE_CLAUDE_MAX_CHARS` | Max chars for tool output | `20000` |
| `MONOCLE_CLAUDE_DEBUG` | Enable debug logging | `false` |

### Claude Code Settings

Location: `~/.claude/settings.json`

```json
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
```

## Span Types

| Span | Type | Description |
|------|------|-------------|
| Turn | `agentic.turn` | User→assistant interaction cycle |
| Inference | `inference` | LLM call with tokens |
| Tool | `agentic.tool.invocation` | Read, Write, Bash, etc. |
| Agent | `agentic.invocation` | Subagent spawn |
| MCP | `agentic.mcp.invocation` | MCP server tool call |

## Span Attributes

### Turn Span
```
span.type: agentic.turn
scope.agentic.session: <session-id>
turn.number: 1
monocle.service.name: claude-cli
```

### Inference Span
```
span.type: inference
gen_ai.system: anthropic
gen_ai.request.model: claude-opus-4-5-20251101
gen_ai.response.id: msg_xxx
gen_ai.usage.input_tokens: 1500
gen_ai.usage.output_tokens: 250
gen_ai.usage.cache_read_tokens: 11282
gen_ai.usage.cache_creation_tokens: 759
```

### Tool Span
```
span.type: agentic.tool.invocation
tool.name: Read
tool.id: toolu_xxx
```

## Files

| Path | Description |
|------|-------------|
| `~/.claude/hooks/monocle_hook.py` | Main hook script |
| `~/.claude/state/monocle_hook.log` | Debug log file |
| `~/.claude/state/monocle_state.json` | Incremental state |
| `~/.claude/settings.json` | Claude Code settings |

## Troubleshooting

### Hook not running

1. Check settings.json is valid JSON
2. Verify hook path exists: `ls ~/.claude/hooks/monocle_hook.py`
3. Check log: `cat ~/.claude/state/monocle_hook.log`

### No spans exported

1. Check environment variables are set
2. Verify OKAHU_API_KEY is valid
3. Enable debug: `export MONOCLE_CLAUDE_DEBUG=true`

### Permission errors

```bash
chmod +x ~/.claude/hooks/monocle_hook.py
```

## Architecture

```
Claude Code CLI
       │
       │ (writes)
       ▼
Transcript JSONL
~/.claude/projects/{hash}/{session}.jsonl
       │
       │ (Stop hook fires)
       ▼
monocle_hook.py
       │
       ├─ Parse new JSONL records
       ├─ Build turns (user→assistant)
       ├─ Match tool_use with tool_result
       ├─ Discover subagent transcripts
       └─ Emit OpenTelemetry spans
              │
              ▼
       Okahu / OTLP Backend
```

## Comparison with Langfuse

| Feature | Langfuse | Monocle |
|---------|----------|---------|
| Subagent traces | No | Yes |
| Session scope | Basic ID | `agentic.session` |
| Token tracking | No | Full (incl. cache) |
| Span types | Generic | Rich (inference, tool, etc.) |
| Model per inference | No | Yes |

## License

Apache 2.0
