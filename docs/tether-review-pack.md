# Tether Review Pack

## Project pitch

Tether is a lightweight local coding agent harness for repository-grounded engineering tasks. It wraps a model with workspace context, explicit tools, state tracking, memory, run artifacts, and benchmark evidence.

## Architecture map

- `tether.cli` wires configuration, provider clients, workspace context, and the runtime.
- `tether.runtime.Tether` coordinates the agent control surface.
- `tether.context_manager` builds bounded model context from prefix, memory, history, and the current request.
- `tether.tools` defines the explicit tool allowlist used by the runtime.
- `tether.run_store` writes per-run artifacts for review and replay.

## Benchmark evidence

Benchmark runs should preserve reproducibility metadata, task rows, summary counts, and failure categories so reviewers can distinguish runtime regressions from task or provider failures.

## Sample run artifact list

- `.tether/runs/<run_id>/task_state.json`
- `.tether/runs/<run_id>/trace.jsonl`
- `.tether/runs/<run_id>/report.json`
