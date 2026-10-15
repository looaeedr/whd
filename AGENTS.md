---
whd_doc_role: CURRENT
whd_contract: agent-startup-process
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 開發與本地整合規則

## 日常施工來源硬閘門 `LOCALX_DEVELOPMENT_SOURCE_AUTHORITY_V1`

- **唯一日常施工與治理修改基準是 GitHub `localX`**：啟動時明確取得 `ref=localX` 的最新 HEAD，讀同一 HEAD 的 `AGENTS.md`／CURRENT Skill／產品程式與規格。新工作分支從此 HEAD 建立，既有分支先核對與最新 `localX` 的差異；產品／治理 PR 的 base 預設 `localX`，通過 exact SHA CI 後合回 GitHub `localX`。
- `X=cleanup/2d-3d-sync` **只在正式發布、發版前比較及其受信任 gate 查核時讀取**；X 的舊 `AGENTS.md` 不得覆蓋 `localX` 的施工／技能／環境選路。X-only 提交不得默默 merge、rebase 或複製到 `localX`。沒有當次 `/推推` 不可發布 X。
- GitHub repository default `main` 是歷史分支；GitHub fetch/search 未指定 ref 或無法證明所讀分支／HEAD 時不能當成施工證據，必須重讀 `localX`。使用 CoreELEC/RC/DC 不是因為 `localX` 需要本機 checkout，而只在當次使用者明確選擇對應裝置與操作並通過外部核准時採用；一般 `/派工`、BUG 修復、QA、治理改動不探測 CoreELEC。
- 舊 `NON_PRODUCT_GOVERNANCE_DIRECT_X` 僅供歷史事件分類；現在治理變更也先走 `localX`，不因治理白名單繞過正式 X 的人工驗收與 `/推推` gate。

## 所有產品修改前先讀程式與文檔硬閘門 `SOURCE_READ_BEFORE_MUTATION_V1`

- **適用所有入口**：`/debug`、`/派工`、`/接手` 與一般 BUG／功能修改。任何產品程式碼、幾何公式、GUI、3D、DXF、製造路徑、測試或 fixture 寫入前，都必須先完成真實來源閱讀；僅只讀診斷可先繼續，不得把「已搜尋到檔名」當作「已讀程式」。
- **讀取範圍以真實影響鏈為準，不是無限制掃完整倉庫**：fresh-read GitHub `localX` 最新 HEAD 的 `AGENTS.md`、目前施工分支的精確 ref/HEAD、與本問題直接相關的 CURRENT 規格／資料來源，接著讀完受影響函式的**實際內容**及入口 → 呼叫者／被呼叫者 → 資料轉換 → 2D/3D／製造輸出／保存等相關鏈路，並核對現有測試、資料檔、版本差異。需要時擴展到完整相關模組；不得只看片段就擅自寫公式或覆蓋現有邏輯。
- **讀後要有可核對的 `SOURCE_READ_EVIDENCE`**：在第一筆程式／測試修改前簡短交代 (1) repo、來源 ref/HEAD；(2) 已讀程式檔與實際函式／呼叫路徑；(3) CURRENT 規格／CSV／JSON／DXF 等根據與衝突；(4) 使用者要修的真實症狀及可判斷 RED 的測試／重現方式；(5) 最小修改範圍。這是同輪事實摘要，不另要求使用者核准、也不建立工作槽／新憑證。不得虛構閱讀或測試證據。
- **材料／座標錯誤的專項條件**：對折彎、截角、中隔與側板、裝配、孔位、碰撞，還須核對相應基準檔與座標系（尤其 Z 基準、變換、正反面、折向、避讓關係），以及資料進入 GUI、3D、碰撞檢查和製造輸出的實際路徑；不得以當前畫面／既有錯誤輸出／測試 fixture 反推規格。
- **Fail closed**：缺任一必要原始碼／CURRENT 文檔、無法核對分支、讀到規格衝突或未取得可重現的正確性判準時，標 `SOURCE_READ_PRECONDITION_FAILED`，先補讀／查證／只讀診斷，**禁止猜測後直接寫產品程式或回歸期待值**。確認來源後直接續作，不用重問已授權的同範圍工作；此閘門不擴充 DC／本機權限，也不跳過 exact SHA CI、`localX` 與人工驗收。

