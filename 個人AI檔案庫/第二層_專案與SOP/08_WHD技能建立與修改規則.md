---
whd_doc_role: REFERENCE
whd_contract: ai-library-reference
whd_canonical: null
whd_schema: WHD_DOC_META_V1
whd_doc_id: WHD-SOP-SKILL-AUTHORING
---
# WHD 技能建立與修改規則

> 目的：讓所有後續 AI 在建立或修改 `.agents/skills/**` 時，不再把特定模型、特定 CLI、背景 Subagent、viewer 或 TodoList 當成普遍存在的能力，並維持 Skill 資料夾、frontmatter、路由與引用的一致 identity。

## Authority

1. 使用者本輪明確核准規格最高。
2. `AGENTS.md`、Phase6 Knowledge Preflight、WHD 專案 Skill/Registry/AI Library/Source of Truth 次之。
3. 通用 skill-writing 慣例只能補充，不能繞過 WHD gate。

## Skill startup communication 硬閘門

<!-- SKILL_INVOCATION_ANNOUNCEMENT_GATE_V1 -->

只要本回合實際使用 WHD Skill，startup communication 必須先於 substantive work，但 surface 依 runtime 能力：

- ChatGPT / interactive chat：第一個 user-visible 行／句公告 canonical Skill identity。
- Codex / CLI / headless：第一個 machine-visible `STDOUT / TASK_EVENT / LOG` 記錄 canonical Skill identity + startup declaration。
- 沒有 chat UI 不得成為 blocker；不得要求 headless executor 等待不存在的 ChatGPT surface。
- announcement 不取代 Skill read、Phase6 Preflight、required references、RED/GREEN 或其他 execution evidence。
- machine contract=`WHD_EXECUTION_STARTUP_COMMUNICATION_V1`。

## 必守規則

- 普通 Skill authoring 使用 executor-local repo workspace + fresh `cleanup/2d-3d-sync` baseline；Codex 常見 `/workspace/whd`。
- baseline `READ/FETCH/COMPARE/BRANCH_READ/REPO_METADATA_READ` 不需第二份 remote authorization。
- 使用者已明確要求 exact repository-content task 時，同 invocation + 同 scope 的 tested delivery 可一次 mint `WORKSPACE_DELIVERY`；push/PR/CI/merge 不得重問相同授權。
- Drive/shared-zero 已退役；有無 historical drift 都固定 WORKSPACE_DEFAULT，不得啟動 shared-zero fallback、merge/freeze 或 /推推 前置。 repository-content 修改先在 executor-local repo workspace + fresh cleanup/2d-3d-sync baseline 完成 author/test，再以 exact tested diff delivery。
- AI Library 只在 runtime 有 ChatGPT surface 時作 enrichment；Codex/headless 缺 connector 固定 `NOT_APPLICABLE_NO_AI_LIBRARY_SURFACE`。
- 依 `AGENTS.md` 跑 Preflight；changed files 已知後重新帶 `--changed-file` 驗一次。
- 既有 Skill 修改保留可追溯 baseline snapshot。
- 客觀流程型 Skill 要有 RED-capable contract，再最小修改到 GREEN。
- 驗證只能判定對不對，不能反過來成為 production/domain 規則的計算來源。
- Skill 只能要求目前環境真的具備的能力；缺少可選 surface 時使用可執行替代，不得等待不存在的第三方回報。
- 修改完成後 remote delivery/readback 若已在使用者授權 scope 內，直接完成；不得把同 scope 重複授權當停止點。
## 中文 Skill identity 永久 invariant

對 `.agents/skills/**` 下**資料夾 basename 含中文，且該資料夾包含 `SKILL.md`** 的 Skill：

1. frontmatter `name` **必須與 parent folder basename 完全相同**。
2. H1/title 與使用者可見 canonical 名稱也應使用該中文名稱；英文技術術語可留在 body，但不能繼續冒充 Skill identity。
3. README/router/Registry/其他 Skill 若指向該 Skill，canonical target 必須使用真實中文 path/name。
4. 舊英文 identity 只可留在 migration/history/legacy alias 說明，不可作新的 canonical routing target。
5. rename 時同步 frontmatter、README/router、Registry（若有 route）、tests、docs/AI Library、release policy（若需要）。
6. machine guard 固定使用 `tests/test_chinese_skill_identity_contract.py` 自動遞迴掃描；未來新增中文 Skill 也會自動納入，不靠人工清單才發現 mismatch。

