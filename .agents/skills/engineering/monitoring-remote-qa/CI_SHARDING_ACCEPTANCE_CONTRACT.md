---
whd_doc_role: REFERENCE
whd_contract: ci-sharding-acceptance-contract
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# CI Sharding / Parallel Acceptance Contract

This REFERENCE preserves #303/T8 CI qualification and historical integration evidence; it is **not a separate CURRENT execution, branch, merge or user-authorization policy**. For current actions use formal-X `AGENTS.md`, `.agents/skills/engineering/monitoring-remote-qa/SKILL.md`, `.agents/skills/engineering/派工/SKILL.md`, and `.agents/skills/engineering/推推/SKILL.md`. Sharding evidence below remains useful; if old process wording conflicts, the CURRENT owners control routing.

## Run identity and monitoring

- **NO RUN IDENTITY => NO WAIT.** If no concrete workflow `run_id + head_sha` exists, classify the state as `RUN_NOT_CREATED`; immediately diagnose and execute/fix the prerequisite that should create the run. Do not poll an absent run.
- Once a concrete non-terminal run exists, lock to that exact `run_id + head_sha` and actively poll it. The user is not the scheduler. Normal user-visible observation cadence is approximately 30 seconds.

## Deterministic shard ownership

- Collect the canonical test manifest once and share that exact artifact with all shard jobs. Do not let each shard independently recollect ownership.
- Require `FULL_COLLECTION == UNIQUE_SHARD_UNION`. Missing nodes and duplicate ownership are fail-closed errors.
- Never assign ownership with collection-index modulo or Python's built-in `hash()`.
- Default deterministic owner selection is HRW/Rendezvous hashing. Duration-aware weighted/LPT balancing is allowed only from measured, versioned timing evidence.
- Declare and enforce an explicit `CI_CONCURRENCY_BUDGET` / `max-parallel`; do not assume unlimited runner capacity.
- Rebalancing must be evidence-driven from measured shard durations, not intuition.

## Execution isolation and classification

- Keep GUI/Xvfb execution isolated from non-GUI shards and preserve required serial/state-isolation contracts.
- Result capture must be fail-safe: preserve node IDs, JUnit/result artifacts, exit status and unresolved classifications even when a shard fails.
- `CLASSIFICATION_NOT_RUN` is not automatically HANG or TIMEOUT. A hang/timeout classification requires actual timeout evidence.
- A retry that turns the first RED into GREEN remains `[FLAKY-WARNING]`; do not silently erase the initial failure.
- Inherited baseline RED must match the authoritative inherited set exactly. New failures, missing inherited failures, or changed node identity fail closed.

## Acceptance evidence

- Produce a one-page Unified Summary in `$GITHUB_STEP_SUMMARY` containing collection, shard union, pass/fail/skip/inherited-RED counts, missing/duplicate nodes, protected drift, timing and final gate.
- Timing vocabulary is fixed: `EXECUTION_WALL_CLOCK` measures execution; `END_TO_END_WALL_CLOCK` includes queue/setup as defined by the workflow; queue time is reported separately. Do not compare unlike timing definitions.
- Legacy-vs-optimized A/B acceptance must execute the **same exact source SHA** and equivalent authoritative test collection/contracts.
- Preserve protected invariants such as `config.ini`, protected DXF/baseline files and tracked-tree constraints. Validation evidence must never become a production geometry/calculation source.

## Cleanup and integration

- Cleanup occurs only after acceptance evidence is durable.
- Immediately before deleting any branch, perform a fresh OPEN-PR protection readback for both `head.ref` and `base.ref`; never delete a branch referenced by an open PR and never fake deletion by moving refs.
- **Historical #303/T8 routing only:** the former rules said “Every modification starts on a fresh branch” and “Final production integration requires the user's explicit `合`.” Neither sentence is a current WHD branch or release authorization requirement.
- **Current routing:** for an existing Issue/PR, continue the authorized work branch; new isolated work uses a new branch. Product PRs target `localX`; after exact CI SUCCESS, same-scope authorized work defaults to GitHub localX merge without DC. Explicit scoped DC access still requires external platform approval. Product `localX → cleanup/2d-3d-sync` requires fresh `/推推` and Windows manual acceptance; the trusted formal-X gate currently also requires governance changes to enter X through localX, not the retired direct lane. `GO`, `繼續`, QA GREEN, or issue closure does not create missing merge/publish permission.
- Integration must preserve qualified history and current production governance/continuity rules; do not use force updates to bypass conflicts.