- **預設 `main` 歷史隔離（`MAIN_HISTORICAL_UNMANAGED_EXPLICIT_X_ONLY`）**：`main` 保持原狀，視為非現行歷史分支；**不清理、不縮成 tombstone、不自動合併、鏡像、同步或刪除**。開發／治理的 CURRENT 施工權威是 GitHub `localX`；`X=cleanup/2d-3d-sync` 僅保有正式發布與其受信任發布 gate 的權威。凡 GitHub／Agent／Skill／CI 查詢日常施工規則，必須明確指定 `ref=localX`；未指定 ref、工具默認落到 `main` 或無法確定 HEAD 時，須以 localX 重讀並 fail closed。只有正式發布查核才使用精確 `ref=cleanup/2d-3d-sync`，且此 X ref 不得作為日常產品／治理施工基準。舊 `WHD_DEFAULT_BRANCH_FAIL_CLOSED_V1` 的 `MAIN_MINIMAL_TOMBSTONE_TREE` 要求已退役，不得再次啟動 `main` 清理；使用者另有當次明確指令才可另行規劃 `main` 變更。
- **舊工單交易、工作槽與 lease 控制系統已退役**；不得要求其憑證、工作槽、Preflight receipt 或其他管控才能執行修改、測試、Git commit。
- **入口及階段分流**：`/派工` 的施工、測試、commit、PR、CI 僅可在 GitHub／排程／雲端進行；同工單 exact SHA CI SUCCESS 後，**預設透過 GitHub PR 合併到遠端 `localX`（`GITHUB_LOCALX_FIRST`）**，不先進 DC。Windows `Z:\localX` 使用既有 Fast-forward 更新腳本並手動 GUI 驗收；`/接手` 需當次明確指令才能 RC 施工。
- **產品施工通道**：已授權的同 Issue／BUG 修復範圍含施工、PR、exact HEAD CI 與 GitHub 遠端 `localX` 最終合併，不需每張 PR 再問合併許可。合併前核對當前 PR head/base、scope、全部必要 CI、mergeable、base 演進與測試覆蓋；用 `expected_head_sha` 且不得 force/reset。合併後 readback PR merged 與 GitHub HEAD，回報 `GITHUB_LOCALX_MERGED + WINDOWS_LOCALX_SYNC_PENDING`；未取得 Windows 真實 SHA 不得稱同步成功，更不得捏造人工 UAT 成功。GitHub 平台拒絕時不得改用 DC 繞過；正式產品 X 仍限當次 `/推推`。
- **治理變更與正式 X 現行硬閘門（`NON_PRODUCT_GOVERNANCE_DIRECT_X` 歷史分類）**：純治理／技能／流程測試可以獨立於產品本體施工與產品 QA，但現行正式 X 的受信任 `tools/change_lane_gate.py::evaluate_pr` 已限制所有 X PR 必須 head=`localX` 且具 Windows UAT、當次 `/推推` 的 owner 精確證據；**不能僅憑治理分類直合 X**。治理先透過 GitHub PR 整合 `localX`，發布 X 遵守受信任 X 閘門；若另行合法修改正式 X gate，必須配套更新 tests 與規則，不可只修改 Skill 宣稱已放行。
- **非本體 CI 排程／驗收權威硬分流（`CI_SCHEDULING_ONLY_V1`）**：純 CI 排程數字、既有 Runner 選型可依 `tools/change_lane_gate.py` 的**受信任 base X → PR HEAD 實際 blob 差異**執行 CI 調度分類驗證，不需本機 `localX`／DC／完整產品回歸。產品驗收主 workflow `.github/workflows/whd-product-regression.yml` **不得僅憑副檔名或 `.github/workflows/` 目錄判定治理**：只有對既有行的 `runs-on`、`timeout-minutes`、`max-parallel`、`retention-days` 且舊值、新值均符合白名單的替換能例外直送。增刪行、修改觸發 paths、matrix shards、jobs/if、測試指令、必跑步驟、CI 名稱、artifact 集合、完整性檢查一律產品通道；`tools/product_ci_regression.py`、`tools/product_ci_green_reuse.py`、`tools/whd_v15_acceptance_evidence.py`、產品測試清單／驗收矩陣與相關測試，永遠不能只靠 CI 調度名義豁免產品回歸與 `/推推`。GitHub X 的 required `WHD Change Lane Gate` 必須由**受信任 X 版本**執行這項判定。未知／缺少 git diff 證據 fail closed，不得自行改走本機。 **此分類不是從 X 開發或繞過 `localX → 人工驗收 → /推推 → X` 的授權。**
- **混合／未知檔案一律回產品通道**：只要包含一個非白名單路徑，即不得以治理分類豁免產品 QA 或正式 X 發布閘門；檔案改名必須同時分類舊、新路徑，空 diff、跨 repo、來源分支不符都 fail closed。正式判斷由 `.github/workflows/whd-change-lane-hard-gate.yml` 與 `tools/change_lane_gate.py` 執行。
- GitHub 正式硬閘門必須在 X 的 Ruleset 把 `WHD Change Lane Gate` 設為 required status check，否則只能算 CI 檢查、不能宣稱平台端不可繞過；直接 push X 應由分支 Ruleset 禁止。
- 禁止遺失使用者本地未發布修改，禁止用 X 覆蓋 localX。保留程式碼 review、製造幾何與產品回歸檢查；無需工單交易硬閘門。
- 本地工作不需 Google Drive 工作根目錄，也不需調用舊協調分支。
- **兩入口共享交付範圍、不共享施工權限**：`/派工` 與 `/接手` 共用 Issue、PR、產品驗收標準，但前者預設 GitHub 施工與 GitHub `localX` 合併，不以 PR GREEN 自動授權 DC。`/接手` 僅當次明確允許 RC；DC 必須有特定目的／裝置／操作授權且經外部審查。治理變更也先整合 `localX`，正式 X 仍限驗收後的 `/推推`。

