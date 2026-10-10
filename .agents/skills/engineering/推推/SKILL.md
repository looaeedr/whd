---
name: 推推
description: WHD 產品修改由 localX /推推 發布；純治理文件採治理直送硬閘門，不需要 /推推。
whd_doc_role: CURRENT
whd_contract: localx-explicit-publish
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /推推 — 產品通道發布授權

產品程式、GUI、幾何、DXF、製造資料、產品測試及混合變更必須依 `/派工`（雲端施工）或 `/接手`（RC 施工）的授權路線完成驗證，最後先整合至**本機** `localX`，再同步 GitHub `localX`。未收到使用者當次 `/推推`，不得把產品改動合併至 `cleanup/2d-3d-sync`。
產品正式發布仍驗證 exact PR、head SHA、target SHA 及 GitHub owner comment，由 `tools/localx_publish_gate.py` 判斷。
**純治理直送例外**：只有 `tools/change_lane_gate.py` 判定為 `GOVERNANCE_DIRECT_X` 的非產品修改，不需要 `/推推`。從最新 X 建立 `governance/*`、`docs/*` 或 `skills/*` 本地分支，檢查後直接 push/PR/merge 至 X；禁止與產品變更混合。
不得用任意的「文檔」文字標籤繞過機器路徑檢查；unknown/mixed = 產品通道。
`/推推 文檔` 和 `/推推 主體` 為相容命令，不能放寬產品通道的人工授權。

## `LOCALX_PUBLISH_THEN_X_BACKSYNC`（發布前不倒灌 X）

1. **Fresh 三方核對**：取得本機 `localX`、GitHub `localX`、正式 X 的 SHA，確認工作樹與未發布修改；先將本機驗證後的 `localX` **非強制推送** GitHub `localX`，回讀一致。若遠端 `localX` 超前或分叉，安全核查與整合後再推，不得覆蓋任何提交。
2. **只檢查 X 獨有歷史、不先合回本機**：正式 X 若領先兩邊 `localX`，必須檢查 X-only **每個 commit** 都是 `GOVERNANCE_DIRECT_X` 白名單內的非本體。任何產品、未知、混合、歷史驗證失敗，`X_AHEAD_NON_GOVERNANCE_BLOCKED`；不得假設 X 超前必然只有文檔。此時**禁止先 pull／merge／rebase X 到 localX**。
3. **由 localX 發布正式 X**：當次使用者 `/推推`、GitHub owner 的 exact PR/head/base SHA、必要 CI 綠燈與無合併衝突都通過時，從 GitHub `localX` PR **merge 進 X**；不得強推，也不能捨棄 X 既有的非本體變更。若 X PR base 變動，重驗授權與 CI，不沿用舊證據。
4. **發布完成後才回同步**：取得 X 的合併後新 SHA，先在本機 `localX` 做 `git fetch` + `git merge --ff-only`（保留未追蹤與本地修改，不 reset），必要驗證後由本機非強制 `git push` 到 GitHub `localX`。
5. **三方 readback**：核實本機 `localX`、GitHub `localX`、X 的 HEAD 完全相同，PR 確實 merged，才回報 `PUBLISHED_AND_SYNCED`；若任何一步遭拒或衝突，回報 `POST_PUBLISH_LOCALX_SYNC_PENDING`、三邊 SHA 與真正阻塞點，不准虛報完成，也不准強制覆寫。
6. **非本體獨立**：治理、技能、純非本體文件直接治理 PR → X，**不經 localX、不使用 /推推**；不能因為由 `/派工`／`/接手` 執行就錯誤改走產品通道。
