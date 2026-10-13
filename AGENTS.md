---
whd_doc_role: CURRENT
whd_contract: agent-startup-process
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 開發與本地整合規則

- **預設 `main` 歷史隔離（`MAIN_HISTORICAL_UNMANAGED_EXPLICIT_X_ONLY`）**：`main` 保持原狀，視為非現行歷史分支；**不清理、不縮成 tombstone、不自動合併、鏡像、同步或刪除**。正式執行／治理唯一權威是 `X=cleanup/2d-3d-sync`。凡 GitHub／Agent／Skill／CI 查詢現行 WHD 規則，必須明確指定 `ref=cleanup/2d-3d-sync`；未指定 ref、工具默認落到 `main` 或無法確定所讀 HEAD 時，禁止把結果當 CURRENT，須重新以 X ref 讀取或 fail closed。舊 `WHD_DEFAULT_BRANCH_FAIL_CLOSED_V1` 的 `MAIN_MINIMAL_TOMBSTONE_TREE` 要求已退役，不得再次啟動 `main` 清理；使用者另有當次明確指令才可另行規劃 `main` 變更。
- **舊工單交易、工作槽與 lease 控制系統已退役**；不得要求其憑證、工作槽、Preflight receipt 或其他管控才能執行修改、測試、Git commit。
- **入口及階段分流**：`/派工` 的**施工、修改、測試、commit、PR 與 CI** 只能在 GitHub／排程／雲端執行器完成，嚴禁使用使用者本機。**唯一例外是 exact SHA CI 已通過後的 `LOCALX_INTEGRATION` 最終階段**：此時 `/派工` 可經 Desktop Commander（DC）連線 CoreELEC `whd-dev:/workspace/whd`，**只做使用者本機 `localX` 合併／必要整合驗證／同步回讀**，不得在該階段暗改產品程式或重做雲端施工。`/接手` 仍須使用者明確指令，才可在 RC 進行整個施工流程。
- **產品施工通道**：`/派工` 遠端施工提交後建立 GitHub `localX` 目標 PR，確認 exact HEAD 的 CI SUCCESS；**先透過 DC 在本機 `localX` 整合且保留本機未發布修改**，通過整合驗證後以非強制方式同步 GitHub `localX` 並讀回兩端 SHA／PR 狀態。若 **DC 實際無法連線**，才允許走斷線備援並註明 `DC_UNREACHABLE`、`LOCALX_SYNC_PENDING`；使用者對本工單另有明確 GitHub-only 整合授權時，改依 `GITHUB_ONLY_LOCALX_EXPLICIT_SCOPE_V1` 直接整合遠端 `localX` 並留下本機待同步，不得假稱 DC 已斷線。**DC 正常整合路線**只有實際完成本機安全合併、必要整合驗證、非強制遠端同步並回讀兩端 SHA 後，才能回報 `LOCALX_SYNCED`；**GitHub-only 明確授權／DC 真正斷線備援**才回報 `LOCALX_SYNC_PENDING`。不能把成功的本機整合也報成待同步。DC 可連但本機有衝突、髒檔、權限拒絕、CI RED，**不可冒用斷線備援**。`/接手` 依其明確指令走 RC 全流程。正式 X 的產品發布仍必須當次 `/推推`。
- **治理直送通道（正式硬閘門 `NON_PRODUCT_GOVERNANCE_DIRECT_X`）**：僅限 `tools/change_lane_gate.py` 明確白名單內的非產品文件、治理規則、技能、GitHub 工作流程與其專用測試。此類修改**不必**走 localX、`/推推`、工單派工或產品 QA；**優先直接使用 GitHub／雲端治理分支** `governance/*`、`docs/*` 或 `skills/*`，從最新 X 修改、檢查、PR 至 X 並合併。**未取得使用者本次對 DC／本機的明確授權，不得為治理修改存取 CoreELEC、whd-dev 或本地 shell**；雲端能力不足時回報阻塞，不得自動轉走 DC。
- **非本體 CI 排程／驗收權威硬分流（`CI_SCHEDULING_ONLY_V1`）**：純 CI 排程數字、既有 Runner 選型可依 `tools/change_lane_gate.py` 的**受信任 base X → PR HEAD 實際 blob 差異**走治理直送，不需本機 `localX`／DC／完整產品回歸。產品驗收主 workflow `.github/workflows/whd-product-regression.yml` **不得僅憑副檔名或 `.github/workflows/` 目錄判定治理**：只有對既有行的 `runs-on`、`timeout-minutes`、`max-parallel`、`retention-days` 且舊值、新值均符合白名單的替換能例外直送。增刪行、修改觸發 paths、matrix shards、jobs/if、測試指令、必跑步驟、CI 名稱、artifact 集合、完整性檢查一律產品通道；`tools/product_ci_regression.py`、`tools/product_ci_green_reuse.py`、`tools/whd_v15_acceptance_evidence.py`、產品測試清單／驗收矩陣與相關測試，永遠不能只靠 CI 調度名義豁免產品回歸與 `/推推`。GitHub X 的 required `WHD Change Lane Gate` 必須由**受信任 X 版本**執行這項判定。未知／缺少 git diff 證據 fail closed，不得自行改走本機。
- **混合／未知檔案一律回產品通道**：只要包含一個非白名單路徑，即不得走治理直送；檔案改名必須同時分類舊、新路徑，空 diff、跨 repo、來源分支不符都 fail closed。正式判斷由 `.github/workflows/whd-change-lane-hard-gate.yml` 與 `tools/change_lane_gate.py` 執行。
- GitHub 正式硬閘門必須在 X 的 Ruleset 把 `WHD Change Lane Gate` 設為 required status check，否則只能算 CI 檢查、不能宣稱平台端不可繞過；直接 push X 應由分支 Ruleset 禁止。
- 禁止遺失使用者本地未發布修改，禁止用 X 覆蓋 localX。保留程式碼 review、製造幾何與產品回歸檢查；無需工單交易硬閘門。
- 本地工作不需 Google Drive 工作根目錄，也不需調用舊協調分支。
- **兩入口共享交付範圍、不共享施工權限**：已確定 Issue 的 `/派工`、`/接手` 均限定 repo=`looaeedr/whd`、工作分支、PR base=`localX`、exact CI 和回讀。`/派工` 對 DC 的許可**僅限最終 `LOCALX_INTEGRATION`，不代表取得本機施工授權**；`/接手` 才允許使用者 RC 工作區完成施工。無需退役 remote token／unlock；**平台公開上傳安全審查仍有效**，不能繞過。沒有 `/推推` 不得發布正式 X。