## 新增功能入口 `/功能` — `FEATURE_FLOW_V1`

- `/功能` 路由至唯一 CURRENT `.agents/skills/engineering/新增功能/SKILL.md`；支援 `/功能 設計`（只讀）、`/功能 新增`（合法 GitHub 功能施工與 localX 整合）、`/功能 繼續 #Issue`（沿用原工單／PR）。`/debug` 仍由 `diagnosing-bugs` 處理既有錯誤；不建立第二套派工、lease、測試或發布系統。
- 施工前遵守 `SOURCE_READ_BEFORE_MUTATION_V1`，依真實影響核對 GUI、資料、Save→Reload、2D、3D、碰撞、製造及舊功能；不適用領域可有理由 N/A。`WHD_CHANGE_TEST_PROFILE_V1` 的 FEATURE、UI／GEOMETRY 與 final gate、`GITHUB_LOCALX_FIRST`、Windows 人工 GUI UAT 均維持原權威。
- 同範圍功能之 PR exact SHA CI SUCCESS 後可整合 GitHub 遠端 `localX`；Windows 同步／人工驗收是獨立待辦，正式 `X=cleanup/2d-3d-sync` 仍須使用者驗收及當次 `/推推`，不得修改 RC／DC 權限或以 X 作日常施工來源。

## WHD 長對話上下文損耗防護 `WHD_CONTEXT_LOSS_PREVENTION_V1`

**目的：降低本體因對話過長、重複工具輸出或系統壓縮而遺失已決定事項的機率。這不是交接流程。** 平台不提供可直接讀取的「剩餘 Token 百分比」或下一次自動壓縮時點，無法保證不被截斷，也不能主動清除既有上下文；禁止捏造容量、倒數或「已開啟背景監控」。

1. **先控制上下文占用**：GitHub/API/長日誌優先取得指定檔案行範圍、diff／變更路徑、run/job/step 摘要與失敗切片；只要結果足夠作判斷，就不回傳整份 `AGENTS.md`、全量 commit 列表、重複長 Log 或同一份已讀文件。工具回傳過長時，在工具結果處先萃取必要欄位，固定有限上限（一般 log tail 不超過 80 行），完整證據留來源平台，不灌滿對話。
2. **只維護當輪精簡工作事實**：在當次執行中以最小工作狀態辨識 `Issue/PR`、`branch/HEAD`、已確認的使用者決策、剛完成的操作、精確下一步；僅實際變動時更新，不把整套規格或工具輸出重新敘述一次。這是當前作業的上下文節流，**不建立新交接文件、工單、排程、定時檢查或跨對話記憶承諾**。
3. **從可觀察異常防止錯做**：工具結果 `truncated`、既有摘要取代原文、發現不一致 SHA／PR、無法確定使用者已決定的條件時，標示「上下文資訊需核對」，只針對缺少的事實重讀 GitHub `localX` 精確 HEAD 或原 Issue/PR／此對話決策；只有正式發布查核才讀 `X=cleanup/2d-3d-sync`，不猜、不重新問已提供的答案，也不全面重新 Discovery。若原決策無法核實，清楚標未核實，尤其不能據此做不可逆合併／發布。
4. **已在執行時不中斷**：風險提示不等於停止施工。CI／工單狀態沿用現有 exact `HEAD`／`run_id` 與已取得的結果；只補讀缺口，不因對話濃縮而重新觸發測試、重做工單接取或要求使用者再輸入「繼續」。重大合併前回讀現況，不把過期摘要當權威。
5. **誠實提示但不假裝預知**：只有觀察到內容截斷、資訊矛盾或真實銜接困難才簡短提醒，並說明正在核對的具體項目；`/上下文` 可以要求現在的可觀察風險評估，但不是原生容量計量器。不得把「對話很長」推論成某個剩餘百分比或自動提醒已啟動。

本規則僅改善本體處理資訊的方式，不擴充 DC／本機權限，也不新增 GitHub 施工前置硬閘門；非本體治理修訂從 GitHub `localX` 開分支並經治理 CI 合回 `localX`。歷史 `NON_PRODUCT_GOVERNANCE_DIRECT_X` 不是今日直送正式 X 的授權。

## `/推推` 發布先行、X 回同步硬閘門 `LOCALX_PUBLISH_THEN_X_BACKSYNC`

