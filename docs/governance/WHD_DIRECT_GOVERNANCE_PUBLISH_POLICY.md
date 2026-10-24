---
whd_doc_role: CURRENT
whd_contract: direct-governance-publish
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 治理與產品由 GitHub localX 正式發布 X

## 兩條驗收通道，單一發布來源

1. **治理／技能／文件專用變更**：從最新 GitHub `localX` 建工作分支，適用治理 CI 通過後 PR 合併 GitHub `localX`；不因檔案命中治理白名單直接合併正式 X。發佈正式 X 必須使用者當次 `/推推`，GitHub 精確 owner 授權及受信任 X gate。
2. **產品通道 `PRODUCT_LOCALX_ONLY`**：產品程式、GUI、幾何、製造資料、DXF、產品測試、未分類檔案，或任何產品與文件混合的變更，先完成適用產品 CI 並整合 GitHub `localX`，再由使用者當次 `/推推`（即驗收與授權）經 X PR exact SHA/head/base、owner comment 及必要 CI 發布。**Windows 本機 UAT／同步不作為前置阻擋。**

## `/推推` 預設 GitHub-only；舊授權例外已退役

`LOCALX_PUBLISH_THEN_X_BACKSYNC` 與 `GITHUB_ONLY_PUBLISH_EXPLICIT_SCOPE_V1` 為保留的歷史識別：從前「本機優先」及「額外 GitHub-only 授權」的操作要求不再有效。**普通 `/推推` 就是 GitHub-only 正式發布授權，不需第二次口令或本機存取許可。** 先確認 GitHub `localX` 已整合的 scope、fresh SHA、正式 X-only 歷史、必要 CI、GitHub owner `/推推` 精確留言、mergeable；來源 HEAD／範圍變更時，重新檢查並更新該版本的證據，不沿用舊 SHA。

正式 X PR 合併後僅用 `expected_sha`、非強制 fast-forward 更新**遠端** GitHub `localX` 對齊 X。本機不可由普通 `/推推` 自動讀取或修改；未查驗標 UNKNOWN／`LOCAL_SYNC_PENDING`。不得把本機待辦誤稱完成；不豁免產品測試，也不豁免 X trusted policy／Ruleset。最後依 `LOCALX_PUBLISH_OFFICIAL_RELEASE_V1` 驗證正式 GitHub Release/tag：只有公開 Release 存在且精確指向 X merge SHA 才回報 `OFFICIAL_RELEASED`。

## Fail-closed 不可繞過規則

- `GOVERNANCE_DIRECT_X` 只供既有紀錄分類，**已退役，不是可執行的 X 快車道**。空 diff、未知路徑、非法路徑、一份 diff 包含任何產品路徑均不能以治理名義跳過產品 CI。
- Git rename/copy 同時檢查原路徑與新路徑；不能把產品檔改名為 Markdown 來騙過白名單。
- 只有指定 repo、正式 X base、同 repo head、實際 Git diff 與受信任狀態才可通過。X-only 獨有提交若含產品、未知或混合變更且未安全查證，必須阻止發布，不能強制同步。
- **以正式 X 為 base 的產品／混合發布 PR**：head 必須為 `localX`，並具有使用者當次 exact `/推推` 授權；不能僅靠 PR body、機器人 comment 或舊版核准。**以 `localX` 為 base 的一般產品工作 PR**：是正常施工與 CI 驗收流程，不是 X 發布，不需每張另下 `/推推`；仍須依當次 `/派工`／`/接手` 授權、安全整合與遠端回讀。不得用這項區分跳過正式 X 發布閘門。
- GitHub Actions 使用 **base SHA 的可信政策程式**，不能直接信任候選 PR 修改後的 gate。
- 本機測試、GitHub Actions 結果及 merge/readback 各自回報；CI GREEN 不等於已合併，PR merged 也不等於正式 GitHub Release 已發布。

## 平台端必備 Ruleset

Repository Ruleset `Protect cleanup/2d-3d-sync` 應要求：

- Required status check：`WHD Change Lane Gate`（workflow `WHD Change Lane Hard Gate`）。
- 禁止 X 直接 push、禁止 force-push／刪分支；必須 PR。
- 合併時重新檢查當下 SHA、必要 CI、owner 授權，不接受未測新 commit。

`tools/change_lane_gate.py` + `.github/workflows/whd-change-lane-hard-gate.yml` 是 trusted X gate 實作 owner；`tools/localx_publish_gate.py` 與 `.github/workflows/whd-official-release.yml` 驗證精確 `/推推` 和最終正式 Release。本文件只是規格，不能單靠文字宣稱平台 Ruleset 已啟用。

## 現行稽核

治理 PR 應以 GitHub `localX` 為 base，跑適用治理 CI 後合併 `localX`；若涉及 GUI、幾何、DXF、產品測試、unknown/mixed，必須走 `PRODUCT_LOCALX_ONLY`。正式 X 發布統一依使用者當次 `/推推` 及受信任 gate，不存在額外 GitHub-only／Windows UAT 前置。