## WHD 長對話上下文損耗防護 `WHD_CONTEXT_LOSS_PREVENTION_V1`

**目的：降低本體因對話過長、重複工具輸出或系統壓縮而遺失已決定事項的機率。這不是交接流程。** 平台不提供可直接讀取的「剩餘 Token 百分比」或下一次自動壓縮時點，無法保證不被截斷，也不能主動清除既有上下文；禁止捏造容量、倒數或「已開啟背景監控」。

1. **先控制上下文占用**：GitHub/API/長日誌優先取得指定檔案行範圍、diff／變更路徑、run/job/step 摘要與失敗切片；只要結果足夠作判斷，就不回傳整份 `AGENTS.md`、全量 commit 列表、重複長 Log 或同一份已讀文件。工具回傳過長時，在工具結果處先萃取必要欄位，固定有限上限（一般 log tail 不超過 80 行），完整證據留來源平台，不灌滿對話。
2. **只維護當輪精簡工作事實**：在當次執行中以最小工作狀態辨識 `Issue/PR`、`branch/HEAD`、已確認的使用者決策、剛完成的操作、精確下一步；僅實際變動時更新，不把整套規格或工具輸出重新敘述一次。這是當前作業的上下文節流，**不建立新交接文件、工單、排程、定時檢查或跨對話記憶承諾**。
3. **從可觀察異常防止錯做**：工具結果 `truncated`、既有摘要取代原文、發現不一致 SHA／PR、無法確定使用者已決定的條件時，標示「上下文資訊需核對」，只針對缺少的事實重讀 GitHub 正式 `X=cleanup/2d-3d-sync` 或原 Issue/PR／此對話決策，不猜、不重新問已提供的答案，也不全面重新 Discovery。若原決策無法核實，清楚標未核實，尤其不能據此做不可逆合併／發布。
4. **已在執行時不中斷**：風險提示不等於停止施工。CI／工單狀態沿用現有 exact `HEAD`／`run_id` 與已取得的結果；只補讀缺口，不因對話濃縮而重新觸發測試、重做工單接取或要求使用者再輸入「繼續」。重大合併前回讀現況，不把過期摘要當權威。
5. **誠實提示但不假裝預知**：只有觀察到內容截斷、資訊矛盾或真實銜接困難才簡短提醒，並說明正在核對的具體項目；`/上下文` 可以要求現在的可觀察風險評估，但不是原生容量計量器。不得把「對話很長」推論成某個剩餘百分比或自動提醒已啟動。

本規則僅改善本體處理資訊的方式，不擴充 DC／本機權限，不新增 GitHub 施工前置硬閘門；非本體治理修訂依 `NON_PRODUCT_GOVERNANCE_DIRECT_X` 直接走治理 PR 至正式 X。

## `/推推` 發布先行、X 回同步硬閘門 `LOCALX_PUBLISH_THEN_X_BACKSYNC`

- **預設本機優先，GitHub-only 須當次明確授權**：一般 `/推推` 先查本機 `localX`、GitHub `localX`、正式 X 的 fresh SHA／未發布修改，將本機驗證版本以非強制方式同步 GitHub `localX`，讀回一致後再發布；遠端超前或分叉須安全整合，不 reset、不強推。**只有使用者當次明確指定 `GitHub-only` 發布、範圍包含現有遠端 `localX` 內容且接受「本機同步待辦」時**，才允許不讀／不改本機，直接以已完成遠端 `localX` 整合及 exact HEAD 為來源建立 X PR；本機 HEAD 只能標 UNKNOWN／`LOCAL_SYNC_PENDING`，不可虛稱三方已對齊。一般「/推推」「繼續」不得冒充 GitHub-only 授權。
- **X 超前只能是非本體**：發布前只**檢查** X 相對於 `localX` 獨有的所有 commit（含 merge commit 第一父提交的差異），並以 `tools/change_lane_gate.py` 的治理白名單逐一核對。任何本體／混合／未知路徑、無法證實的歷史均 `X_AHEAD_NON_GOVERNANCE_BLOCKED`，不得假設「一定只有文件」。通過時也**不得在正式發布前**先把 X pull／merge／rebase 進本機或 GitHub `localX`。
- **X-only 歷史時區 CI 相容例外（只讀）**：僅兩個已在 X 合併且驗收的不可變提交 `06d97ca575ebf9c2973ab3fdaa669787702faac4`、`beac45c3b3afc5bb11629fcbcd6e1e51b76c8e09`（新增 `Asia/Taipei` 環境與來源時間安全檢查）可在 X-only 歷史回讀時視為治理；還須確認其除既定 CI workflow 外的差異全屬治理白名單。**不授權任何新 PR、其他 workflow 變更或任意 SHA 豁免**；產品發布與當次 `/推推` 仍照原硬閘門。
- **先發布，再回同步**：使用者當次 `/推推`、exact PR head/base SHA、GitHub owner comment、必要 CI、X-only 治理歷史與無衝突都符合後，由 GitHub `localX` PR **合併至 X**（不 force、不覆蓋）。預設發布後先從 X fast-forward 同步**本機 `localX`**，必要驗證後非強制同步 GitHub `localX`；**當次明確 GitHub-only** 則僅可在 GitHub `localX` 為發布後 X 的祖先時，以 `expected_sha` 限定、非強制 fast-forward 遠端 `localX` 至 X，留下本機 `LOCAL_SYNC_PENDING`，不探測 DC／RC／本機。
- **三方回讀與狀態分流**：只有實際確認 `HEAD(本機 localX) == HEAD(GitHub localX) == HEAD(X)` 且 PR merged 才能回報 `PUBLISHED_AND_SYNCED`。當次明確 GitHub-only 發布，若 X PR merged 且遠端 `localX` 已非強制對齊，**只能**回報 `GITHUB_ONLY_PUBLISHED + LOCAL_SYNC_PENDING`，本機 SHA 未查為 UNKNOWN；不可宣稱三方同步。若 DC 不可用、認證拒絕、衝突或 GitHub 更新導致任一步失敗，回報 `POST_PUBLISH_LOCALX_SYNC_PENDING`、已知 SHA／真正原因；不重複索取 `/推推`，不得 force 或覆蓋未發布資料。
- **通道不變**：純治理／技能／非本體文件直接治理分支 PR 合併 X，不經兩邊 `localX`，也不需要 `/推推`；以上三方回同步僅適用於產品發布，不得反過來把治理變成本體。發布操作遵守既有平台安全審查與 DC 授權範圍。