- **預設本機優先，GitHub-only 須當次明確授權**：一般 `/推推` 先查本機 `localX`、GitHub `localX`、正式 X 的 fresh SHA／未發布修改，將本機驗證版本以非強制方式同步 GitHub `localX`，讀回一致後再發布；遠端超前或分叉須安全整合，不 reset、不強推。**只有使用者當次明確指定 `GitHub-only` 發布、範圍包含現有遠端 `localX` 內容且接受「本機同步待辦」時**，才允許不讀／不改本機，直接以已完成遠端 `localX` 整合及 exact HEAD 為來源建立 X PR；本機 HEAD 只能標 UNKNOWN／`LOCAL_SYNC_PENDING`，不可虛稱三方已對齊。一般「/推推」「繼續」不得冒充 GitHub-only 授權。
- **X 超前只能是非本體**：發布前只**檢查** X 相對於 `localX` 獨有的所有 commit（含 merge commit 第一父提交的差異），並以 `tools/change_lane_gate.py` 的治理白名單逐一核對。任何本體／混合／未知路徑、無法證實的歷史均 `X_AHEAD_NON_GOVERNANCE_BLOCKED`，不得假設「一定只有文件」。通過時也**不得在正式發布前**先把 X pull／merge／rebase 進本機或 GitHub `localX`。
- **X-only 歷史時區 CI 相容例外（只讀）**：僅兩個已在 X 合併且驗收的不可變提交 `06d97ca575ebf9c2973ab3fdaa669787702faac4`、`beac45c3b3afc5bb11629fcbcd6e1e51b76c8e09`（新增 `Asia/Taipei` 環境與來源時間安全檢查）可在 X-only 歷史回讀時視為治理；還須確認其除既定 CI workflow 外的差異全屬治理白名單。**不授權任何新 PR、其他 workflow 變更或任意 SHA 豁免**；產品發布與當次 `/推推` 仍照原硬閘門。
- **先發布，再回同步**：使用者當次 `/推推`、exact PR head/base SHA、GitHub owner comment、必要 CI、X-only 治理歷史與無衝突都符合後，由 GitHub `localX` PR **合併至 X**（不 force、不覆蓋）。預設發布後先從 X fast-forward 同步**本機 `localX`**，必要驗證後非強制同步 GitHub `localX`；**當次明確 GitHub-only** 則僅可在 GitHub `localX` 為發布後 X 的祖先時，以 `expected_sha` 限定、非強制 fast-forward 遠端 `localX` 至 X，留下本機 `LOCAL_SYNC_PENDING`，不探測 DC／RC／本機。
- **三方回讀與狀態分流**：只有實際確認 `HEAD(本機 localX) == HEAD(GitHub localX) == HEAD(X)` 且 PR merged 才能回報 `PUBLISHED_AND_SYNCED`。當次明確 GitHub-only 發布，若 X PR merged 且遠端 `localX` 已非強制對齊，**只能**回報 `GITHUB_ONLY_PUBLISHED + LOCAL_SYNC_PENDING`，本機 SHA 未查為 UNKNOWN；不可宣稱三方同步。若 DC 不可用、認證拒絕、衝突或 GitHub 更新導致任一步失敗，回報 `POST_PUBLISH_LOCALX_SYNC_PENDING`、已知 SHA／真正原因；不重複索取 `/推推`，不得 force 或覆蓋未發布資料。
- **通道不變**：治理／技能／非本體文件也由最新 GitHub `localX` 開工作分支，通過必要治理 CI 後 PR 合回 `localX`；只有完成 Windows UAT 且使用者當次 `/推推` 才進正式 X。不得以過時治理直送 X 說明或 CoreELEC 工作副本繞過這條邊界；發布操作仍須遵守平台審查。

## 當次明確 GitHub-only 產品發布例外 `GITHUB_ONLY_PUBLISH_EXPLICIT_SCOPE_V1`

此例外**僅改變指定當次產品發布的整合位置與同步回報，不是另一條無授權發布捷徑**：使用者須明確指向 GitHub-only 的 `localX → X` 發布、包含的新產品功能／範圍、以及本機同步待辦。先確認遠端 `localX` 已整合相應產品 PR、當下 head/base SHA、必跑 CI（含正式 X PR 自身）、GitHub owner exact `/推推` 留言及 X-only 治理歷史；任一 HEAD 或產品範圍中途變更，必須按新版本重新驗證與取得覆蓋新範圍的當次明確授權，不能沿用舊 SHA 紀錄。

發布後僅在確定 fast-forward 時更新**遠端** `localX`；本機標 `LOCAL_SYNC_PENDING` 並留待使用者另行授權的安全同步，不使用 DC、RC、本機 shell，不 reset／強推。**未取得 GitHub-only 明確授權時，`LOCALX_PUBLISH_THEN_X_BACKSYNC` 仍採本機優先。**

## 全域台灣時區硬閘門 `TAIWAN_TIMEZONE_HARD_GATE_V1`