此 invariant 是對「既有 Skill 預設保留名稱」的專案級特例：**中文資料夾已是使用者指定的 canonical identity 時，`name` 要跟資料夾走。**

## 專案 Skill 邊界：修改DXF

- 使用者已明確確認：**`修改DXF` 不是 WHD／本專案 Skill**。
- 不得因工作內容、資料夾名稱或關鍵字含 `DXF`，就把外部／其他專案的 `修改DXF` 能力自動加入 `.agents/skills/skill_registry.json`、WHD README/router、Phase6 Preflight 或 release Skill 清單。
- WHD 目前的 `.agents/skills/engineering/驗證板件與DXF/SKILL.md` 是**驗證／驗收 Skill**；它負責 canonical geometry、2D/3D parity、DXF export→reopen、multipart、Save→Reload 等 QA，**不等於也不取代 `修改DXF`**。
- 若使用者另外點名 `修改DXF`，先定位其真正所屬專案／來源，再依那個來源的規則執行；不能用 WHD `驗證板件與DXF` 冒充。
- machine guard：`tests/test_dxf_skill_scope_contract.py`。

## WHD 標準入口

正式 Skill 撰寫/修改規則：

`.agents/skills/engineering/寫技能/SKILL.md`

機器可讀路由：

`.agents/skills/skill_registry.json`

中文 identity contract：

`tests/test_chinese_skill_identity_contract.py`

DXF Skill scope contract：

`tests/test_dxf_skill_scope_contract.py`

全域踩坑庫：

`個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`

## 常見反模式

- 從 Claude/Cowork 範例直接複製成 WHD 必備流程。
- 說「已派 subagent，等它回來」但實際沒有 subagent runtime。
- 強制一定要 HTML viewer 才能 review，導致沒有 viewer 的環境停工。
- 為既有 Skill 隨意加 `v2`，造成舊引用與新 identity 分裂。
- 中文資料夾叫 `寫成規格書`，frontmatter 卻仍叫 `to-spec`；資料夾與 `name` split identity。
- README/router 還連 `./to-spec/`、`./grilling/` 之類不存在路徑，即使 SKILL.md 本身已改名仍造成 discovery 斷鏈。
- 看到 `DXF` 就把其他專案的 `修改DXF` 當成 WHD Skill，或用 `驗證板件與DXF` 冒充 DXF 編輯能力。
- 使用者明確要求改名，卻被「永遠保留原名」規則擋住。
- 只改 Skill 文字，沒有 contract test / Registry / AI Library durable writeback。
- 看到測試 expected value 就把差值回灌 production。

## 派工技能特別注意

`.agents/skills/engineering/派工/SKILL.md` 是流程型 Skill，**canonical frontmatter identity 固定為 `name: 派工`**；舊 `name: dispatching` 已 superseded，不得再恢復。

修改時至少驗：

- frontmatter `name: 派工` 與目錄 `派工/` 一致；
- PM → Implementer → QA 狀態機；
- owning Issue / AI Library / checkpoint / journal；
- process-group timeout 分類與 resume；
- remote QA monitoring；
- 不虛構背景工程師、不把聊天 runtime 當 scheduler；
- 章節順序與自我檢查不互相矛盾。

## 2026-09-10 中文 Skill 全樹清理

本次以 `.agents/skills/**/SKILL.md` 實體 tree 盤點到 11 個中文 Skill 資料夾；其中 8 個仍保留英文 frontmatter identity。永久修正不是「把那 8 個名字寫死」，而是把上述 basename invariant + 全樹 contract 納入專案，避免未來同類 drift 再發生。

## 找技能：外部 Skill 發現與專案納入邊界

WHD canonical discovery Skill：`.agents/skills/productivity/找技能/SKILL.md`。