## 當次明確 GitHub-only 產品發布例外 `GITHUB_ONLY_PUBLISH_EXPLICIT_SCOPE_V1`

此例外**僅改變指定當次產品發布的整合位置與同步回報，不是另一條無授權發布捷徑**：使用者須明確指向 GitHub-only 的 `localX → X` 發布、包含的新產品功能／範圍、以及本機同步待辦。先確認遠端 `localX` 已整合相應產品 PR、當下 head/base SHA、必跑 CI（含正式 X PR 自身）、GitHub owner exact `/推推` 留言及 X-only 治理歷史；任一 HEAD 或產品範圍中途變更，必須按新版本重新驗證與取得覆蓋新範圍的當次明確授權，不能沿用舊 SHA 紀錄。

發布後僅在確定 fast-forward 時更新**遠端** `localX`；本機標 `LOCAL_SYNC_PENDING` 並留待使用者另行授權的安全同步，不使用 DC、RC、本機 shell，不 reset／強推。**未取得 GitHub-only 明確授權時，`LOCALX_PUBLISH_THEN_X_BACKSYNC` 仍採本機優先。**

## 全域台灣時區硬閘門 `TAIWAN_TIMEZONE_HARD_GATE_V1`

- **唯一人類操作時區**：`Asia/Taipei`（UTC+08:00），涵蓋本專案的 Agent、ChatGPT 回報、工單／PR 留言、文件發布時間、測試摘要、排程與提醒、GUI 顯示、日誌檢視、交付檔名及相對日期（今天／明天／週末）的解讀；不得依執行機器、瀏覽器、GitHub Runner 的預設時區自行決定。
- **時間必須可辨識時區**：人類可讀的完整時間戳採 `YYYY-MM-DD HH:mm:ss +08:00` 或帶 `+08:00` 的 ISO 8601；僅顯示日期時須已先換算到台灣日期。不能輸出無標示時區的日期時間並冒充台灣時間；夏令時間不得套用至台灣。
- **CI 強制執行**：關鍵 GitHub Actions jobs 必須設 `TZ=Asia/Taipei`，`tools/change_lane_gate.py` 檢查明確的環境設定與 ZoneInfo offset；任一不符即 `TAIWAN_TIMEZONE_HARD_GATE_FAILED`。增修 Python 日期時間產生點時，不得加入無時區的 `datetime.now()`、`datetime.today()`、`datetime.utcnow()`、`datetime.astimezone()` 或使用執行機器本地時間的 `time.localtime()`。新改動由 CI diff guard 驗證；歷史既有日期來源需分批補上精確的產品回歸，不以文字規則冒稱已改好。
- **排程換算**：需求的日／週／幾點一律先用台灣時間解析；若 GitHub Actions cron 或第三方 API **僅接受 UTC**，則只在傳輸層轉換成等價 UTC（例如台灣 08:00 對應 UTC 00:00），顯示與排程權威仍為 `Asia/Taipei`；不得因 runner 預設 UTC 造成日期跨日錯誤。
- **外部格式例外不等於使用 UTC 操作**：GitHub 事件 ISO UTC、Unix epoch、Git commit 與 API 明定 UTC 的儲存／簽名／傳輸欄位保留原格式，不擅自改寫證據；在回報、呈現或作本地日界判斷前必須換算台灣時間。保證同一瞬間不因格式轉換而改變。
- **禁止藉時區門檻擴權**：不修改舊工單交易規則、既有排程啟停、產品幾何與 DC 權限；此硬閘門的治理變更走既有 governance 直送 X 通道。`AGENTS.md` 與 `.agents/contracts/WHD_TAIPEI_TIMEZONE_HARD_GATE_V1.json` 為時間權威，後續 SOP／技能需從此契約繼承。

## 全域 DC 硬閘門 `DC_DEFAULT_DENY_EXPLICIT_SCOPE_GATE`

**預設禁止（DENY）**：所有 ChatGPT／Agent／排程／治理／文件／程式執行器，**在呼叫任何 Remote Desktop Commander（DC）工具之前**先做以下判斷。包含 `list_devices`、`ping`、`who_am_i`、檔案讀寫、工作目錄查詢、process／shell／Git 操作；**不得先連線探測再補問授權**。除以下五種情況外一律 `DC_ACCESS_DENIED_BY_DEFAULT`：

1. **當前使用者明確下達 `/接手`**：僅授權該次指定工單及 RC → `whd-dev:/workspace/whd` 的施工、測試和該工單交付。先前對話的 `/接手` 不得永久沿用；不能把一般「去修修」「繼續」「可以」、文件修改或推送 GitHub 的授權解讀為 `/接手`。
2. **`/派工` 的最後 `LOCALX_INTEGRATION` 階段**：必須先由真正雲端完成施工，確認對應工作 PR `base=localX`、exact HEAD SHA 的必要 CI 全部 SUCCESS、可整合，才准 DC **只做本機 `localX` 最終合併、必要整合驗證、同步與回讀**；此例外不允許本機 BUILD／TEST／COMMIT／修產品程式，不允許提早讀取 DC 裝置或測試連線。
3. **使用者當次下達 `/推推`**：視為產品 `localX → X` 的完整發布授權，內含為該次發布所需的 DC 本機 `localX` 查核、安全同步、發布後 X 回同步與三方 readback；無須另請一次「允許 DC」。此授權只涵蓋同一批已驗收產品成果的發布與同步，不得藉此施工、修改無關檔案、強推或略過 CI；若當次使用者明確指定 GitHub-only，則不觸碰 DC，並保留 `LOCAL_SYNC_PENDING`。
4. **一般對話已明確要求執行特定 BUG 修復，且進入該次 `LOCALX_INTEGRATION`**：依 `CONVERSATIONAL_BUGFIX_LOCALX_CONTINUITY_V1`，原授權只在同一 repo、已確認的 BUG 範圍與工作成果、exact HEAD 必要 CI 全部 SUCCESS、PR base=`localX`、且未明示禁止 DC／改用 GitHub-only 時，延續至本機 `localX` 安全合併、必要驗證、非強制同步與回讀；不得再要求一次「允許 DC」。純討論 BUG、尚未要求施工、未知範圍、未完成測試或提前進入本機施工均不適用。
5. **使用者對本次特定目的明確指示允許 DC**：必須能辨識當次授權的工作、裝置、操作／路徑範圍；不能將概括的修正命令、先前授權或某個 Skill 裡的建議當作當次 DC 許可。