- **唯一人類操作時區**：`Asia/Taipei`（UTC+08:00），涵蓋本專案的 Agent、ChatGPT 回報、工單／PR 留言、文件發布時間、測試摘要、排程與提醒、GUI 顯示、日誌檢視、交付檔名及相對日期（今天／明天／週末）的解讀；不得依執行機器、瀏覽器、GitHub Runner 的預設時區自行決定。
- **時間必須可辨識時區**：人類可讀的完整時間戳採 `YYYY-MM-DD HH:mm:ss +08:00` 或帶 `+08:00` 的 ISO 8601；僅顯示日期時須已先換算到台灣日期。不能輸出無標示時區的日期時間並冒充台灣時間；夏令時間不得套用至台灣。
- **CI 強制執行**：關鍵 GitHub Actions jobs 必須設 `TZ=Asia/Taipei`，`tools/change_lane_gate.py` 檢查明確的環境設定與 ZoneInfo offset；任一不符即 `TAIWAN_TIMEZONE_HARD_GATE_FAILED`。增修 Python 日期時間產生點時，不得加入無時區的 `datetime.now()`、`datetime.today()`、`datetime.utcnow()`、`datetime.astimezone()` 或使用執行機器本地時間的 `time.localtime()`。新改動由 CI diff guard 驗證；歷史既有日期來源需分批補上精確的產品回歸，不以文字規則冒稱已改好。
- **排程換算**：需求的日／週／幾點一律先用台灣時間解析；若 GitHub Actions cron 或第三方 API **僅接受 UTC**，則只在傳輸層轉換成等價 UTC（例如台灣 08:00 對應 UTC 00:00），顯示與排程權威仍為 `Asia/Taipei`；不得因 runner 預設 UTC 造成日期跨日錯誤。
- **外部格式例外不等於使用 UTC 操作**：GitHub 事件 ISO UTC、Unix epoch、Git commit 與 API 明定 UTC 的儲存／簽名／傳輸欄位保留原格式，不擅自改寫證據；在回報、呈現或作本地日界判斷前必須換算台灣時間。保證同一瞬間不因格式轉換而改變。
- **禁止藉時區門檻擴權**：不修改舊工單交易規則、既有排程啟停、產品幾何與 DC 權限；此硬閘門的治理變更一樣先由 GitHub `localX` 開分支及 PR 合回，不准藉時區治理直送 X。`AGENTS.md` 與 `.agents/contracts/WHD_TAIPEI_TIMEZONE_HARD_GATE_V1.json` 為時間權威，後續 SOP／技能需從此契約繼承。

## 全域 DC 硬閘門 `DC_DEFAULT_DENY_EXPLICIT_SCOPE_GATE`

**DC 預設禁止**，連 `list_devices`、`ping`、讀取與 shell 都不能先探測再求授權。`/派工` 或一般 BUG 修復的 CI GREEN 只觸發 GitHub `localX` 合併，絕非 DC 授權。
- **預設產品路線**：`GITHUB_LOCALX_FIRST` 不使用 DC、不要求 DC 斷線證據、不標示 `DC_UNREACHABLE`；Windows `Z:\localX` 由使用者 Fast-forward 自行同步，未回讀時標 `WINDOWS_LOCALX_SYNC_PENDING`，人工製造驗收另記 `WINDOWS_UAT_PENDING`。
- **特定 DC 操作**：僅在使用者當次明確指定工作、裝置、路徑及讀／改／執行範圍時才可使用，並接受外部存取審查。`/接手` 的 RC 施工、`/推推` 的發布所需本機核對也不得超出各自明確範圍。外部審查拒絕即 `DC_AUTHORIZATION_REJECTED`，停止 DC，不得改走 shell 或用技能取代平台許可。
- **明確本機整合**：當次使用者特別選用 DC 並獲核准時，僅於 exact CI 成功後安全整合指定 `localX`、保留未發布修改、不 reset／強推，雙端回讀才可報 `LOCALX_SYNCED`。
- **拒絕處置**：GitHub PR 合併遭拒就報真實衝突／權限／測試問題；不可因 DC 拒絕而阻塞原本不需 DC 的 GitHub `localX` 整合。
## 一般對話 BUG 修復授權延續 `CONVERSATIONAL_BUGFIX_LOCALX_CONTINUITY_V1`

- 已明確要求執行的同 scope BUG 修復（不是純討論）授權包含 GitHub 施工、必要測試、PR／CI 與 GitHub 遠端 `localX` 安全整合；無需因新 commit SHA 或每張 PR 重問原有範圍的許可。跨 repo／工單／scope 仍須重新核實。
- `tools/localx_publish_gate.py::require_github_localx_integration` 只對已可信驗證的對話與 fresh exact CI/PR 做純檢核，不能把 caller JSON 當成真正授權證據。預設不讀本機；只有當次明確 DC 授權和外部平台核准，才可用 `require_conversational_bugfix_localx_integration` 的明確 DC 路線。
- GitHub 合併不代表 Windows 已更新／驗收；回報 `GITHUB_LOCALX_MERGED + WINDOWS_LOCALX_SYNC_PENDING`。BUG 授權不允許直接產品 `localX → X`；X 仍要當次 `/推推`。
## 合併後測試證據沿用硬閘門 `MERGE_TEST_REUSE_HARD_GATE`

