# DM6 / T1 Checkpoint

Task ID: DM6
Work order: #65 / T1
Current role: PM preparing executable RED evidence
Owning branch: `work/dm6-t1-annotation-semantic-contract`
Dispatch base: `f465dffabc7c381eef106d7d3dc24a22ba2c72c9`
Latest known commit before this checkpoint: `a46d0d83a81bd0bb38f8ceab9e5273a98d341c52`

Completed:
- Read dispatch / ticket / deep-scan / remote-QA rules.
- Read global pitfall library and DM scan AI Library rule.
- Added requirement-level RED tests in `tests/test_dm6_annotation_semantic_contract.py`.
- Recorded preflight evidence.

Pending:
- Create one-shot GitHub Actions RED workflow.
- Capture `run_id + head_sha`.
- Poll run -> jobs -> steps to terminal.
- Fetch failed-job logs and record exact intended RED failures.
- Present RED matrix for user approval before production code.

Failed/blocked:
- None. Previous local-runtime blocker assessment was incorrect; remote Actions is the executable test surface.

Relevant files:
- `tests/test_dm6_annotation_semantic_contract.py`
- `.scratch/dm6-t1/preflight-evidence.md`
- `.scratch/dm6-t1/checkpoint.md`
- `.scratch/dm6-t1/state.json`

Verification command:
`python -m pytest -q tests/test_dm6_annotation_semantic_contract.py`

Resume command:
Re-read `.scratch/dm6-t1/state.json`, then query the recorded GitHub Actions `run_id + head_sha`; do not create a replacement run while the recorded run is non-terminal.