**其餘所有情境（含治理文件直合 X、GitHub 能力不足、排程卡關、只想看看本機狀態、清理先前事故殘留）一律不用 DC。** 若確實需要，先向使用者說明 **使用 DC 的必要原因、預計使用的裝置／路徑、要讀／改／執行的操作與影響**，標記 `DC_AUTHORIZATION_REQUIRED`，**停止任何 DC 呼叫並等待使用者明確核准**；未核准不得改用其他本機通道繞行。核准僅在被核准的當次目的與範圍有效，不自動延伸到下一張工單或其他工作。

**失敗即封閉**：授權來源不明、`/派工` 所在階段不明、CI 非 exact SUCCESS、PR base 不確定、使用者撤回授權時都視為 DENY。此規則不改動平台工具 ACL；任何外部平台拒絕仍不得繞過。CI 回歸測試可約束倉庫規則不被改鬆，**但不得誤稱 GitHub CI 能直接攔截 ChatGPT 的 DC 工具呼叫**。

## 一般對話 BUG 修復授權延續 `CONVERSATIONAL_BUGFIX_LOCALX_CONTINUITY_V1`

- **已明確要求執行**的 BUG 修復（不必輸入斜線指令）授權同一任務的工作區施工、必要測試、提交、PR／CI，以及在 exact HEAD CI 成功後的 **本機 `localX` 最終整合**。不得把「這個 BUG 怎麼回事？」等純討論解釋成執行授權；對話裡的明確否定、GitHub-only 指示、範圍限制仍優先。
- 必須核對當次可信對話中的修復指令、repo、功能範圍、工作分支／PR 及 exact HEAD；實際 DC 呼叫只允許在 `LOCALX_INTEGRATION` 階段、安全保留本機未發布修改、必要合併檢查與非強制 GitHub `localX` 同步。不准藉此提早於本機 BUILD／TEST／COMMIT、修改無關檔案或走到正式 X。原範圍沒變就不重問 DC 授權。
- machine decision：`tools/localx_publish_gate.py::require_conversational_bugfix_localx_integration`。輸入必須來自執行者**已驗證真實來源**的對話授權與 GitHub CI／PR readback；caller 提供的文字／JSON 不能自行證明對話真實性，GitHub CI 更不能代替 ChatGPT 驗證對話。來源不明、CI 不是 exact SUCCESS、scope drift、拒絕本機或 DC 不可用時 fail closed，記錄實際 blocker；不得以重複授權問題假裝為 blocker 或偷走 GitHub-only。

## 合併後測試證據沿用硬閘門 `MERGE_TEST_REUSE_HARD_GATE`

- 工作區與 exact HEAD 必要測試／CI 通過後，**合併不是自動重跑 GUI／完整回歸的理由**。先回讀 trusted test receipt 和合併後實際 Git tree；`tools/change_test_profile.py::evaluate_merge_test_reuse` 對已測試 commit 與整合 commit 做 read-only tree 比對。tested tree 與 integrated tree 完全相同（即使 commit SHA 不同）且所需測試完整通過 → `REUSE_VERIFIED`，直接保留 GREEN 並執行 Git SHA／merge/readback，不得重啟已完成的 GUI 測試。
- 兩個 tree 不同 → 先列出 `git diff` 實際異動路徑、衝突與依賴影響，僅補跑未被原證據覆蓋的目標 GUI／模組／整合測試；影響不可界定才跑完整回歸。缺少可核驗測試收據、測試未完成、CI 非 SUCCESS 或 Git tree 無法回讀 → `EVIDENCE_INCOMPLETE`，**不得冒稱免測通過**。
- 已在執行的本機測試應先核對是否真屬重複且可安全停止；不得為求速度殺掉未知程序、取消必要測試或破壞本機檔案。安全同步 GitHub `localX` 與正式 `/推推` 權限邊界均不變。此決策器**不代替** GitHub CI 簽章及真實外部驗收，執行者須從可信來源驗證輸入後才能採信。

## /派工跨工單自動收尾 `DISPATCH_DEFAULT_LOCALX_CONTINUATION_V1`

**既有 `/派工` 授權涵蓋同一 Issue／PR 的正常 `localX` 最終整合，不存在每張單另下合併口令的前置。** 對每張已合法接取的產品工單，PR base=`localX`、exact HEAD CI 全綠及範圍／mergeability 核對成功後，執行者必須繼續預設 `DC_LOCALX_FIRST`：在 `LOCALX_INTEGRATION` 合法階段經 DC 僅檢查及安全合併本機 `localX`、必要整合驗證、非強制同步 GitHub `localX`、兩端 readback；不能以 `LOCALX_INTEGRATION_PENDING` 當成已結案，更不能反覆要求「GitHub-only 合併 PR #...」取代預設路線。同一工單重新產生 HEAD 只重驗 exact CI／修改範圍，不重索既有 localX 整合授權。

只有**該 Issue／PR 的使用者明確指定**不碰 DC、且授權 GitHub-only 遠端 `localX` 合併，才改走 `GITHUB_ONLY_LOCALX_EXPLICIT_SCOPE_V1`；只有真實 DC 連線故障且有證據才能走 `DC_UNREACHABLE_FALLBACK`。**兩種例外均不代表本機已整合**。若 DC 合法階段缺工具或連線被拒，須留下可核對的 blocker／SHA／續接動作，不得捏造失聯、不擅自遠端代合。這是當次執行者的連續交付義務，不是 GitHub Actions／文件自身具備跨回合喚醒或操作 DC 的能力；也不改動正式 X 產品發布仍需 `/推推` 的界線。

## 工單範圍授權延續 `ISSUE_SCOPE_AUTHORIZATION_REUSE`