- 工作區與 exact HEAD 必要測試／CI 通過後，**合併不是自動重跑 GUI／完整回歸的理由**。先回讀 trusted test receipt 和合併後實際 Git tree；`tools/change_test_profile.py::evaluate_merge_test_reuse` 對已測試 commit 與整合 commit 做 read-only tree 比對。tested tree 與 integrated tree 完全相同（即使 commit SHA 不同）且所需測試完整通過 → `REUSE_VERIFIED`，直接保留 GREEN 並執行 Git SHA／merge/readback，不得重啟已完成的 GUI 測試。
- 兩個 tree 不同 → 先列出 `git diff` 實際異動路徑、衝突與依賴影響，僅補跑未被原證據覆蓋的目標 GUI／模組／整合測試；影響不可界定才跑完整回歸。缺少可核驗測試收據、測試未完成、CI 非 SUCCESS 或 Git tree 無法回讀 → `EVIDENCE_INCOMPLETE`，**不得冒稱免測通過**。
- 已在執行的本機測試應先核對是否真屬重複且可安全停止；不得為求速度殺掉未知程序、取消必要測試或破壞本機檔案。安全同步 GitHub `localX` 與正式 `/推推` 權限邊界均不變。此決策器**不代替** GitHub CI 簽章及真實外部驗收，執行者須從可信來源驗證輸入後才能採信。

## /派工跨工單自動收尾 `DISPATCH_DEFAULT_LOCALX_CONTINUATION_V1`

同工單已授權的 `/派工` 在 exact CI SUCCESS 後，**預設 `GITHUB_LOCALX_FIRST`**：回讀 PR/base/head、測試、mergeability 和 base 新變動，必要時僅補測差異；GitHub PR merge 使用 `expected_head_sha`，合併後 readback remote HEAD／PR。**不使用 DC、不要求另一張每 PR 合併口令**；Windows `Z:\localX` 由使用者執行既有更新腳本，未取得證據不可冒稱同步或 UAT 成功。
不可 force/reset、跨 scope、借用過期 CI、提前 `/推推` 發布。遠端合併後立即續作 Issue 結案回讀與下一張工單發現；只有真實阻塞才停。
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
- **原權限不變。** `/派工` 的 BUILD／TEST／COMMIT 不得改用使用者本機、RC 或 DC；必要 exact SHA CI、`LOCALX_INTEGRATION` 與產品正式發布 `/推推` 均不豁免。本條只改執行者優先順序；**修改治理文件／技能本身由 `localX` 建分支、通過治理測試後先合 `localX`，不需產品 QA；正式 X 仍受發布閘門限制。**

## /派工真實啟動證據 `DISPATCH_EXECUTOR_HANDOFF_REQUIRED`

- **/派工不是只登記 Issue/PR。** 先依 `DISPATCH_SELF_EXECUTION_FIRST` 由本體使用現有 GitHub／雲端 CI 能力直接施工；只有本體缺少實際能力才尋找、啟動外部雲端代理。Issue、PR、留言、指派欄位、未對應實質施工的 CI run、外掛搜尋都不是開工證據，不能宣稱已派工或執行中。
- **成功證據必須回讀：** `EXECUTOR_START_CONFIRMED` 必須有可核對的 Issue、原工作分支、執行者身分與真實施工動作。**本體施工**以實質 commit SHA、PR、exact GitHub Actions run／測試結果為憑，不要求外部 task ID；**委派外部代理**才需真實啟動回執／task ID 及代理接取。單純留言或宣稱已接取不算施工，不得冒稱另有 Agent。
- **失敗必須真實結束：** 只有登記成功時標 `DISPATCH_REGISTERED_ONLY`；無法調用實際雲端施工入口時標 `REMOTE_EXECUTOR_UNAVAILABLE`；呼叫遭拒／未得到接取證據時標 `DISPATCH_START_UNCONFIRMED`，列明拒絕或未證實之處、最後可驗證狀態與續作入口，不得稱派工完成、不得假裝背景有人施工。**不要再創第二張 Issue／PR 來掩飾失敗。** 不得因此改走 DC、本機或未授權 `/接手`。
- **成功接取之後**仍須按現有 CI、`localX` 與 `/推推` 規則續作；這只是防止「登記即完成」的真實性檢查，**不建立舊式 lease／claim／Flow v2 或新的輪詢排程**。

## `/派工` 分階段位置硬閘門 `DISPATCH_CLOUD_BUILD_GITHUB_LOCALX_ONLY`

- `DISCOVERY / BUILD / TEST / COMMIT / PUSH / PR / CI`：只能 `GITHUB|SCHEDULER|REMOTE_ACTION`，不准 RC／DC／本機 shell 替代。
- `LOCALX_INTEGRATION`：**預設 GitHub `localX` PR 合併與回讀**，絕不預設 DC；本機未知一律 `WINDOWS_LOCALX_SYNC_PENDING`，Windows 由使用者手動更新／UAT。
- 只有當次明確 DC 操作且外部審查通過，才在 CI GREEN 後受限使用；保留未發布內容、不得 reset/force。正式產品 X 仍限當次 `/推推`。
## GitHub `localX` 預設整合 `GITHUB_LOCALX_FIRST_V1`

