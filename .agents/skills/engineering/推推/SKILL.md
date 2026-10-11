---
name: 推推
description: WHD 產品修改由 localX /推推 發布；純治理文件採治理直送硬閘門，不需要 /推推。
whd_doc_role: CURRENT
whd_contract: localx-explicit-publish
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /推推 — 產品通道發布授權

產品程式、GUI、幾何、DXF、製造資料、產品測試及混合變更，預設依 `/派工`（雲端施工）或 `/接手`（RC 施工）路線驗證並先整合至**本機** `localX`，再同步 GitHub `localX`；只有使用者**當次明確指定 GitHub-only 發布及本機同步待辦**時，才適用下方 `GITHUB_ONLY_PUBLISH_EXPLICIT_SCOPE_V1`。未收到當次 `/推推` 授權，不得發布產品至正式 X。
產品正式發布仍驗證 exact PR、head SHA、target SHA 及 GitHub owner comment，由 `tools/localx_publish_gate.py` 判斷。
**純治理直送例外**：只有 `tools/change_lane_gate.py` 判定為 `GOVERNANCE_DIRECT_X` 的非產品修改，不需要 `/推推`。從最新正式 X 以 GitHub／雲端建立 `governance/*`、`docs/*` 或 `skills/*` 治理分支，檢查後直接 push/PR/merge 至 X；禁止與產品變更混合。
不得用任意的「文檔」文字標籤繞過機器路徑檢查；unknown/mixed = 產品通道。
`/推推 文檔` 和 `/推推 主體` 為相容命令，不能放寬產品通道的人工授權。

## `LOCALX_PUBLISH_THEN_X_BACKSYNC`（發布前不倒灌 X）

1. **預設 fresh 三方核對**：取得本機 `localX`、GitHub `localX`、正式 X 的 SHA，確認工作樹與未發布修改；先以非強制方式同步本機已驗證的 `localX` 至 GitHub。**當次明確 GitHub-only** 則只讀 GitHub `localX`／X 與 PR exact SHA，保留本機 UNKNOWN／`LOCAL_SYNC_PENDING`；禁止藉本技能探測本機。
2. **只檢查 X 獨有歷史、不先合回本機**：正式 X 若領先兩邊 `localX`，必須檢查 X-only **每個 commit** 都是 `GOVERNANCE_DIRECT_X` 白名單內的非本體。任何產品、未知、混合、歷史驗證失敗，`X_AHEAD_NON_GOVERNANCE_BLOCKED`；不得假設 X 超前必然只有文檔。此時**禁止先 pull／merge／rebase X 到 localX**。
3. **由 localX 發布正式 X**：當次使用者 `/推推`、GitHub owner 的 exact PR/head/base SHA、必要 CI 綠燈與無合併衝突都通過時，從 GitHub `localX` PR **merge 進 X**；不得強推，也不能捨棄 X 既有的非本體變更。若 X PR base 變動，重驗授權與 CI，不沿用舊證據。
4. **發布完成後才回同步**：預設取得 X 合併後新 SHA，在本機 `localX` 安全執行 fetch＋`merge --ff-only`，必要驗證後由本機非強制推 GitHub `localX`。**當次 GitHub-only** 僅在 X 是遠端 `localX` 後繼、無分叉時，以預期舊 HEAD 非強制 fast-forward GitHub `localX` 至 X；本機留待另行安全同步。
5. **回讀分流**：實際驗證三方 SHA 完全相等才回報 `PUBLISHED_AND_SYNCED`；當次 GitHub-only 成功發布且 GitHub X／`localX` 相同，僅回報 `GITHUB_ONLY_PUBLISHED + LOCAL_SYNC_PENDING`，本機 HEAD 未查為 UNKNOWN；衝突、拒絕或遠端新提交須如實回報，不 reset／force／覆蓋未發布資料。
6. **非本體獨立**：治理、技能、純非本體文件直接治理 PR → X，**不經 localX、不使用 /推推**；不能因為由 `/派工`／`/接手` 執行就錯誤改走產品通道。

## `GITHUB_ONLY_PUBLISH_EXPLICIT_SCOPE_V1`（當次限定）

使用者須當次明確指示 GitHub-only 正式發布、允許包含的 `localX` 產品範圍與本機同步待辦。先確認來源 `localX` 已完成遠端整合、fresh head/base/PR、正式 X-only 治理歷史、精確 GitHub owner `/推推` 留言、所有必要 CI SUCCESS 及無衝突；新增產品提交或 SHA 變更須重新核對實際範圍並取得當次涵蓋新版本的授權，不能沿用過期核准。發布後只准非強制 fast-forward GitHub `localX` 回 X；本機標 UNKNOWN／`LOCAL_SYNC_PENDING`，不得接觸 DC／RC／本機，也不得宣稱 `PUBLISHED_AND_SYNCED`。

沒有此明確授權，一般 `/推推` 繼續遵守上方本機優先整合順序。
