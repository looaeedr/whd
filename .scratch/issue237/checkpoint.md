# #237 checkpoint

- Base: T5 tested head `296aa4376efa25bae5cc47c51fb6b871eceb720e`
- Durable-rule commit: `d84a46314818c146144e6c9330f370850b0c851b`
- Goal: durable fail-closed QA rules only
- Durable targets: `AGENTS.md`, `monitoring-remote-qa/SKILL.md`, AI long-log pitfall
- Production behavior changes: forbidden
- Runner must now be idempotent: apply step must produce zero worktree diff.
- Validation must see exactly one `QA_PIPELINE_FAIL_CLOSED_V1` marker in each durable target, plus pipefail / immutable-SHA rules and allowed diff only.