同工單已有合法施工授權即可執行**GitHub-only 遠端 `localX`** 正常收尾，不再把它當 DC 斷線例外。前提是 exact HEAD 必要 CI 全部 SUCCESS、PR base=`localX`、mergeable、原工作分支及 scope 有證據、最新 base 演進無未驗影響；用 `expected_head_sha` merge 並 readback PR merged 與遠端 HEAD，不能 force/reset 或繞過外部上傳審查。
遠端合併只回報 `GITHUB_LOCALX_MERGED + WINDOWS_LOCALX_SYNC_PENDING`，不冒稱 Windows 同 SHA、UAT GREEN、DC 失聯。Windows `Z:\localX` 沿用現有 Fast-forward 腳本及人工 GUI／製造驗收；無 `/推推` 不得發布正式產品 X。
## /派工退出前查核 `DISPATCH_TURN_EXIT_GATE_V1`

**執行者必須先判斷下一個合法動作，才可正常結束當前施工回合。** 狀態表權威為 `.agents/contracts/WHD_DISPATCH_TURN_EXIT_GATE_V1.json`；它是治理契約，不是平台層級的 ChatGPT 回合攔截器。只有本體當輪具備實際工具能力才能執行續作；此契約**不會在回合結束後自行喚醒模型或啟動背景輪詢**。

- **先對準 exact HEAD**：讀取當下 PR `base=localX`、`head_sha` 與同一 SHA 的 Canonical Product Regression `run_id/status/conclusion`、jobs。缺 run、查到舊 SHA／矛盾資料 → `RECONCILE_ONLY`，不得借用其他 HEAD 的 GREEN。
- **CI 非終態**（`requested/queued/waiting/pending/in_progress`）→ `CONTINUE_POLL`：在當次仍可呼叫工具時持續查詢 exact run，2–3 次操作回報一次實質進度，回報不是退出訊號；只讀結構化狀態與精簡失敗資料，不重抓長 Log、不要無限制高頻打 API。
- **CI 終態**：`success` → `LOCALX_INTEGRATION_PENDING`，立即走 GitHub remote `localX` 合併及 readback（預設不需 DC）；`failure/cancelled/timed_out/action_required` → `REPAIR_AND_RETEST`，不可將 GREEN 誤報產品 X 已發布。
- **CI 成功仍未完成交付**：本機／遠端 `localX` 整合回讀、Issue close/readback 及 `NEXT_ISSUE_DISCOVERY_REQUIRED` 等既有義務未處理 → `CONTINUE_FINALIZATION`；達到所有必要驗收與追蹤義務、讀回證據後才可標 `RELEASED`。正式 X 仍限使用者當次 `/推推`。
- **允許當回合非完成式退出的真實例外**：有可追溯 API 錯誤／權限拒絕／無合法執行途徑 → `BLOCKED_WITH_EVIDENCE`，或執行環境真實中斷／當回合工具資源限制 → `RUNTIME_LIMIT_UNRESOLVED`；回報當時 `Issue/PR/head_sha/run_id/last_observation/blocker/next_exact_action`，**不得標示 DONE、已完成、背景自動續作**，不得假造阻塞來取代仍可做的輪詢。
- **不擴權**：本規則只對現有 `/派工` 回合施加退出前的決策檢查；不啟動新排程／`workflow_run` 自動施工、不重建舊 Flow v2、不增設 GitHub 分支保護，不允許提早使用 DC／RC／本機；純治理文件先從 `localX` 建工作分支、跑治理測試、PR 合回 `localX`。正式 X 的任何發布仍需人工驗收和當次 `/推推`。

## /派工 產品交付不中斷閘門（執行者責任）

- `/派工` 不以「已建立 PR」「CI queued/in_progress/pending」作為交付完成。這些都是 **CONTINUE_POLL**，不能以「等 CI 完成」作最終答覆來退出當輪任務。
- 一旦已建立指向 `localX` 的產品 PR，就應在**當次可執行回合**追蹤 exact PR HEAD、base 與 Canonical Product Regression 的 GitHub Actions run；短間隔再次查詢。每 2–3 次操作回報實質進度，但**回報本身不是停止訊號**。
- exact HEAD 的 Product Regression `SUCCESS` 且 PR 可整合 → **GitHub PR merge `localX`**，核對 head/base/scope/CI、最新 base diff，merge 後遠端 SHA/PR 回讀，標記 `GITHUB_LOCALX_MERGED + WINDOWS_LOCALX_SYNC_PENDING`，回寫 Issue 與 close/readback 並查找下一張。Windows 以 `Z:\localX` 腳本自行更新與人工驗收；不再預設 DC，也不冒稱 Windows 同步成功。產品 X 仍必須當次 `/推推`。
- **下一張工單觸發點**：GitHub 遠端 `localX` PR 合併及 HEAD／PR readback 成功即 `NEXT_ISSUE_DISCOVERY_REQUIRED`，不要求 DC、CoreELEC 斷線證據或 Windows 已同步；原工單留言／close/readback 仍要完成。搜尋 OPEN Issue、排除衝突／已接取及未滿足前置；找不到符合條件則回報 `NO_ELIGIBLE_ISSUE`。不得把 Issue CLOSED 當作唯一觸發條件。

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