- `找技能` 的工作是理解需求、搜尋候選、做品質驗證、呈現候選，並在**使用者明確同意**後才使用實際可用安裝機制。
- `skills.sh`、`npx skills`、web/catalog、安裝器都屬 capability：**有就用，沒有就退化**；不得假裝查過 leaderboard、跑過 CLI、看過 stars/install count 或完成安裝。
- 外部 Skill 的 installs、GitHub stars、來源信譽等是推薦 evidence；來源檔的 1K+/100 installs/100 stars 為 heuristic，不是硬式安全閘門。取不到的資料標 unknown，不腦補。
- **不得自動安裝**外部 Skill。使用者要先看到候選、來源與可驗證品質資訊，再明確選定。
- **不得自動納入 WHD**。外部 Skill 被找到或已裝到個人環境，都不代表它是 `.agents/skills/**` 的 canonical project Skill。
- 若使用者明確要求把外部 Skill 加進 WHD，必須轉 `寫技能`，重新走 `AGENTS.md` / root-local-first / Preflight / Git-phase branch / 中文 identity / contract / Registry / AI Library / release durable writeback。
- 這條邊界同時保護 `修改DXF`：即使 `找技能` 找到外部 DXF 編輯 Skill，也不得因此把它誤掛成 WHD Skill。
- machine guard：`tests/test_find_skill_contract.py`。

## 2026-09-11 第二批：Skill 模板吸收與 MCP 工具操作

使用者核准第二批後，WHD 採以下永久邊界：

### `make-skill-template` 不建立第二套 authoring authority

- 外部 `make-skill-template` 和既有 `寫技能` 高度重疊，因此**不建立** `.agents/skills/**/make-skill-template` 或另一顆「技能模板」Skill。
- 有價值的通用內容直接吸收到 `寫技能`：`compatibility`、`metadata`、`allowed-tools` 等選用 frontmatter 的使用邊界，以及 `templates/` 為可編輯 scaffold、`assets/` 為 as-is 資產的分工。
- 外部模板的 lowercase-hyphen naming 規則不得覆蓋 WHD 中文 canonical identity。
- `allowed-tools` 只能描述 host/spec 真支援的 tool surface，不能把「列在 frontmatter」誤當成已取得權限或已安裝工具。

### `MCP工具操作` 是 canonical MCP Skill

WHD canonical path：`.agents/skills/productivity/MCP工具操作/SKILL.md`。

- identity 固定為中文 `MCP工具操作`，frontmatter / folder / H1 / Registry / README 必須一致。
- 上游輸入來源是 `github/awesome-copilot` 的 `mcp-cli` Skill，但 WHD **不把 mcp-cli 當硬相依**。
- 每次先能力偵測：有 runtime 原生 connector / typed tool 就優先使用；只有真的有 `mcp-cli` 時才走 CLI；兩者都沒有就 fail closed。
- 流程固定為 Discover → Explore → Inspect schema → Execute。不得猜 server、tool、schema 或參數。
- 「已發現／已呼叫／已成功／已寫入」必須有本回合實際 tool result 支撐。
- CLI route 保留 `mcp-cli` 的 exit-code contract；原生 connector 則保留自己的 structured error，不硬套 CLI code。
- MCP 是 transport / external capability，不是 domain authority。任何外部 tool result **不自動升格**為 WHD mechanical/manufacturing Source of Truth，也不能繞過 root-local-first、Preflight、`GIT_WRITE_UNLOCKED` 後 Git-phase branch、remote QA 或其他專案 gate。
- machine guard：`tests/test_second_batch_skills_contract.py`。

## 2026-09-11 第三批：Python 測試實務

WHD canonical path：`.agents/skills/engineering/Python測試實務/SKILL.md`。

- identity 固定為中文 `Python測試實務`；folder / frontmatter / H1 / README / Registry 必須一致。
- 此 Skill 是 **pytest 工程實務層**，負責 fixture、`tmp_path` isolation、parameterization、mock/monkeypatch、async、property-based、markers、coverage/CI mechanics；**不取代** `tdd` 的 seam / RED→GREEN authority，也不取代 `diagnosing-bugs` 的 repro / root-cause 流程。
- 測試不得污染 `config.ini`、`基準檔/**` 或其他 tracked source；優先在 `tmp_path` / temporary workspace 操作。需要碰真實 tracked 檔時，必須有 teardown，並以測試前後 hash/SHA 或 `git diff` 證明還原。
- `fixture`、expected value、snapshot、counterexample、tolerance、probe result 都只屬 validation input；它們**不能回灌 production**，也不會因為放進 `conftest.py` 或參數表就升格成 Source of Truth。
- `mock` / `monkeypatch` 只隔離真正外部邊界；不得 mock 掉本輪必須驗的 geometry、DXF export→reopen、Save→Reload、multipart/physical-part、2D/3D parity 等真實 seam。
- parameterization 用來擴大同一 invariant 的 coverage；不得把大量 current output hard-code 成產品規格。
- property-based / fuzz 找到的 counterexample 只能證明 invariant 被破壞，不能直接回灌 production offset / formula。
- `skip` / `xfail` 必須有具體理由；**SKIP 不等於 PASS**。Headless/GUI/Xvfb 結果要分開解讀。
- **focused GREEN 不等於 final acceptance**；專案若另要求 `驗證板件與DXF`、release gate 或其他 final acceptance，仍必須完成。
- coverage 只表示 code path 被執行；不得把外部範例的任意門檻（例如 80%）直接變成 WHD 硬規則。
- machine guard：`tests/test_python_testing_practices_skill_contract.py`。

