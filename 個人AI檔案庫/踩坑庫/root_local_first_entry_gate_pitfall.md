---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Root-local-first 入口硬閘門踩坑

## 2026-09-29 — workspace-first 與 branch-before-write 同時 CURRENT

- **事故模式**：Flow v2 / work-root 已要求 `/Google Drive/WHD` 作 interactive workspace，但 AGENTS、Skills 與 contract tests 仍要求第一次 repository write 前先建 Git work branch。結果同一任務同時存在兩個相反順序。
- **根因**：舊 branch policy 沒有被降級成 Git-phase-only，且 tests 還把 `branch-first` 關鍵字當正向 invariant。
- **永久規則**：interactive/default content work 唯一順序為 `ROOT_SOURCE_CURRENT → PATHS_RESERVED → ROOT_MUTATIONS_COMPLETE → ROOT_TEST_CLASSIFIED → ROOT_TESTS_GREEN → ROOT_DIFF_FROZEN → GIT_WRITE_UNLOCKED`；新 READY work 以 atomic `ACQUIRE.effect.admission_reservation` 取得 live lease + ACTIVE mutation scope，fresh Git work branch 只在 unlock 後建立。
- **Git phase invariant**：仍禁止直接寫 `cleanup/2d-3d-sync` / `main`；unlock 後只允許 `EXACT_TESTED_DIFF_ONLY`。
- **source freshness**：Drive full snapshot 若落後，只可作 bootstrap base；manifest 必須標示真實 source SHA/tree，未證明 current 的 touched path 不得修改。
- **remote scope**：`SCHEDULER_LANE / GITHUB_ONLY / REMOTE_ACTION` 仍依 Flow v2 remote authority；不得拿 remote mode 當 interactive content-work bypass。
- **machine owner**：`tools/root_local_first_gate.py` + `tests/process/test_root_local_first_entry_hard_gate.py`。
