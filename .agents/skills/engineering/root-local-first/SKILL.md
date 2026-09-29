---
name: root-local-first
description: WHD 互動式與一般開發的 root-first 入口流程。修改、除蟲、更新、新增、測試或推 Git 時，先把 canonical Google Drive `/Google Drive/WHD` 視同本機工作面；所有修改與測試先在 root-backed workspace 完成，只有 exact tested diff GREEN 後才允許 Git write/push。
whd_doc_role: CURRENT
whd_contract: root-local-first-entry
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# root-local-first

## 目的

這個 Skill 把 `/Google Drive/WHD` 的 canonical work root 變成 WHD 一般開發的 **local-first 工作面**。GitHub 仍是 code/PR/CI/control-plane authority，但不是第一個修改或第一個測試面。

canonical entry gate：`/Google Drive/WHD/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json`。
repo mirror：`.agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json`。
machine validator：`tools/root_local_first_gate.py`。

## 固定流程

1. **Root identity**：先完成 `WORK_ROOT_BOOTSTRAP_HARD_GATE_V1`，確認 `/Google Drive/WHD`、folder id 與 Current Source Manifest。
2. **Root source current**：以 Current Source Manifest 做 bootstrap；必要時可把 canonical root materialize 到 runtime filesystem，但 provenance 必須仍指回 `/Google Drive/WHD`，不得把 `/mnt/data` 或 Git checkout 重新命名成 canonical root。
3. **Git write lock**：root 完成前，Git 只准 `READ / FETCH / COMPARE`。`CREATE_OR_UPDATE_FILE / CREATE_COMMIT / UPDATE_REF / PUSH / MERGE` 全部鎖住，狀態為 `LOCKED_UNTIL_ROOT_TESTS_GREEN`。
4. **只在 root 修改**：production、tests、Skill、Registry、治理文件與驗證腳本的施工都先發生在 root-backed work surface；不要先 patch GitHub 再下載回 root 補測。
5. **測試分類**：修改前先分類，並依分類選測試；測試只驗證，不得回灌 production authority。
6. **RED → GREEN**：可客觀驗證的新流程先建立會失敗的 contract，再最小修改到 GREEN。Bugfix 要先有 repro RED；新增/更新至少有新 contract/unit + affected integration。
7. **Root completion evidence**：至少具備 `ROOT_SOURCE_CURRENT → ROOT_MUTATIONS_COMPLETE → ROOT_TEST_CLASSIFIED → ROOT_TESTS_GREEN → ROOT_DIFF_FROZEN`，記錄 source SHA、changed files、test class、root diff SHA256。
8. **Git unlock**：只有 completion evidence VALID 才進 `GIT_WRITE_UNLOCKED`。此時才從最新 authoritative target HEAD 建 Git work branch，並只套用 `EXACT_TESTED_DIFF_ONLY`。
9. **Drift fail closed**：若 touched target path 在 root baseline 後有變動，停止 Git write，回 root 同步並重測；固定 action=`RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE`。
10. **Remote verification**：push 後才跑 PR/CI/GitHub Actions。GitHub Actions 是 post-push verification，**不是第一個測試面**，也不能替代 root GREEN。

## 測試分類

- `GOVERNANCE_OR_SKILL`：focused contract + Preflight/Registry + affected process regression。
- `BUGFIX`：repro RED + focused regression + affected subsystem。
- `UPDATE_OR_FEATURE`：new contract/unit + affected integration。
- `CORE_OR_HIGH_RISK`：full relevant regression；若 release/final acceptance 另有更強 gate，仍要照做。

不要用「每次都跑全部」取代分類，也不要因 focused GREEN 就宣告 release acceptance。分類決定第一輪與必要 regression；高風險或 release 才升級完整矩陣。

## Git 寫入前硬條件

以下五個狀態缺一不可：

- `ROOT_SOURCE_CURRENT`
- `ROOT_MUTATIONS_COMPLETE`
- `ROOT_TEST_CLASSIFIED`
- `ROOT_TESTS_GREEN`
- `ROOT_DIFF_FROZEN`

完成後才可建立 Git work branch。這裡的 branch-first 指的是 **Git integration phase first**：禁止直接寫 target branch，但不再要求在 root-local 第一筆檔案修改前先建 Git branch。

## 禁止

- root GREEN 前用 GitHub Contents API、commit/ref API、push 或 merge 當施工面。
- 把 Git checkout 當未指定時的預設根目錄。
- 把 runtime materialization path 當 canonical root identity。
- root 測完後再偷偷改內容但沿用舊 evidence；任何 diff 改動都要重算 diff hash 並重跑受影響測試。
- target drift 後直接套 patch 或以「只是治理文字」跳過重測。
- 把 remote CI GREEN 冒充 root-local testing evidence。

## 完成定義

完成不是「GitHub 已有 commit」，而是：root source current、root diff 可追溯、分類測試 GREEN、diff frozen、Git write unlock、exact tested diff 已推到 work branch，並完成該任務要求的 remote verification / PR gate。