## 2026-09-11 第四批：性質導向測試與尺寸語意分析

### `性質導向測試`

WHD canonical path：`.agents/skills/engineering/性質導向測試/SKILL.md`。

- 責任是 property / invariant 設計、generator strategy、shrinking 與 counterexample classification；不取代 `Python測試實務` 的 pytest mechanics，也不取代 `tdd` / `diagnosing-bugs`。
- 優先使用有獨立 authority 的 roundtrip、inverse、oracle、idempotence、invariant 等 property，並選擇能真正排除錯誤的最強 property。
- 禁止 tautology 與 vacuity：不要用同一 production formula 重算 expected，也不要靠大量 `assume()` 把有效輸入全部濾掉；constraints 優先編碼進 generator strategy。
- Hypothesis / PBT library 是 capability/dependency；專案未安裝時不得假裝存在，新增 dependency 必須經專案／使用者決策。
- shrunk counterexample 必須先分類成 property 錯、spec ambiguous、strategy 過寬或真 code bug；在 authority 未釐清前不能把 counterexample 寫成 canonical expected。
- property、counterexample、fixture、seed 與 probe 都屬 validation evidence，**不能回灌 production**，也不能建立新的 Source of Truth。

### `尺寸語意分析`

WHD canonical path：`.agents/skills/engineering/尺寸語意分析/SKILL.md`。

- WHD 尺寸除了物理 unit（常見為 mm）還要追 semantic dimension；同為 `29 mm`，`{FW_formed}`、`{material_length}`、`{formed_outside_length}` 仍可能完全不相容。
- canonical vocabulary 至少區分 `{material_length}`、`{formed_outside_length}`、`{FW_formed}`、`{sheet_thickness}`、`{flat_relief_length}`、`{collision_envelope}`、`{datum_offset}`。
- 料尺寸、包外、flat、formed、FW、T/2T、datum offset 與 collision envelope 不可因數字相近就互換；跨語意轉換必須有獨立 conversion authority。
- 此 Skill **只能分析與驗證**。Finding 可以指出 mismatch 或缺少 conversion，但**不能回灌 production**、不能從差值發明 offset / formula、不能把 collision/test result 升格成 Source of Truth。
- upstream `dimensional-analysis` 的固定 `full-auto` / Task-subagent pipeline 不適合作為 WHD 硬依賴。每輪先偵測 capability：有真 subagent/parallel runtime 才可分工；沒有就由**同一執行者**逐階段完成，**不得假裝**派工或等待不存在的 agent。
- machine guard：`tests/test_fourth_batch_skills_contract.py`。

## 2026-09-11 第五批：UI設計與去AI味

WHD canonical path：`.agents/skills/engineering/UI設計與去AI味/SKILL.md`。

- `UI設計與去AI味` 是 WHD 的 UI visual design / information hierarchy / existing-UI de-AI audit 與安全 rewrite authority；它**不取代** product、geometry、manufacturing、Save→Reload、2D/3D、DXF 或 domain semantics authority。
- WHD 是 **Python Tkinter / ttk engineering desktop app**。外部 `frontend-design` 與 `avoid-ai-design` **只作 input / 輸入參考**，不得把 React / Tailwind / shadcn、Web hero 或 mobile-first 假設變成 WHD hard dependency，也不建立第二套 canonical UI Skill。