- 只有一個 GitHub 整合來源：`origin/localX`。CoreELEC `whd-dev:/workspace/whd` 的 `localX` 僅是當次明確選用時的可選測試／施工副本；Windows `Z:\localX` 的 `localX` 是使用者自行更新、親自操作、測試及最終驗收的唯一使用者測試區。三者不是三條發布分支，也都不是正式 `X=cleanup/2d-3d-sync`。
- 工作成果經 exact HEAD 必要測試後，自動、安全、非強制合入 GitHub `localX`；預設由 GitHub／雲端將已測試成果直接合回 GitHub `localX`；CoreELEC 不必參與；Windows 從 GitHub 安全快轉更新，不得用任一個副本的舊狀態強制覆蓋其他副本。Windows 同步由使用者自行執行。
- 正式 X 的所有新修改（含治理/文件/CI）一律先經 `localX`；舊的 `NON_PRODUCT_GOVERNANCE_DIRECT_X` 僅能用於此規則正式部署前的歷史解讀，不能作為後續直送 X 的執行授權。
- GitHub CI GREEN、PR merged、CoreELEC 測試都不等於已在 Windows 人工操作。**使用者下達當次 `/推推`，即代表使用者已決定驗收當下的 exact GitHub `localX` 版本並授權正式發布**，不再另外要求 `/驗收通過` 或 Windows 測試回執；不得將此決定虛構為實際 Windows GUI 測試。發布前若 head SHA 改變，必須重新取得涵蓋新版本的使用者 `/推推`；exact PR、CI、X-only 安全檢查與 GitHub Ruleset 仍須全部通過。
- `/推推` 前能查得的產品／治理範圍和 SHA 應據實回報；GitHub `localX`、CoreELEC、Windows 各自已證實的 SHA 不得混用。Windows 未同步／未測試標 UNKNOWN 或 PENDING，但**不再阻止使用者用 `/推推` 宣告驗收與發布**。不可重複索取第二道驗收口令。
- 以上政策不變更 `main` 歷史隔離、不准 reset/force-push、不准清除未提交修改、不授權未指定的本機操作。平台層須要求 X PR 通過 `WHD Change Lane Gate` 且禁止直接推送 X；只有文檔或工作流不能替代分支保護。

## /推推 最終新版本發布硬閘門 (LOCALX_PUBLISH_OFFICIAL_RELEASE_V1)

- **/推推 最後一步是建立正式 GitHub Release，不是 PR merge**：使用者當次 `/推推` 直接構成驗收與發布授權，對應 exact GitHub `localX` SHA。通過必要 CI、正式 X PR 已合併、GitHub `localX` 安全回同步後，核對 HEAD(X) = HEAD(GitHub localX) = X merge SHA，才可發布正式 Git tag 和 GitHub Release。Windows／CoreELEC 若尚未同步仍獨立標記待辦，不得聲稱已測試或同步。
- **自動完成而不誤發布**：`.github/workflows/whd-official-release.yml` 僅對 GitHub localX push 檢查。localX 與正式 X 不同，或 X 最新提交不是來自當次 `/推推` 授權的 localX→X PR，均不得發布。由 X merge commit 兩個不可變 parent 取回原 X/base 與 localX/head，驗證 GitHub owner 的 `WHD_LOCALX_PUBLISH_AUTH_V1` exact SHA 留言；歷史 `WHD_WINDOWS_LOCALX_UAT_V1` 可保留作為測試紀錄但不再是發布前置。不得信任合併後會漂移的分支 SHA。
- **版本與稽核**：命名為 vYYYY.MM.DD-x-<merge SHA 前12碼>，日期以 GitHub merged_at 轉為 Asia/Taipei。Tag 的目標必須是完整 40 位 X 合併 SHA。Release 內容須列來源 PR、正式 SHA、授權與發布說明。重跑只可確認並重用相同 tag/SHA/Release；衝突時失敗，不重寫或移動舊 tag。version.txt 依 .gitignore 保持不進 Git、不得為發版改寫。
- **最後完成硬閘門**：只有 Release 公開發布（不是 draft、不是 prerelease）、tag SHA 精確對齊 X merge、URL 存在且已回讀，才可回報 OFFICIAL_RELEASED。否則 OFFICIAL_RELEASE_PENDING／OFFICIAL_RELEASE_FAILED；PR merged、CI GREEN、GitHub branches synced 都不等於 /推推 完成。權限或 API 失敗時原工作流必須保留失敗並可重跑；不重新合併 X，也不再索取一次 /推推。
- **不擴權**：此自動化只驗證真實使用者當次 `/推推`、精確 PR/SHA、必要 CI 和 X 安全整合；不追溯歷史提交、不碰 `main`、不改 Windows 本機、不授權 RC/DC。取消強制雙重驗收，不等於冒稱 GUI 手動測試已執行；平台 Ruleset／權限審查仍有效。

