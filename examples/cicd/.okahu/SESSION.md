# Okahu Instrumentation Session

## Last Updated
2026-05-01

## App
- **Path**: /Users/quanghoc/Documents/GitHub/monocle/examples/cicd
- **Run command**: `python deploy_app.py`

## Scan Results (/ok-scan)
- **Existing instrumentation**: None
- **Entry point selected**: deploy_app:main (deploy_app.py:43, CLI via __main__)
- **Frameworks detected**: None (pure custom code)

### Methods to Instrument
| # | Module | Method | Args |
|---|--------|--------|------|
| 1 | deploy_app | deploy_azure_blob() | account_name, resource_group, location |
| 2 | deploy_app | AzureSQLDeploy.deploy() | server_name, database_name, resource_group |
| 3 | deploy_app | KustoDeploy.deploy_tables() | cluster_name, database_name, tables |
| 4 | deploy_app | UserAccountProvision.create_accounts() | display_name, principal_name, role |

### Methods Covered (traced as child spans, no separate config needed)
- None — all selected methods are called directly by main

### Arg Handling
- None needed (all args are simple primitives or lists)

## Analysis Files
All in `/Users/quanghoc/Documents/GitHub/monocle/examples/cicd/.okahu/`:
- `ast_data.json` — parsed classes, methods, args
- `call_graph.json` — caller→callee edges
- `entry_points.json` — detected entry points
- `relevance.json` — module relevance scores
- `arg_analysis.json` — large arg flags
- `choices.json` — user selections (methods, arg handling)

## Instrumentation Applied
_Updated by: /ok-instrument_
- **Approach**: Zero-code
- **Config file**: okahu.yaml
- **Methods instrumented**: 4 (read_log removed)

## Run History
_Updated by: /ok-run_
- 2026-05-01: `python deploy_app.py` — zero-code — completed (cloud + local tracing, exit 1 expected from Step 4)
- 2026-05-01: `python deploy_app.py` — zero-code — completed (cloud + local, 4 traces, log content in outputs)
- 2026-05-01: `python deploy_app.py` — zero-code — completed (read_log removed, 4 traces with 2 spans each)

## Next Steps
- [ ] Run `/ok-local-trace` to check traces

---