- `UI UX Pro Max` 納入同一 canonical `UI設計與去AI味` 的外部 design-intelligence route；來源固定記錄 `nextlevelbuilder/ui-ux-pro-max-skill@15de38fb70bc80ae9276fa7703b48ae861a672e6`，**不建立第二顆 CURRENT UI Skill**。
- UI UX Pro Max 必須先做 runtime capability check：可用時 New Design 可先查 `--design-system`、局部問題查明確 `--domain`；WHD 為 Tkinter/ttk 且 upstream 沒有 Tkinter stack，禁止假造 `--stack tkinter` 或硬套 Web/mobile stack。不可用時走 canonical Skill 的 **inline fallback**，標示 `UI UX Pro Max runtime unavailable`，不得假裝 query 已執行。
- 固定順序：`WHD functional/domain contract → UI UX Pro Max design intelligence (if available) → UI設計與去AI味 filtering → TDD / implementation → Tk/Xvfb functional + layout regression → real visual acceptance`。外部 palette / spacing / typography / design-system output 只屬 recommendation/input，不得覆蓋 WHD product、geometry、manufacturing、Save→Reload、2D/3D 或 DXF authority；預設也不得用 `--persist` 另建第二套設計 SoT。

- 核心順序是 **functionality > aesthetics**。`visual simplification` 不得變成 `semantic simplification`；callback、selection/project state、editable/readonly、Save→Reload、2D/3D、manufacturing、geometry authority、keyboard/accessibility/scroll 都必須保留。
- 正式 Rewrite 禁止暴力**全域** style / presentation Search/Replace；採**逐元件**施工，最小施工單位是可獨立驗證的 widget / panel / dialog / toolbar / sidebar / workspace region，固定走「讀元件 → 功能 contract → 修改單一區域 → render/inspect（若有）→ functional check → layout regression → 才進下一區域」。
- 去 AI 味不是灰階化。既有有語意的 Brand / **Action Color**、selection、active、warning、error、success、focus 必須保留其角色，不能因 anti-AI cleanup 全部拔色。
- `monospace` 只用在有理由的尺寸、座標、數值表格、ID 等資料區；每次都檢查 `width`、clipping、換行、DPI、dialog/table/control layout，避免工程感字型把畫面撐破。
- `shadow` / border / gradient / round corner / **elevation** 本身不是 AI 味；Modal / Dropdown / Toast 等 foreground surface 必須保留足夠深度。若移除 gradient/glow/blur/heavy shadow，必須用 restrained border / 1px divider / surface tone / spacing / alignment 等補回 hierarchy。
- 現行 text scale 是小 `1.0`、中 `1.2`、大 `1.4`；三種都必須維持 required controls 可見或可 scroll 到，不能只在小字正常。
- 有真 GUI / screenshot / Xvfb 才能宣告 visual acceptance；沒有 visual runtime 時只能標 `inferred` / `visual acceptance pending`，**不得假裝**看過畫面或已完成視覺驗收。
- Audit mode 是 read-only；already-good UI 可以 `keep / 不修改`。成功不是改得多，而是只修改有產品、層級或操作理由的地方。
- machine guard：`tests/test_ui_design_de_ai_skill_contract.py`。

## 2026-09-30 — Flow v2 多 AI 單一 writer / durable progress CURRENT 規則

<!-- FLOW_V2_MULTI_AI_SINGLE_WRITER_CURRENT_V1 -->

GitHub owning Issue、assignee、comment、label、舊 shared claim 都不提供 CURRENT 施工權。唯一 execution authority 是 `coord/execution-v2` 的 native `WHD_EXECUTION_RECORD_V2`。

- **ONE ISSUE / ONE MUTATION WRITER**：substantive repository work 必須持有 exact Issue 的 live lease 與 ACTIVE `mutation_scope`。新 READY work 用 atomic `ACQUIRE.effect.admission_reservation` 一次取得；不得主動拆成 `ACQUIRE → RESERVE_PATHS`。
- **STALE PLAN MUST DIE**：每次 interactive Git mutation 綁 `issue + generation + record_fingerprint + lease_token + invocation_identity + next_action + work/target HEAD`。任一 identity 已前進，舊 plan 永久失效並從最新 structured `next_action` replan。
- **Durable progress owner**：state / branch / HEAD / QA / next_action / blocker / closure 全部由 ExecutionRecord 表達；`coord/monitor-v2` 只做 NON_AUTHORITY observation。
- **Scope expansion**：只可對既有 ACTIVE scope 走 monotonic `RESERVE_PATHS`；不得先改新檔再補 reservation。
- **Terminal**：唯一正常完成是 durable DONE tuple（Issue closed、lease/owner cleared、reservation RELEASED）；merge/QA GREEN 本身不是完成。
- **Legacy history**：`execution_claim_guard.py`、Remote Guard、claim/checkpoint coordination 只可作 migration/audit historical evidence，不得作 CURRENT execution/write authority。

