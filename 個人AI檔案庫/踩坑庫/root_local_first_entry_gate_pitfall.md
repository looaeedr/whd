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

## 2026-10-01 — TEST_RED 語意缺口讓聊天層重新長回逐顆 Flow v2 transaction

- **事故模式**：interactive fast path 雖禁止平常逐顆 transaction，卻把 `TEST_RED` 列入「可離開 fast path 升級完整治理」。結果 QA RED 後，操作員會重新手送 `FAIL_QA → RECONCILE → START_QA...`，把 generation / lease / CAS / workflow round-trip 暴露回聊天層。
- **根因**：把「產品需要 repair」和「外層 orchestration 需要切換成治理模式」混成同一 escalation。
- **永久規則**：`TEST_RED` 固定為 `RETURN_TO_ROOT_REPAIR_IN_SAME_SESSION → ROOT_MUTATE`；修正、重測、refreeze、repush 仍沿 session fast path。
- **machine-only transition**：FAIL_QA 是 machine-internal consume。需要保存 terminal failure 時，`FAIL_QA` / failure consume 由 trusted session/executor 內部吸收，不是 user-visible / chat-issued action。
- **anti-regrowth**：任何 escalation 都不得授權 `PER_TRANSACTION_MANUAL_ORCHESTRATION`；真正 escalation 只剩 `PATH_CONFLICT / SAME_ISSUE_OTHER_WRITER / SUBSTANTIVE_TARGET_OVERLAP / MACHINE_FAIL_CLOSED / USER_INPUT_REQUIRED`。
- **machine owner**：`tools/root_local_first_gate.py::classify_interactive_fast_path_event` + `tests/process/test_root_local_first_entry_hard_gate.py`。

