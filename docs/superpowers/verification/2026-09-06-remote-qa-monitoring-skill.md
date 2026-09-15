# Remote QA Monitoring Skill Verification

Date: 2026-09-06
Branch: cleanup/2d-3d-sync

## User requirement
When synchronizing to remote and starting remote QA, activate a monitoring skill so the agent does not stop after merely triggering GitHub Actions.

## Implementation
- Added `.agents/skills/engineering/monitoring-remote-qa/SKILL.md`.
- Added registry route `remote-qa-monitoring` for remote QA / GitHub Actions / workflow-run language.
- Dispatching now declares `**REQUIRED SUB-SKILL:** monitoring-remote-qa` for remote QA.
- AGENTS bootstrap now names both remote-sync fallback and remote-QA monitoring skills.
- Added `tests/test_remote_qa_monitoring_skill_contract.py`.

## TDD evidence
RED:
- `tests/test_remote_qa_monitoring_skill_contract.py` -> 1 failed because the monitoring skill did not exist.

GREEN:
- local contract -> 1 passed.
- changed-file Skill Preflight -> PASS.

## Remote monitored QA
Initial run:
- run 34022198454
- monitoring contract: PASS
- dispatch contract: PASS
- preflight gate: FAIL because AGENTS.md was already missing the literal git-remote-sync fallback skill path required by an existing test.

Fix:
- restored the existing git-remote-sync skill path in AGENTS.md and added the new monitoring skill path.

Replacement run:
- run 34022240801
- head: 20197d903628e463b5450413f1263059c36207f8
- monitoring skill contract: 1 PASS
- dispatch timeout/monitoring contract: 8 PASS
- Skill Preflight registry gate: 13 PASS
- total: 22 PASS / 0 FAIL

## Cleanup
- one-shot trigger removed
- one-shot workflow removed
- remote reread confirmed both paths absent

## Completion contract
Remote QA trigger is now the *start* of monitoring. QA cannot be accepted while the run is queued/in-progress, failed logs are unread, temporary workflow files remain, or durable terminal evidence has not been written.