## 2026-09-13 — Canonical Authority Roles / Mirror Contract

<!-- ISSUE173_CANONICAL_AUTHORITY_ROLE_CONTRACT -->

WHD 的文件、AI Library、Skill、handoff 或相容入口只要描述同一個 domain contract，就必須先分類成下列角色；完整 mapping 由 `個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md` 擁有：

- `CURRENT`：該 contract 唯一可作現行 Source of Truth 的 owner。
- `REFERENCE`：背景／方法／evidence；可輔助，但不得覆蓋 CURRENT。
- `MIRROR`：預設只作入口相容或導覽，必須指回 canonical owner。純 pointer mirror 必須標記 `POINTER_ONLY`；若檔內明確含 `FLOW_V2_EXECUTION_BRIDGE_V1`，可保留**狹窄的入口專屬 routing / projection / user-visible contract**，但不得定義第二套 execution state、lease、mutation transaction、QA acceptance、merge、finalization 或 closure state machine，且所有這些語意必須明確 defer 到 canonical `flow-v2-execution`。
- `HISTORICAL`：日期化／已被取代的 evidence；不得參與 current routing，也不得繼續使用「CURRENT／最高優先級／下一個主要任務」等現行語氣。

### 單一 CURRENT 硬規則

- **同一 contract 只能有一個 `CURRENT` owner。** 兩份文件即使內容暫時相同，只要都自稱 current/最高優先級，就屬 authority conflict。
- 搬移或升格 canonical owner 時，舊 owner 必須在**同一變更**降級為 `REFERENCE`、`MIRROR` 或 `HISTORICAL`；禁止先留下雙 CURRENT 再靠閱讀順序猜哪份新。
- 保留舊路徑時優先採 `MIRROR + POINTER_ONLY`；只有 `FLOW_V2_EXECUTION_BRIDGE_V1` 可使用 narrow bridge 例外。Bridge 只能擁有入口專屬 routing/projection，不得複製 canonical state machine；全文 copy 仍視為第二 SSOT。
- 發現 exact duplicate 但檔名／語意角色不同時，先決定真正 owner；非 owner 要刪除、改 pointer 或明確 historical，不能讓 duplicate SHA 掩蓋 identity 衝突。
- 新規則推翻舊規則時，舊規則在原位置標 `SUPERSEDED / REVOKED / HISTORICAL`，不得只在另一份文件後面補一段新說法。

### 永久驗證

`tests/knowledge/test_knowledge_authority_contract.py` 是 T1 起始的 machine guard；它只判定 authority contract 是否符合，不成為任何製造／幾何／產品規則的 Source of Truth。


## Domain route 必須包含 domain authority

- Phase6 Knowledge Preflight 的 domain route 必須在 `required_references` 直接列出該 domain 的 **current canonical authority**；全域踩坑庫或通用 Skill-authoring 規則只能補充，不能代替 domain Source of Truth。
- dimension semantics route 至少必須載入 canonical `07_Phase6尺寸語意與標準截角母規則.md`。
- DM7 / Corner Data / physical-part navigation route 必須載入 current navigation rule 與 `dm7_part_navigation_pitfalls.md`；stale child identity 不得靠 generic Skill policy 決定。
- manufacturing / DXF acceptance route 必須載入 current `04_WHD鈑金展開幾何引擎規範.md`。
- 缺少 domain authority evidence 時 Preflight 必須 fail closed；不能因 `08_WHD技能建立與修改規則.md` 或全域 06 已讀就 false GREEN。
- 每個 domain route 都要有 regression，至少證明「缺 domain evidence → RED；補齊 → GREEN」，並保留既有 domain reference 不被後續 Registry 編輯移除。


## Active Skill runtime capability contract