- **授權以施工範圍為主、SHA 供版本驗證**：使用者已明確核准指定 Issue 的公開交付時，範圍包含 `repo=looaeedr/whd`、指定 Issue、原工作分支、允許修改的功能／檔案範圍、PR 目標 `localX` 與 push／PR／CI／同工單修復／重測／整合 `localX`。執行者須能回讀原授權對話或可驗證的核准證據，不可捏造、不可用另一張 Issue 的核准冒充。**若使用者明示僅限某固定 commit SHA，仍以該較窄的授權為準。**
- **同一工單同一範圍的修復續作**：CI 失敗、必要測試修復而產生新 commit SHA，原授權仍有效，**不因 SHA 更新就要求重複核准公開上傳**。但每個新 SHA 的 diff 都要重新核對原範圍、以新 exact HEAD 重跑必要測試／CI，不能繼承舊 SHA 的 GREEN；於 PR／Issue 留存版本變更證據。
- **跨越原範圍須新授權**：跨 Issue（#1466 的許可不等於 #1467）、repo、工作分支、PR 目標，或新增無關功能、使用者明示排除的檔案；不得用「小修正」包裝擴權。**正式產品 `localX → cleanup/2d-3d-sync` 仍只依當次 `/推推` 與 `tools/localx_publish_gate.py` 的 exact PR／SHA 驗證**，本規則不得放寬。
- **外部平台安全審查不受此規則改寫**：GitHub／RC／自動核准系統若實際拒絕公開 push／merge，保留既有提交，明確回報被拒工具、操作、缺少哪類證據與 `PUBLIC_UPLOAD_REVIEW_BLOCKED`。不得以切換工具或傳輸管道繞過；已具有有效範圍核准時，也不得只是對使用者重播同一句核准問題而不解決證據傳遞。
- 此條不恢復舊 Flow v2／lease／工作槽等交易控制，也不能把聊天文字聲稱為已通過平台審查。

## /派工本體優先施工 `DISPATCH_SELF_EXECUTION_FIRST`

- **本體直接施工優先。** 只要當次已有合法 GitHub 讀寫、建立 commit／PR 的能力與可觸發的雲端 CI，當前 AI 本體就應沿用指定 Issue、既有 PR 與工作分支直接執行實質修改、補測試、提交和 CI；**不得先搜尋 Codex、雲端程式代理外掛或子代理**，也不得因缺少另一位 executor 而停工。GitHub 工具可施工不代表本體能自行在雲端執行 shell；可由 GitHub Actions 執行可用測試，不得假稱本體已在 GitHub Runner 上測過。
- **兩種接取證據分開。** 本體施工時記錄身分 `本體直接接取`、`execution_location=GITHUB`、Issue／原工作分支／PR，以及第一筆真正的修改 commit SHA；有 CI 時再記錄 exact SHA 的 Actions run ID／測試結果。不要求不存在的外部 task ID。**只有文字留言、空提交或搜尋外掛不是施工成功**。外部代理施工才需要對方的實際啟動回執／接取證據。
- **能力不足才找外援。** 先具體指出缺少哪些 GitHub 寫入、提交、合法雲端驗證／CI 等能力，確實無法由本體施工才尋找或啟動外部代理；僅搜尋外掛不算派工。無可行途徑時正確標 `DISPATCH_REGISTERED_ONLY`／`REMOTE_EXECUTOR_UNAVAILABLE`，不可假稱已接取或背景運作。
- **原權限不變。** `/派工` 的 BUILD／TEST／COMMIT 不得改用使用者本機、RC 或 DC；必要 exact SHA CI、`LOCALX_INTEGRATION` 與產品正式發布 `/推推` 均不豁免。本條只改執行者優先順序；**修改治理文件／技能本身仍依治理直送 X，不走產品派工或 localX。**

## /派工真實啟動證據 `DISPATCH_EXECUTOR_HANDOFF_REQUIRED`

- **/派工不是只登記 Issue/PR。** 先依 `DISPATCH_SELF_EXECUTION_FIRST` 由本體使用現有 GitHub／雲端 CI 能力直接施工；只有本體缺少實際能力才尋找、啟動外部雲端代理。Issue、PR、留言、指派欄位、未對應實質施工的 CI run、外掛搜尋都不是開工證據，不能宣稱已派工或執行中。
- **成功證據必須回讀：** `EXECUTOR_START_CONFIRMED` 必須有可核對的 Issue、原工作分支、執行者身分與真實施工動作。**本體施工**以實質 commit SHA、PR、exact GitHub Actions run／測試結果為憑，不要求外部 task ID；**委派外部代理**才需真實啟動回執／task ID 及代理接取。單純留言或宣稱已接取不算施工，不得冒稱另有 Agent。
- **失敗必須真實結束：** 只有登記成功時標 `DISPATCH_REGISTERED_ONLY`；無法調用實際雲端施工入口時標 `REMOTE_EXECUTOR_UNAVAILABLE`；呼叫遭拒／未得到接取證據時標 `DISPATCH_START_UNCONFIRMED`，列明拒絕或未證實之處、最後可驗證狀態與續作入口，不得稱派工完成、不得假裝背景有人施工。**不要再創第二張 Issue／PR 來掩飾失敗。** 不得因此改走 DC、本機或未授權 `/接手`。
- **成功接取之後**仍須按現有 CI、`localX` 與 `/推推` 規則續作；這只是防止「登記即完成」的真實性檢查，**不建立舊式 lease／claim／Flow v2 或新的輪詢排程**。

## `/派工` 分階段位置硬閘門 `DISPATCH_CLOUD_BUILD_DC_LOCALX_ONLY`

- **施工階段**（`DISCOVERY / BUILD / TEST / COMMIT / PUSH / PR / CI`）：限 `execution_location=GITHUB|SCHEDULER|REMOTE_ACTION` 的真正雲端執行器（不得暗接使用者裝置）；`RC / DESKTOP_COMMANDER / LOCAL_SHELL / /workspace/whd / Z:\\新WHD` 一律 `DISPATCH_LOCAL_EXECUTION_DENIED`。
- **最終整合階段**（`LOCALX_INTEGRATION`）：PR HEAD exact CI SUCCESS 且 scope／工作分支驗證通過後，**才**允許一次 DC 連線，將已測試的 commit 整合到**本機** `localX`，確認 `localX` 現況並保留任何本機未發布改動；整合必須非強制、不得 reset／覆蓋、不得藉本機修改程式取代遠端施工。完成本機整合後才同步 GitHub `localX` 並回讀兩端；PR 自動關閉或 GitHub 狀態異常時必須實際回讀，不虛構 merge。
- **DC 斷線備援（非使用者明確授權 GitHub-only）**：記錄實際連線失敗／逾時、當時 PR/HEAD/CI 證據後，才可合併 GitHub 遠端 `localX`；標記 `DC_UNREACHABLE + LOCALX_SYNC_PENDING`，安排後續本機對齊而非冒稱本機已整合。DC 可連線但 merge 衝突、工作樹 dirty、認證被拒或測試失敗時**不能**改走斷線備援。
- 沒有雲端施工能力回報 `REMOTE_EXECUTOR_UNAVAILABLE`，不能用 DC 做施工；`/派工` 不會因此隱性轉成 `/接手`。任何平台公開上傳／遠端工具拒絕仍需遵守，不得換 transport 偷渡。

