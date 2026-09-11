# WHD 技能建立與修改規則

> 目的：讓所有後續 AI 在建立或修改 `.agents/skills/**` 時，不再把特定模型、特定 CLI、背景 Subagent、viewer 或 TodoList 當成普遍存在的能力，並維持 Skill 資料夾、frontmatter、路由與引用的一致 identity。

## Authority

1. 使用者本輪明確核准規格最高。
2. `AGENTS.md`、Phase6 Knowledge Preflight、WHD 專案 Skill/Registry/AI Library/Source of Truth 次之。
3. 通用 skill-writing 慣例只能補充，不能繞過 WHD gate。

## 必守規則

- 修改 Skill 前先反讀 target HEAD，依 WHD `branch-first` 建新 branch；不得直接改 `cleanup/2d-3d-sync` / `main`。
- 依 `AGENTS.md` 跑 Preflight；changed files 已知後重新帶 `--changed-file` 驗一次。
- 既有 Skill 修改先保留可追溯 baseline snapshot（原始 SHA/commit/ref/內容）。
- 客觀流程型 Skill 要有 RED-capable contract，再最小修改到 GREEN。
- **驗證只能判定對不對，不能反過來成為 production / domain 規則的計算來源。**
- Skill 只能要求目前環境真的具備的能力；沒有背景 Subagent / viewer / package / CI 時要退化成可執行替代方案，**不得假裝工具存在，也不得等待不存在的第三方回報**。
- reviewer/viewer 是可選 review surface，不是完成 Skill 的唯一途徑。
- 若使用者明確要求改 Skill 名稱，使用者指示優先；要同步 frontmatter、目錄/路徑（如需要）、Registry、tests、docs 與其他引用。沒有明確要求則預設保留原名。
- 使用者指出可重複錯誤後，主動同步直接相關 Skill、AI Library/踩坑規則與 Registry，不再等使用者逐次提醒。
- 修改完成後一定遠端 re-read，不能只相信 write API 回傳。

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
- 若使用者明確要求把外部 Skill 加進 WHD，必須轉 `寫技能`，重新走 `AGENTS.md` / Preflight / branch-first / 中文 identity / contract / Registry / AI Library / release durable writeback。
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
- MCP 是 transport / external capability，不是 domain authority。任何外部 tool result **不自動升格**為 WHD mechanical/manufacturing Source of Truth，也不能繞過 branch-first、Preflight、remote QA 或其他專案 gate。
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
- 核心順序是 **functionality > aesthetics**。`visual simplification` 不得變成 `semantic simplification`；callback、selection/project state、editable/readonly、Save→Reload、2D/3D、manufacturing、geometry authority、keyboard/accessibility/scroll 都必須保留。
- 正式 Rewrite 禁止暴力**全域** style / presentation Search/Replace；採**逐元件**施工，最小施工單位是可獨立驗證的 widget / panel / dialog / toolbar / sidebar / workspace region，固定走「讀元件 → 功能 contract → 修改單一區域 → render/inspect（若有）→ functional check → layout regression → 才進下一區域」。
- 去 AI 味不是灰階化。既有有語意的 Brand / **Action Color**、selection、active、warning、error、success、focus 必須保留其角色，不能因 anti-AI cleanup 全部拔色。
- `monospace` 只用在有理由的尺寸、座標、數值表格、ID 等資料區；每次都檢查 `width`、clipping、換行、DPI、dialog/table/control layout，避免工程感字型把畫面撐破。
- `shadow` / border / gradient / round corner / **elevation** 本身不是 AI 味；Modal / Dropdown / Toast 等 foreground surface 必須保留足夠深度。若移除 gradient/glow/blur/heavy shadow，必須用 restrained border / 1px divider / surface tone / spacing / alignment 等補回 hierarchy。
- 現行 text scale 是小 `1.0`、中 `1.2`、大 `1.4`；三種都必須維持 required controls 可見或可 scroll 到，不能只在小字正常。
- 有真 GUI / screenshot / Xvfb 才能宣告 visual acceptance；沒有 visual runtime 時只能標 `inferred` / `visual acceptance pending`，**不得假裝**看過畫面或已完成視覺驗收。
- Audit mode 是 read-only；already-good UI 可以 `keep / 不修改`。成功不是改得多，而是只修改有產品、層級或操作理由的地方。
- machine guard：`tests/test_ui_design_de_ai_skill_contract.py`。
