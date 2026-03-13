---
name: ok:find
description: Semantic search for methods matching a description
argument-hint: [query]
allowed-tools:
  - Read
  - Bash
  - Write
  - Glob
  - Grep
  - AskUserQuestion
---

# ok:find [query]

Search for methods matching a natural language description.

## Steps

1. If no query provided, **USE AskUserQuestion** to ask for description
2. Run `python .claude/scripts/ast_parser.py <path>` if not already done
3. Search class/method names, docstrings for matches
4. Rank by relevance to query
5. Present candidates in text output: "Found N matches..."
6. **USE AskUserQuestion** to select which methods to trace
7. Find paths from entry points to selected methods
8. Save to `.analyze/choices.json`
9. Suggest `/ok:plan`

## Interactive Questions - USE AskUserQuestion TOOL

### Ask for search query (if not provided):
```json
{
  "questions": [{
    "question": "What kind of methods are you looking for?",
    "header": "Search",
    "multiSelect": false,
    "options": [
      {"label": "Payment processing", "description": "Methods related to payments, billing, charges"},
      {"label": "Database operations", "description": "Methods for CRUD, queries, transactions"},
      {"label": "User authentication", "description": "Methods for login, tokens, sessions"},
      {"label": "API endpoints", "description": "Route handlers and controllers"}
    ]
  }]
}
```

### Method selection:
```json
{
  "questions": [{
    "question": "Which methods should be traced?",
    "header": "Methods",
    "multiSelect": true,
    "options": [
      {"label": "billing.Processor.charge (Recommended)", "description": "Score: 0.95 - 'Process a payment charge'"},
      {"label": "orders.Order.process_payment", "description": "Score: 0.82 - 'Handle order payment'"},
      {"label": "checkout.Cart.finalize", "description": "Score: 0.71 - 'Complete checkout with payment'"},
      {"label": "All matches", "description": "Trace all methods matching the query"}
    ]
  }]
}
```

## Usage Examples

```
/ok:find payment flow
/ok:find database operations
/ok:find user authentication
/ok:find error handling
```

## Related Commands

- `/ok:trace` - Find all paths to a specific method
- `/ok:plan` - Generate monocle.yaml from selections