## 使用者明確授權 GitHub-only 整合 `GITHUB_ONLY_LOCALX_EXPLICIT_SCOPE_V1`

- **獨立於 DC 斷線備援**：當使用者針對本次指定 Issue／PR **明確要求不用 DC／不接觸本機，且已授權將成果整合至 GitHub 遠端 `localX`** 時，允許在 exact HEAD CI 全綠、PR base=`localX`、無衝突、合併權限與施工範圍符合後，直接用 GitHub PR merge 整合遠端 `localX`。不必先探測 DC，也**不得**假記 `DC_UNREACHABLE`。單純執行者自寫 PR 說明「無 DC」、只有 CI GREEN 或只允許寫程式，均**不構成使用者遠端合併授權**。
- **回讀與權威分流**：合併前再次讀 PR/head_sha/base/current remote localX，使用 `expected_head_sha` 防競態；成功後回讀 PR merged、merge_commit_sha 與 GitHub `localX` HEAD，標記 `GITHUB_ONLY_LOCALX_MERGED + LOCALX_SYNC_PENDING`。**本機 `localX` SHA 未經合法連線實際讀取前一律 UNKNOWN**，不虛構本機已整合；不 force、不 reset、不覆蓋本機未發布改動。
- **完成與續作**：GitHub-only 遠端合併後可依既有規則續行 Issue 留言／結案回讀及 `NEXT_ISSUE_DISCOVERY_REQUIRED`；本機同步仍列待辦，不能標 `LOCALX_SYNCED` 或宣稱三方一致。若沒有同工單明確 GitHub-only 整合授權，必須保留 `LOCALX_INTEGRATION_PENDING` 並回報缺少何種核准，**不得偷走 DC 斷線備援**。
- **正式 X 邊界不變**：產品 `localX → X` 必須使用者當次 `/推推`；這項例外不准提前碰使用者本機／DC、不允許跳過必要 CI、不擴張其他工單的公開推送或合併權限。非產品治理依 `NON_PRODUCT_GOVERNANCE_DIRECT_X` 直送 X。

## /派工退出前查核 `DISPATCH_TURN_EXIT_GATE_V1`

**執行者必須先判斷下一個合法動作，才可正常結束當前施工回合。** 狀態表權威為 `.agents/contracts/WHD_DISPATCH_TURN_EXIT_GATE_V1.json`；它是治理契約，不是平台層級的 ChatGPT 回合攔截器。只有本體當輪具備實際工具能力才能執行續作；此契約**不會在回合結束後自行喚醒模型或啟動背景輪詢**。

- **先對準 exact HEAD**：讀取當下 PR `base=localX`、`head_sha` 與同一 SHA 的 Canonical Product Regression `run_id/status/conclusion`、jobs。缺 run、查到舊 SHA／矛盾資料 → `RECONCILE_ONLY`，不得借用其他 HEAD 的 GREEN。
- **CI 非終態**（`requested/queued/waiting/pending/in_progress`）→ `CONTINUE_POLL`：在當次仍可呼叫工具時持續查詢 exact run，2–3 次操作回報一次實質進度，回報不是退出訊號；只讀結構化狀態與精簡失敗資料，不重抓長 Log、不要無限制高頻打 API。
- **CI 終態**：`success` → `LOCALX_INTEGRATION_PENDING`，按既有 DC 最終階段／合法斷線備援／明確 GitHub-only 授權例外進行合併回讀，不能停在「CI GREEN」；`failure/cancelled/timed_out/action_required` 或其他不成功 → `REPAIR_AND_RETEST`（如平台無權操作則報實際阻塞），不當作驗收完成。
- **CI 成功仍未完成交付**：本機／遠端 `localX` 整合回讀、Issue close/readback 及 `NEXT_ISSUE_DISCOVERY_REQUIRED` 等既有義務未處理 → `CONTINUE_FINALIZATION`；達到所有必要驗收與追蹤義務、讀回證據後才可標 `RELEASED`。正式 X 仍限使用者當次 `/推推`。
- **允許當回合非完成式退出的真實例外**：有可追溯 API 錯誤／權限拒絕／無合法執行途徑 → `BLOCKED_WITH_EVIDENCE`，或執行環境真實中斷／當回合工具資源限制 → `RUNTIME_LIMIT_UNRESOLVED`；回報當時 `Issue/PR/head_sha/run_id/last_observation/blocker/next_exact_action`，**不得標示 DONE、已完成、背景自動續作**，不得假造阻塞來取代仍可做的輪詢。
- **不擴權**：本規則只對現有 `/派工` 回合施加退出前的決策檢查；不啟動新排程／`workflow_run` 自動施工、不重建舊 Flow v2、不增設 GitHub 分支保護，不允許提早使用 DC／RC／本機，純治理文件照既有 `NON_PRODUCT_GOVERNANCE_DIRECT_X` 直送 X。

## /派工 產品交付不中斷閘門（執行者責任）

- `/派工` 不以「已建立 PR」「CI queued/in_progress/pending」作為交付完成。這些都是 **CONTINUE_POLL**，不能以「等 CI 完成」作最終答覆來退出當輪任務。
- 一旦已建立指向 `localX` 的產品 PR，就應在**當次可執行回合**追蹤 exact PR HEAD、base 與 Canonical Product Regression 的 GitHub Actions run；短間隔再次查詢。每 2–3 次操作回報實質進度，但**回報本身不是停止訊號**。
- exact HEAD 的 Product Regression `SUCCESS` 且 PR 可整合 → **合併至 localX（本機優先），進入 `LOCALX_INTEGRATION`，使用 DC 合併本機 `localX` → 必要本機整合驗證 → 非強制同步 GitHub `localX` → 兩端 SHA／PR 狀態回讀 → 工單留言 → close + readback**。除 DC 連線實際失敗的斷線備援外，使用者明確授權本工單 GitHub-only 整合時，亦可按 `GITHUB_ONLY_LOCALX_EXPLICIT_SCOPE_V1` 合併遠端 `localX` 並標記 `LOCALX_SYNC_PENDING`；兩者均不得冒稱本機同步，不需用戶重複喊「繼續」。
- **觸發點是本機 `localX` 真正合併成功並回讀、或已證實 DC 斷線而 GitHub `localX` 備援合併成功且記錄待同步；不是 Issue CLOSED。** 回讀確認成功後立即執行 `NEXT_ISSUE_DISCOVERY_REQUIRED`：查最新 GitHub Open Issue 與前置狀態、排除已完成／既有 owner／衝突工作；符合資格者直接進入下一張的派工及施工入口。原工單留言／close/readback 仍要完成，但不得把 close 當尋找下一張的前置，也不能因「已結案」就退出。沒有符合條件者要回報搜尋範圍、已檢查原因及 `NO_ELIGIBLE_ISSUE`，不得虛構已派出。

