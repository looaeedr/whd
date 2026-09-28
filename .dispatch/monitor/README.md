# WHD runtime observations

This branch is NON_AUTHORITY observability for Flow v2.

Canonical execution authority remains:
`coord/execution-v2:.dispatch/execution/issue-<N>.json`.

Runtime files under `.dispatch/monitor/runtime/` use schema
`WHD_RUNTIME_OBSERVATION_V1` and may contain WAKE / PROGRESS / EXIT state.
They must never grant ownership, leases, mutation, merge, finalization or takeover.

Expected files:
- scheduler-a.json
- scheduler-b.json
- work-0.json
- work-1.json
- work-2.json
- work-3.json
