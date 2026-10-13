---
whd_doc_role: CURRENT
whd_contract: direct-governance-publish
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 非產品變更直接發布 X 硬閘門

## 兩條互斥通道

1. **治理直送 `GOVERNANCE_DIRECT_X`**：非產品文件、治理規格、技能、GitHub 工作流程及治理專用測試，必須 **每一個** changed path 命中 `tools/change_lane_gate.py` 的明確白名單。從當前 X 優先在 GitHub／雲端 `governance/*`、`docs/*` 或 `skills/*` 分支修改，執行適用檢查後提交 X PR，CI 通過才 merge/readback；不用 localX、`/推推` 或已退役工單交易。未經使用者當次明確授權，不得使用 DC、CoreELEC、whd-dev 或使用者本機 shell；雲端能力不足時回報實際阻塞，不得自行轉用本機。
2. **產品通道 `PRODUCT_LOCALX_ONLY`**：產品程式、GUI、幾何、製造資料、DXF、產品測試、未分類檔案，或同時包含產品與文件的修改，先測試並整合 localX，等待使用者當次明確 `/推推`，由 exact SHA/PR GitHub owner comment 核准後才能合併 X。

### 當次 GitHub-only 產品發布（`GITHUB_ONLY_PUBLISH_EXPLICIT_SCOPE_V1`）

預設產品先在本機 `localX` 安全整合再同步 GitHub；若使用者**當次明確指定 GitHub-only 正式發布、包含新增產品變更及本機同步待辦**，可僅用已整合的 GitHub `localX`，經正式 X PR exact head/base、owner `/推推` comment、必要產品 CI 與 X-only 歷史檢查後合併 X。來源 SHA／產品範圍改變，不沿用舊授權或舊 CI；必須核對新版本與當次授權是否涵蓋。發布後僅以 `expected_sha`、非強制 fast-forward 讓 GitHub `localX` 對齊 X；本機未查只能回報 `GITHUB_ONLY_PUBLISHED + LOCAL_SYNC_PENDING`。此例外**不開放 DC、RC、本機**，不豁免產品測試或 `/推推`，也不把本機同步待辦誤稱完成。

## Fail-closed 不可繞過規則

- 空 diff、未知路徑、非法路徑、一份 diff 包含任何產品路徑 → **不能使用治理直送**。
- Git rename/copy 同時檢查原路徑與新路徑；不能把產品檔改名為 Markdown 來騙過白名單。
- 只有指定 repo、正式 X base、同 repo head、符合通道的分支、實際 Git diff 才可通過。
- **以正式 X 為 base 的產品／混合發布 PR**：head 必須為 `localX`，並具有使用者當次 exact `/推推` 授權；不能僅靠 PR body、機器人 comment 或舊版核准。**以 `localX` 為 base 的一般產品工作 PR**：是正常施工與 CI 驗收流程，不是 X 發布，不需每張另下 `/推推`；仍須依當次 `/派工`／`/接手` 權限及 `AGENTS.md` 的安全整合、同步、回讀規則辦理。不得用這項區分跳過正式 X 發布閘門。
- GitHub Actions 使用 **base SHA 的可信政策程式**，不能直接信任候選 PR 修改後的 gate。
- 本機測試、GitHub Actions 結果及 merge/readback 各自回報；CI GREEN 不等於已合併。

## 平台端必備 Ruleset

要成為 GitHub 平台不可繞過的硬閘門，Repository Ruleset `Protect cleanup/2d-3d-sync` 必須設置：

- Required status check：`WHD Change Lane Gate`（workflow `WHD Change Lane Hard Gate`）。
- 禁止 X 直接 push、禁止 force-push／刪分支，避免繞過 pull request。
- 合併時強制檢查最新 SHA，不允許未測新 commit 或無檢查時合併。

`tools/change_lane_gate.py` + `.github/workflows/whd-change-lane-hard-gate.yml` 是實作 owner；此文件是 policy 規格。若 Ruleset 未將檢查列為 required，CI 只能提供警示／測試失敗，不能聲稱平台層已鎖定。

## 上線後實際檢查

每次僅變更上面白名單文件的獨立治理 PR，`WHD Change Lane Gate` 應回傳 `GOVERNANCE_DIRECT_X / PASS`。
該工作流程讀的是 PR **base X** 中的可信政策程式，而不是候選分支覆寫後的程式。
若修改 GUI、幾何、DXF、產品測試或任何未知檔案，必須由機器判斷為 `PRODUCT_LOCALX_ONLY`，不能用治理直送。