- CI 失敗 → 查該 run 的 job/step/log，修復並重測；沒有執行中的 run → 檢查 workflow branch/path 觸發與權限，修接線並重新觸發。不得將其他 SHA、舊 local GREEN 或 pending 冒充目前 PR GREEN。
- 若實際 API/權限/機器或當次執行限制阻止繼續，必須留下**可驗證的阻塞證據及續作點**，不得寫「派工交付完成」。聊天回合結束後**沒有自動背景輪詢**，除非另有明確建立的排程監控；不得宣稱本規則能自行喚醒模型。
- 以上只授權整合產品變更至 `localX`，**不授權發布正式 X**；`/推推` 是 X 產品發布的必要條件。不得增設 GitHub 分支保護、恢復 Flow v2 或其他舊交易門檻。



# 1. 專案核心精神

本專案為 V5 世代的：

> **鈑金自動展開與 DXF 生成引擎**

目前第一套完整驗證的製造體系為：

> **金庫型箱體**

但架構目標不是做成「金庫型專用程式」，而是：

> **以金庫型作為第一套 Factory Policy，建立可持續擴充的通用 2D Sheet-Metal Geometry Engine。**

---

## 1.1 揚棄 Hardcoded Vertex Arrays

新版已開始全面淘汰：

```python
cutting_points = [
    (...),
    (...),
    ...
]
```

這類針對特定零件人工排列 12 點、16 點、17 點主外框的作法。

現在主外框的核心思想為：

```text
母材 Base Polygon
        -
退讓 / 裝配切刀 Relief Polygon
        =
最終 Material Polygon
```

主要透過 Python `Shapely` 執行：

```text
difference
union
intersection
```

最終再取得 polygon exterior 作為 `CUTTING`。

---

## 1.2 Geometry 是唯一真相來源

系統正在收斂成：

```text
Config / 1.csv / 使用者參數
              ↓
      sheetmetal_geometry.py
              ↓
       Geometry Result
        ┌─────┴─────┐
        ↓           ↓
    GUI Preview   DXF Export
```

GUI 與 DXF 不應各自維護一套座標演算法。

---

## 1.3 Topology 與 Factory Policy 分離

必須區分：

```text
Topology
= 這塊板是怎麼折的
```

與：

```text
Factory Policy
= 因為裝配 / 生產需求，哪裡需要退讓
```

例如：

```text
FourSideFlange
```

是一種通用 Topology。

而金庫型封頭尾使用的：

```text
Assembly Insertion Relief
```

則屬於金庫型 Factory Policy。

禁止把目前金庫型規則直接當成所有鈑金箱體的宇宙通則。

---

# 2. 系統模組架構

目前系統主要分為三層。

---

## Layer A：幾何引擎

### `sheetmetal_geometry.py`

負責純 2D 板金幾何。

此層：

```text
不可依賴 ezdxf
不可處理 GUI
不可直接寫 DXF
```

目前主要幾何結構包含：

### FourSideFlange 系列

目前用於：

```text
Door
Indicator Box
Base Plate
End Cap / Tail
```

封頭尾雖然具有較特殊的二折與裝配退讓，但仍應盡可能建立在共用 FourSideFlange / topology 基礎上，而不是重新退化成獨立硬編碼外框引擎。

### StripFoldChain

目前用於：

```text
Box Body
Stretched Box Body
```

它代表沿單一方向連續折彎的板材。

BEND 位置由 segment cumulative sum 動態產生，不再由 exporter 自行維護：

```text
x1
x2
...
x8
```

---

## Layer B：參數整合與 DXF 輸出

### `ae.py`

### 目前開發版本可能為 `ae_3.py`

此層負責：

```text
讀 config.ini
接收尺寸參數
將舊參數轉成 Geometry / Policy
呼叫 sheetmetal_geometry
寫入 DXF layer
處理孔洞與其他 secondary features
```

加工層包括：

```text
CUTTING
BEND
MARKING
CHECK
STOCK
DATUM
```

原則：

> `ae.py` 可以做 Adapter，但不應重新實作 Shapely 主外框布林算法。

---

## Layer C：自動化產線與 GUI

### `batch_unfolder.py`

### `gui.py`

負責：

```text
讀取 1.csv
盤體分類
使用者輸入
批次派發
GUI Preview
```

目前主要待辦：

> 將 `gui.py` Canvas 裡既有的手算預覽座標移除，改為直接使用 `sheetmetal_geometry.py` 的 geometry result。

目標是：

```text
GUI Preview == DXF Structural Geometry
```

---

# 3. Relief / Clearance 的正確定位

不是所有尺寸都必須是 `T` 的倍數。

例如：

```text
ytop1
FW
yl1
yr1
```

這些是真實折邊尺寸，仍然來自：

```text
config
工單
使用者輸入
```

但加工與裝配 clearance 若本質上和板厚有關，應優先表示為：

```text
0.5T
1T
2T
fold - T
```

而不是固定毫米值。

例如金庫型封頭尾目前已確認：

```text
Top Secondary X extra = 0.5T
Top Secondary depth   = 2T
Bottom extra          = 0.5T
```

詳細金庫型規則請讀：

```text
handoff/02_VAULT_FACTORY_RULES.md
```

---

# 4. 理論幾何與加工補償的界線

本 Geometry Engine 應負責：

```text
零件真實外形
折彎拓撲
裝配必要退讓
結構性 interference relief
```

例如：

> 金庫型封頭尾為了插入箱身而產生的 Primary / Secondary Relief

這些屬於零件設計本身，必須留在 Geometry / Factory Policy。

但是下列後加工細節不應污染理論幾何：

```text
Laser Kerf compensation
Corner over-cut hole
一字清角
折床加工補刀
CAM 特殊過切
NC 加工補償
```

這些應由後端 CAM / NC 層處理。

---

# 5. 下一個 AI 的嚴格規則

## 禁止依盤名新增主幾何演算法

