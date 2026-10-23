---
name: 推推
description: WHD 產品與治理先整合 GitHub localX，當次 /推推 即為驗收與 GitHub-only 正式發布授權；Windows 同步獨立待辦。
whd_doc_role: CURRENT
whd_contract: localx-explicit-publish
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# /推推 — 以 GitHub localX 為來源的正式發布

**唯一預設路線：GitHub-only。** 使用者當次發出 `/推推`，即表示對當下 GitHub `localX` 發布候選版本的驗收決定和正式 X 發布授權。不得另要求「GitHub-only」、`/驗收通過`、Windows 本機 SHA／UAT、CoreELEC 或 DC 授權。Windows 同步／實測是獨立待辦，沒做不得謊稱已完成，但**不阻擋遠端發布**。

1. **來源與範圍**：fresh-read GitHub `localX` HEAD、正式 `X=cleanup/2d-3d-sync` HEAD、已整合 PR、實際差異與必要測試。日常產品、治理／技能先分別經適用 CI 和 PR 整合 GitHub `localX`；不從 `main` 或本機工作目錄默認取版本。
2. **X-only 歷史**：只讀確認正式 X 獨有的每個 commit（含 merge 第一父差異）是否全部符合受信任治理白名單；產品／未知／混合或證據不完整 → `X_AHEAD_NON_GOVERNANCE_BLOCKED`，不能先將 X 倒灌 `localX`，也不能 force/reset。
3. **建立與驗證 X PR**：source 必須為 GitHub `localX`、target 必須為 X。記錄 exact head/base SHA 與 scope，附 GitHub repo owner 對該 PR/head/base 的 `/推推` 精確留言，取得正式 X 受信任 Change Lane、產品（如適用）、治理等必要 CI GREEN 及無衝突。HEAD／範圍漂移必須重新檢查，不能借用過期 GREEN 或舊 SHA 留言。
4. **正式發布與遠端回同步**：核對閘門後 PR merge `localX → X`，回讀正式 X merge SHA；GitHub `localX` 是 X 祖先時，才用 `expected_sha`、非強制 fast-forward 更新遠端 `localX` 至 X。不得變動 `main`，不得碰本機或暗中使用 DC。
5. **最後一步是正式 GitHub Release**：依 `LOCALX_PUBLISH_OFFICIAL_RELEASE_V1` 檢查兩邊 GitHub HEAD 同為正式 X merge SHA、Git tag 指向它、GitHub Release 為公開且非 draft／prerelease，回讀 Release URL，才能稱 `OFFICIAL_RELEASED`。如果只有 PR merged，必須報 `OFFICIAL_RELEASE_PENDING`／真正原因，不能假稱完成。
6. **狀態分離**：GitHub 遠端完成可回報 `OFFICIAL_RELEASED + LOCAL_SYNC_PENDING`；本機 HEAD 未讀一律 UNKNOWN。要同步本機未提交變更，需使用者**另行**指定設備／範圍，依原 DC 安全閘門辦理；`/推推` 本身不含本機存取授權。

## 保留的退役流程識別（非現行指令）

`LOCALX_PUBLISH_THEN_X_BACKSYNC` 的「先查本機／本機優先」、`GITHUB_ONLY_PUBLISH_EXPLICIT_SCOPE_V1` 的「必須額外索取 GitHub-only 口令」、以及 Windows UAT 前置，均只供查閱舊紀錄，**不再具有執行權威**。現行正式授權與 fail-closed 條件由 `AGENTS.md` 最新 /推推 段落、`tools/localx_publish_gate.py`、受信任 X 的 `tools/change_lane_gate.py` 和正式 Release workflow 共同約束。

純治理、技能及流程文件同樣先 `localX`、後使用者當次 `/推推` 才能發布 X。unknown/mixed 適用產品通道，不得以「文檔」標籤放寬驗收；`/推推 文檔`、`/推推 主體` 只是相容指令，不擴權。
