---
name: root-local-first
description: WHD 本地施工與 localX 先行整合，無額外入口閘門。
whd_doc_role: CURRENT
whd_contract: root-local-first-workflow
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# root-local-first

此 Skill 僅適用於**使用者當次明確 `/接手` 選用 RC** 的施工路線；來源必須是最新 GitHub `localX`，Remote Desktop Commander → CoreELEC `whd-dev:/workspace/whd` 只是明確選擇的 executor 工作副本，不是 canonical 基準。一般任務／`/派工` 的 BUILD／TEST／COMMIT、CI GREEN 後 PR merge `localX` 都預設 GitHub／雲端，不以 RC 為必要整合前置；DC 權限需當次操作與平台核准。不得退回已退役外部儲存根目錄／`.unpushed` 當工作根目錄。

Registry 選路僅在明確 `/接手` 或直接查改本 Skill 時提示此路線；不得用任意 `changed_file`、通用 Bug 修復、治理任務或 `/派工` 自動載入 `root-local-first` 作為本機權限來源。明確否定的「不要 `/接手`，改用 `/派工`」是禁止接手，既有命令／Registry 路由必須只保留肯定的 `/派工`。Registry 的路由提示本身也不等於使用者 DC 授權。

## DC 呼叫前的強制判斷

本 Skill 遵循 `AGENTS.md` 的 `DC_DEFAULT_DENY_EXPLICIT_SCOPE_GATE`：只有使用者當次明確 `/接手` 選用 RC，或另行明確指定 DC 用途、裝置／路徑／操作且平台准許才能使用。`/派工`、一般 BUG 修復 CI GREEN／`LOCALX_INTEGRATION` 和治理任務均不構成 RC／DC 授權；`/推推` 本身只授權 GitHub-only 正式發布，不代表 Windows 人工 UAT 已執行，更不授權 CoreELEC 施工。其他情境預設 `DC_ACCESS_DENIED_BY_DEFAULT`，連 `list_devices`／`ping` 都不得探測，受阻時不能繞過。

公開交付按 `AGENTS.md` 的 `ISSUE_SCOPE_AUTHORIZATION_REUSE`：同一已核准 Issue、工作分支、`localX` 及施工範圍內的修正 commit 不因 SHA 改變重問；新 SHA 的 diff／CI 仍須核實，不可繞過平台安全審查或擴權至正式 X。

本 Skill 不得新增啟動授權檢查、claim、lease、工作槽、紀錄或協調交易；程式測試和 Git diff 才是修改成果證據.

產品與治理修改一律從最新 GitHub `localX` 開工，必要 CI GREEN 後 PR 合回遠端 `localX`；正式 `X=cleanup/2d-3d-sync` 只在使用者當次 `/推推`（即驗收與發布決定）、精確 SHA／owner comment 與受信任 X gate 通過後發布，**Windows 本機同步與人工 UAT 不是發布前置**，未執行不得冒稱已驗。`main` 為歷史分支，未經當次明確允許不可存取 RC／DC。

合併後測試採 `AGENTS.md::MERGE_TEST_REUSE_HARD_GATE`：使用 `tools/change_test_profile.py --merge-test-reuse` read-only 比對 exact tested 與整合 Git tree；完全一致且必要測試有有效 GREEN 收據，直接沿用測試，不重跑 GUI；有差異只針對受影響範圍補測，無法定界才全面回歸。
