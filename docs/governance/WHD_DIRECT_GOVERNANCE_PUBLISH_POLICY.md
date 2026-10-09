---
whd_doc_role: CURRENT
whd_contract: direct-governance-publish
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 非產品變更直接發布 X 硬閘門

## 兩條互斥通道

1. **治理直送 `GOVERNANCE_DIRECT_X`**：非產品文件、治理規格、技能、GitHub 工作流程及治理專用測試，必須 **每一個** changed path 命中 `tools/change_lane_gate.py` 的明確白名單。從當前 X 在本地建 `governance/*`、`docs/*` 或 `skills/*` 分支施工、執行針對性測試、push、建立 X PR、檢查完成後 merge；不用 localX、`/推推` 或工單交易。
2. **產品通道 `PRODUCT_LOCALX_ONLY`**：產品程式、GUI、幾何、製造資料、DXF、產品測試、未分類檔案，或同時包含產品與文件的修改，先測試並整合 localX，等待使用者當次明確 `/推推`，由 exact SHA/PR GitHub owner comment 核准後才能合併 X。

## Fail-closed 不可繞過規則

- 空 diff、未知路徑、非法路徑、一份 diff 包含任何產品路徑 → **不能使用治理直送**。
- Git rename/copy 同時檢查原路徑與新路徑；不能把產品檔改名為 Markdown 來騙過白名單。
- 只有指定 repo、正式 X base、同 repo head、符合通道的分支、實際 Git diff 才可通過。
- Product/mixed PR 只能以 `localX` 為 head 且須已完成使用者 exact `/推推`；不能僅靠 PR body、機器人 comment 或舊版核准。
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
