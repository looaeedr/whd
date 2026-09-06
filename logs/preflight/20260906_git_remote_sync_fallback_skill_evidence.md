# Git Remote Sync Fallback Skill Evidence

- task: 將容器無法解析 GitHub DNS、無法直接 git push 時的正確 GitHub Connector fallback 流程固化為專案 Skill。
- backup: backup-20260906-115308
- source_head: 8d15cef04d4af6993fbb27e1bbf4e28da1a29788

phase6-release-packaging
diagnosing-bugs
tdd
git-remote-sync-fallback
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: release_required_artifacts.json

## RED
- Static contract check failed before implementation:
  - registry route `git-remote-sync-fallback` missing.
  - `.agents/skills/misc/git-remote-sync-fallback/SKILL.md` missing.
- Persistent regression test initially failed with `KeyError: 'git-remote-sync-fallback'`.

## GREEN
- Added dedicated `git-remote-sync-fallback` Skill.
- Added registry route for `git push`, `GitHub Connector`, `DNS`, `remote sync`, related transport symptoms.
- Added fail-closed language distinguishing GitHub Connector content synchronization from real `git push` / local commit identity.
- Added partial-success recovery rule: re-read remote before retry; never blindly replay a failed connector batch.
- Added remote HEAD / force=false / remote second-verification requirements.
- Added new Skill to `release_required_artifacts.json:mandatory_update_files`.
- Added pitfall #90 to the global lessons database.

## Verification
- `python -m pytest -q tests/test_phase6_skill_preflight_gate.py` -> 13 passed.
- Final changed-file Phase6 Knowledge Preflight -> all required skills/references PASS.