錯誤方向：

```python
if part_type == "NEW_PANEL":
    build_new_panel_17_points()
```

正確流程：

```text
先辨識 Topology
↓
尋找現有 Policy
↓
若已有相同物理關係，直接共用
```

---

## 禁止手算主外框 Vertex Array

不得為新截角重新推導：

```text
12 點
16 點
17 點
```

應建立：

```text
Base Polygon
+
Relief / Tool Polygon
```

再做布林差集。

---

## 禁止把金庫型 Rule 當成所有箱型 Rule

目前主要 regression 與製造規則來自：

```text
金庫型
```

未來若新增：

```text
落地盤
壁掛盤
戶外箱
其他箱型
```

應先確認實際裝配方式。

Topology 可以共用。

Factory Policy 不一定相同。

---

## 必須維持 API 邊界

`sheetmetal_geometry.py`：

```text
不可 import ezdxf
```

`ae.py`：

```text
不要自己實作主 Shapely boolean geometry
```

GUI：

```text
不得再自行維護另一套 Structural Geometry
```

---

# 6. 目前進度

目前第一階段通用化已涵蓋：

```text
Box Body
Stretched Box Body
End Cap / Tail
Door
Stretched Door
Base Plate
Indicator Box
```

目前核心方向已由：

```text
每個零件一套座標公式
```

轉成：

```text
Part Parameters
→ Topology
→ Factory / Relief Policy
→ Polygon Boolean
→ CUTTING
→ Material-clipped BEND
```

---

# 7. 下一步任務

目前下一個主要任務：

> **GUI Preview 重構**

將 `gui.py` Canvas 裡原本負責畫零件預覽的手工座標邏輯逐步刪除。

改成：

```text
GUI Parameters
      ↓
Part Adapter
      ↓
sheetmetal_geometry.py
      ↓
Outline / Bend Result
      ↓
Canvas Rendering
```

這樣才能保證：

```text
使用者畫面看到的形狀
=
最終輸出的 DXF 形狀
```

---

# 8. 接手 AI 的閱讀順序

本文件只負責「快速建立全局認知」。

需要細節時依序閱讀：

```text
handoff/00_AI_HANDOFF_README.md
```

快速接手說明。

```text
handoff/01_ARCHITECTURE.md
```

完整 Geometry / Topology / DXF 分層。

```text
handoff/02_VAULT_FACTORY_RULES.md
```

金庫型封頭尾與相關 Factory Rules。

```text
handoff/03_PART_TOPOLOGY_MAP.md
```

Door / Indicator / BasePlate / EndCap / BoxBody 的 Topology 對照。

```text
handoff/04_DEVELOPMENT_RULES.md
```

TDD、Hard-Code 禁令、Regression 與驗證規則。

```text
handoff/05_NEXT_STEPS.md
```

後續重構方向與 roadmap。

---

# 9. 接手後第一個動作

下一個 AI 不要拿到專案就立刻修改。

正確流程：

```text
1. 讀本 AGENTS.md
2. 按需求閱讀 handoff/ 細節文件
3. 讀 sheetmetal_geometry.py
4. 找目前實際使用中的 ae.py / ae_3.py
5. 讀現有 tests
6. 跑完整 test suite
7. 確認 green baseline
8. 再開始 GUI Preview 重構
```

---

# 10. 一句話核心

> **Geometry 是共用的，Factory Rule 是可配置的，Part Name 不是幾何規則；GUI 與 DXF 最終必須共用同一份 Geometry Result。**

---

## 截角資料庫來源

截角資料庫不是 Skill。它是 runtime 製造規則 Source of Truth：

```text
基準檔/截角資料庫/certified_relief_rules.json
→ ae_engine/certified_relief_registry.py
→ lookup_certified_endcap_relief()
→ manufacturing geometry
→ 2D / 3D / DXF
```

任何修改 Corner / Relief / Assembly Intent / Registry / 3D backprojection 前，必須先讀：

```text
基準檔/截角資料庫/README_母規則說明.md
基準檔/截角資料庫/certified_relief_rules.json
基準檔/截角資料庫/certified_relief_rules.schema.json
```

Registry HIT 時，Certified JSON 的公式與 metadata 是 canonical 製造答案；production code 禁止另寫第二套公式。Registry MISS 才能進 3D discovery / candidate flow，且 PROVISIONAL 結果不得冒充 CERTIFIED。



---


## 三份 localX 與人工驗收發布規則 (LOCALX_THREE_COPY_UAT_V1)

- 只有一個 GitHub 整合來源：`origin/localX`。CoreELEC `whd-dev:/workspace/whd` 的 `localX` 是 AI 施工、整合與開發測試的工作區；Windows `Z:\localX` 的 `localX` 是使用者自行更新、親自操作、測試及最終驗收的唯一使用者測試區。三者不是三條發布分支，也都不是正式 `X=cleanup/2d-3d-sync`。
- 工作成果經 exact HEAD 必要測試後，自動、安全、非強制合入 GitHub `localX`；CoreELEC 作為施工區負責將已測試成果整合回 GitHub，Windows 從 GitHub 安全快轉更新，不得用任一個副本的舊狀態強制覆蓋其他副本。Windows 同步由使用者自行執行。
- 正式 X 的所有新修改（含治理/文件/CI）一律先經 `localX`；舊的 `NON_PRODUCT_GOVERNANCE_DIRECT_X` 僅能用於此規則正式部署前的歷史解讀，不能作為後續直送 X 的執行授權。
- GitHub CI GREEN、PR merged、CoreELEC 開發測試與同步成功，都不代表使用者已實測；只有使用者在 Windows 測試區的實際驗收才可記為 MANUAL_UAT_PASS。正式 X 發布必須有使用者針對當下 exact `origin/localX` SHA 的人工驗收通過，再有之後的當次 `/推推`；若驗收後 localX HEAD 變更，必須重新確認新的版本，禁止沿用舊驗收或舊 `/推推`。
- `/推推` 前應回報此次包含的產品/治理修改及 localX、CoreELEC、Windows 各自已證實的 SHA。未驗證的副本標 UNKNOWN，不得假稱已同步。無驗收證據時只准停在待驗收狀態，不得將其當作授權請求反覆重問。
- 以上政策不變更 `main` 歷史隔離、不准 reset/force-push、不准清除未提交修改、不授權未指定的本機操作。平台層須要求 X PR 通過 `WHD Change Lane Gate` 且禁止直接推送 X；只有文檔或工作流不能替代分支保護。
