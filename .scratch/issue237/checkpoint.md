# #237 checkpoint

- Base: T5 tested head `296aa4376efa25bae5cc47c51fb6b871eceb720e`
- Goal: durable fail-closed QA rules only
- Durable targets: `AGENTS.md`, `monitoring-remote-qa/SKILL.md`, AI long-log pitfall
- Production behavior changes: forbidden
- Runner must preserve UTF-8 paths in allowed-diff checks and remain fail-closed.
