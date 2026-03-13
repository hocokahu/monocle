---
name: ok:plan
description: Generate monocle.yaml configuration from analysis
allowed-tools:
  - Read
  - Bash
  - Write
  - Glob
  - Grep
  - AskUserQuestion
---

# ok:plan

Generate monocle.yaml from analysis.

## Steps

1. Read `.analyze/choices.json` and analysis files
2. Apply user choices (modules, args, paths)
3. Generate monocle.yaml with:
   - Selected methods
   - Arg filters (include/exclude/truncate)
   - Output extractors
4. Show preview of generated YAML in text output
5. **USE AskUserQuestion** to confirm or request edits (see example below)
6. Write `monocle.yaml`

## Interactive Questions - USE AskUserQuestion TOOL

### Confirm generated YAML:
```json
{
  "questions": [{
    "question": "Does this monocle.yaml configuration look correct?",
    "header": "Confirm",
    "multiSelect": false,
    "options": [
      {"label": "Yes, save it (Recommended)", "description": "Write monocle.yaml to the target directory"},
      {"label": "Edit workflow_name", "description": "Change the workflow name before saving"},
      {"label": "Add more methods", "description": "Include additional methods in instrumentation"},
      {"label": "Remove some methods", "description": "Exclude some methods from instrumentation"}
    ]
  }]
}
```

## Generated YAML Format

```yaml
workflow_name: my_app

instrument:
  - package: billing.processor
    class: PaymentProcessor
    method: charge
    span_name: payment.charge

    inputs:
      include: [amount, card_token]
      exclude: [metadata, logger]
      truncate:
        card_token: 4

    output:
      extract: [transaction_id, status]
```

## Scripts

- `.claude/scripts/yaml_generator.py` - Generate monocle.yaml

## Related Commands

- `/ok:scan` - Run scan first if no analysis exists
- `/ok:instrument` - Run app with generated config