- Active WHD Skill 由 `.agents/skills/skill_catalog.json` classification 決定；filesystem 只證明 inventory，只有 `canonical` 預設可作 current active routing owner。
- Active Skill 在要求 background agent、subagent、browser、CLI、MCP、專用 Skill loader 或其他 runtime 能力前必須先 capability-check；能力不存在時使用 safe **inline fallback**，不得假裝已委派或已執行。
- Active Skill 引用任何 project-local **supporting file**、template、tracker doc 或 script 前必須確認它真的存在；不存在時移除硬依賴、改成 self-contained 流程，或明確 fail closed。
- Skill-to-Skill routing 必須使用 current **canonical identity**；retired/legacy identity 只能存在於 history/migration，不得作 active invocation target。
- `reference`、`upstream-beta`、`tool-specific`、`retired` 可在明確情境讀取，但不得和 canonical owner 競爭 routing。
- Runtime repair 不得為了讓測試通過而把不存在能力包裝成假工具；驗證只判定契約，不能反過來創造 capability。
- Permanent guard：`tests/knowledge/test_active_skill_runtime_contract.py`。

### CI_SHARDING_SKILL_OWNERSHIP_V1
CI sharding 的 pytest isolation / deterministic ownership / concurrency budget / timing / tested-vs-orchestration identity 規則由 `Python測試實務` 擁有；remote polling 入口由 `monitoring-remote-qa` bridge 回 Flow v2 `active_run / POLL_QA / ACCEPT_QA|FAIL_QA`，runtime resume/turn-exit 也只服從 Flow v2 ExecutionRecord + `execution_invocation_exit.py`；`executable-continuity-controller` 只保留相容入口/歷史 reference。長 log classifier 語意由 `long-log-context-safe-execution` 擁有。不得再建立第二套 competing execution authority。

<!-- ISSUE702_MUTATING_TOOLCALL_CRASH_RECOVERY_WRITEBACK_V1 -->
## Mutating toolcall crash-recovery canonical invariant

- Mutating work must persist an operation identity before the side effect and recover from durable readback before any ordinary next action after re-entry.
- Canonical crash boundaries are: `prepare → authorize → post-effect → readback → pre-reconcile → post-reconcile`.
- `EFFECT_OBSERVED` means the requested effect is already proven by exact durable/live evidence: **do not replay the mutation**; reconcile the operation and continue from the reconciled state.
- `AMBIGUOUS` means identity/effect cannot be proven: fail closed and repair evidence/authority; never guess whether a mutation happened.
- **HISTORICAL mapping only**：#702 當時的 `tools/continuity_controller.py`、`tools/execution_claim_guard.py`、`tools/claim_activation_recovery.py` 與 legacy scheduler reconciliation 只保留 crash-boundary / migration evidence，不再是 CURRENT semantic owners。
- CURRENT generic mutation continuity、readback/reconcile、owner transfer、scheduler resume 與 closure 全部由 `WHD_EXECUTION_RECORD_V2` + `tools/control_transaction.py` + structured `next_action` + `tools/execution_invocation_exit.py` 單一擁有；Entry Skills/prompts只能 bridge，不得把 historical owner重新升格。
- Amendment-wide fault matrix authority is `docs/governance/issue702_crash_fault_injection_matrix.json`; accepted provenance/readback is recorded separately in `docs/governance/issue702_combined_acceptance_writeback_manifest.json`.



---

## 已核准規格拆工單 fast path — CURRENT

當使用者已完成規格確認，接著要求「拆工單／拆票／拆成工單」時，`拆解任務工單` 必須直接走 `APPROVED_REQUIREMENT_FAST_PATH`：approved spec → requirement-to-ticket traceability → machine closure-owner validation → blockers-first owning Issues。

- 不得重新要求 requirement-level RED。
- 不得因 implementation test 尚未建立就把產品需求降回未核准。
- 不得再插入第二次人工 breakdown approval gate。
- Acceptance tests 屬施工/驗收條件，不是產品需求重新核准 gate。
- 只有規格仍有真實矛盾、互斥方案或 unresolved product authority 時，才走 `REQUIREMENT_DISCOVERY_PATH`，使用 executable RED 協助釐清；需求一經核准立即回 approved fast path。
- GitHub-backed project 仍需 real owning Issues、單一 `Issue Closure owner`、dependency readback 與 closing ownership；本修正不弱化 machine closure-owner gate。

此條 supersede 舊「所有拆票一律先 requirement RED + 第二次核准」流程。
