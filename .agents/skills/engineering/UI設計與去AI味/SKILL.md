---
name: UI設計與去AI味
description: 當工作要新增、重整或審查 WHD UI，尤其使用者要求 UI 設計、介面重整、去 AI 味、AI slop audit、視覺層級、layout、typography 或「像真正工程軟體」時使用；只負責 presentation / hierarchy / interaction presentation，不取代產品、幾何、製造與資料 authority。
whd_doc_role: CURRENT
whd_contract: ui-design-de-ai
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# UI設計與去AI味

把這個 Skill 當成 **WHD UI 視覺設計與安全重構契約**，不是「套一個比較漂亮的模板」。WHD 是 **Python Tkinter / ttk 桌面工程應用程式**，不是 SaaS landing page，也不得把 React / Tailwind / shadcn 當成硬相依或預設實作環境。

核心目標是：**replace defaults with deliberate decisions**。去 AI 味代表每個視覺選擇都要有產品、資訊層級或操作理由，不是把一種 AI 預設換成另一種預設。

## 1. Authority 與來源邊界

Authority 依序是：

1. 使用者本輪明確指示與已核准規格。
2. WHD `AGENTS.md`、Phase6 Preflight、project Skills / Registry / AI Library / Source of Truth。
3. 現有 UI behavior contract 與已核准 design tokens / brand rules（若存在）。
4. 外部 UI Skill 的通用設計方法。

外部來源只作輸入參考，不建立第二套 canonical UI authority：

- `anthropics/skills@34040c9c568585f6929bedeaad110ad08f079624` 的 `skills/frontend-design/SKILL.md`：吸收 subject-specific、intentional typography/layout、anti-template defaults、self-critique。
- `funboy322/avoid-ai-design@8337060636a8cf12e32e883eb367becd702aa526` 的 `SKILL.md`：吸收 Audit / Rewrite、severity、render-if-available、preserve behavior、re-audit。
- `nextlevelbuilder/ui-ux-pro-max-skill@15de38fb70bc80ae9276fa7703b48ae861a672e6` 的 `.claude/skills/ui-ux-pro-max/SKILL.md`：吸收 searchable design intelligence、design-system/domain query contract、accessibility / interaction / typography / layout prioritization 與 desktop-aware guidance。

以上外部來源**只作輸入**，WHD 不建立第二套 canonical `frontend-design` / `avoid-ai-design` / `ui-ux-pro-max` Skill；Web-specific class、framework、hero、mobile-first 假設不能覆蓋 Tkinter/ttk 與 WHD 工程操作需求。


### 1.1 UI UX Pro Max capability route

`UI UX Pro Max` / `ui-ux-pro-max` 是本 Skill 的**外部設計 intelligence 輸入**，不是新的 WHD CURRENT owner。canonical upstream 固定記錄為 `nextlevelbuilder/ui-ux-pro-max-skill@15de38fb70bc80ae9276fa7703b48ae861a672e6`；更新 upstream revision 必須另走 Skill 修改、contract 與 review，不可默默追 latest。

每次 UI/UX 任務先做 **runtime capability check**：

1. 若目前 runtime 真的已安裝且可呼叫 UI UX Pro Max，先依任務使用最小查詢：New Design / 系統級方向用 `--design-system`；單一 UI 問題用明確 `--domain`；stack guidance 只在專案真的偵測到 upstream 支援的 stack 時使用。
2. WHD 是 Tkinter/ttk desktop app，而 upstream 目前沒有 Tkinter stack；**不得假造 `--stack tkinter`**，也不得硬套 React / Tailwind / mobile-first / touch / GSAP / Web performance 建議。優先吸收與 WHD 相容的 accessibility、keyboard/focus、layout、spacing、typography、information density、forms/feedback 與 interaction hierarchy。
3. 查詢結果只作 recommendation。先由本 Skill 與 WHD product/domain contract 過濾再施工；不得把外部搜尋結果、palette、spacing、font、fixture 或 design-system 輸出升格成 WHD product / geometry / manufacturing / persistence authority。
4. 預設不使用 upstream `--persist` 建立第二套 design-system Source of Truth；只有使用者／WHD 明確要求且 branch-first scope 已納入時才可落盤，並標為 reference/input。
5. 若 runtime 沒有 UI UX Pro Max、search script 或相依能力，使用本 Skill 已固化規則做 **inline fallback**，並明確標記 `UI UX Pro Max runtime unavailable`；**不得假裝**已執行 upstream query、不得等待不存在的工具。
6. 不把 private project data、未公開檔案內容或機密值塞進外部 query。

固定執行順序：

```text
WHD functional/domain contract
→ UI UX Pro Max design intelligence (if runtime available)
→ UI設計與去AI味 filtering
→ TDD / implementation
→ Tk/Xvfb functional + layout regression
→ visual acceptance（只有真 GUI / screenshot / Xvfb evidence 才可宣告）
```


## 2. 責任邊界

本 Skill 負責：

- visual hierarchy；
- layout / spacing / alignment；
- typography 與資訊密度；
- surface / elevation / foreground-background 層級；
- control grouping 與 primary / secondary action 視覺層級；
- existing UI 的 AI-tell audit；
- 在保留功能前提下的 presentation rewrite；
- 新 UI 的視覺與資訊架構設計。

本 Skill**不負責**重新定義：

- product workflow；
- geometry authority；
- manufacturing 公式或輸出；
- FW / T / W / H / D 等 domain semantics；
- Save→Reload schema；
- 2D/3D authoritative state；
- DXF authority；
- 板件 topology / identity。

**visual simplification ≠ semantic simplification**。畫面可以更清楚，但不能因為看起來乾淨就改變產品語意。

## 3. 三種工作模式

### 3.1 Audit mode — 只檢查，不修改

使用者說「先掃」「先 audit」「哪裡有 AI 味」「不要改」時進入 **Audit**。

Audit mode：

- 先讀實際 UI code；
- 有 render/screenshot/Xvfb 能力才看 pixels；
- 將 finding 分成 code-certain / visual-certain / `inferred`；
- 可用 P0 / P1 / P2 表示優先級；
- 每個 finding 標示 `keep / fix / judgment call`；
- **不得改 code、不得寫 presentation 變更**。

已經有清楚產品理由、hierarchy、interaction 或品牌理由的元素，正確結果可以是「保留」。不為了完成 audit 而製造問題。

### 3.2 Rewrite mode — 既有 UI 安全重構

**Rewrite** 適用於功能已存在、使用者要求介面重整或去 AI 味的情境。

最小施工單位固定為可獨立驗證的：

- `widget`
- `panel`
- `dialog`
- `toolbar`
- `sidebar`
- `workspace region`

正式 Rewrite **禁止暴力全域 Search/Replace**，也不得以全域樣式取代作為主要重構策略。不得一次把整份 `gui.py` 的 shadow、border、background、padding、font、relief 或 color 清洗掉。

一次只改一個可驗證 region；通過後才進下一個 region。

### 3.3 New Design mode — 新 UI 先定資訊再定外觀

**New Design** 適用於新增 workspace、dialog、panel 或操作區。

順序固定：

```text
確認功能與資訊
→ 確認操作順序
→ 定 design direction
→ 定 hierarchy / density
→ 定 layout
→ implementation
→ render/inspect（若能力存在）
→ functional validation
```

禁止先產生漂亮 widget 再把功能硬塞進去。

## 4. Rewrite 前先建立功能 contract

修改任何既有 region 前，先**讀目前元件**並記錄該區域的**功能 contract**。至少確認：

- `callback`
- `selection state`
- `project state`
- `Save→Reload`
- `2D/3D` parity / state projection
- `manufacturing` inputs / observable outputs
- `geometry authority`
- `editable` / `readonly` 狀態
- `keyboard` interaction
- `accessibility`
- `scroll` reachability

UI 美化不得偷偷改以上行為。尤其不能為了「資料一致」把原本可直接輸入的欄位改成 readonly，也不能用 redraw/refresh 偷改 control ownership。

## 5. 逐元件施工 loop

每個 region 固定走：

```text
讀目前元件
→ 確認功能 contract
→ 確認視覺角色
→ 修改單一區域
→ render / inspect（若可用）
→ functional check
→ layout regression check
→ 通過後才進下一區域
```

這是硬性施工粒度，不是建議。若一次修改跨多個 region，必須能分別說明與驗證每一區；不可用「整頁看起來比較一致」取代逐區驗證。

## 6. Render / screenshot 能力要先偵測

設計是視覺工作，但工具能力不是永遠存在。

- 有真 GUI、Xvfb、screenshot、preview 或等價 runtime：使用 pixels + source 做 review。
- 沒有 visual runtime：仍可做 source-level audit，但視覺 finding 標 `inferred`，完成狀態只能寫 **`visual acceptance pending`**。
- **不得假裝**已看過畫面、已做 screenshot review 或已完成 visual acceptance。

有就用，沒有就退化，但不得假裝。

## 7. WHD 的設計方向：工程工作台，不是行銷頁

WHD UI 優先順序：

1. 操作正確性
2. 資訊層級
3. 可掃描性
4. 操作效率
5. 資訊密度
6. 視覺一致性
7. 品牌辨識
8. 裝飾

WHD 允許高資訊密度。不要把「乾淨」誤解成大量留白；dashboard / CAD / manufacturing workspace 應優先 **density + legibility + hierarchy**。

每次設計先定一個方向：density stance、typography stance、spacing rhythm、surface hierarchy、control hierarchy、color roles、elevation roles，以及最多一個值得記住的 signature characteristic。不要同時堆數種風格。

## 8. AI-tell audit：看理由，不看黑名單

優先檢查：

- 每個區塊都被包成相同 rounded card；
- 每個 surface 都相同 shadow / border / radius；
- 無理由 gradient / glow / blur；
- icon-in-box everywhere；
- 所有 control 視覺重量相同；
- primary / secondary action 不分；
- 過多 section label / eyebrow；
- spacing 沒有節奏；
- 過度留白；
- 為「工程感」把所有文字換 monospace；
- 去 AI 後全部灰階、黑白灰；
- Modal / Dropdown / Toast 和背景同一層；
- 每個互動都塞無理由 animation；
- 只是把一套 cliché 換成另一套 cliché。

以上都不是機械 blacklist。單一 gradient、shadow、round corner、border、monospace 或品牌色只要有清楚理由就可以保留。

## 9. Brand Color / Action Color 不得被去 AI 味拔掉

去 AI 味不等於灰階化。

已存在且有 semantic role 的 **Brand Color / 品牌色**、**Action Color**、selection、active、warning、error、success、focus 顏色必須保留其角色；若要調整，只能在不破壞語意的前提下改善一致性或可讀性。

禁止因為「AI 常用藍色」就移除藍色，也禁止為了極簡把全部 UI 變成死板黑白灰。

Color 的原則是：少量、穩定、有角色，不當裝飾。

## 10. Monospace 不是工程感濾鏡

`monospace` / tabular treatment 只用在真的需要對齊的尺寸、座標、數值表格、ID、工程碼等資料區。

一般 label、menu、button、說明文字優先使用可讀的 UI font。

任何 monospace 變更前後都要做 layout regression，至少檢查：

- control / column `width`
- `clipping`
- 文字`換行`
- alignment
- DPI / scale
- dialog size

不得為了數據對齊，反而把表格撐破或把操作按鈕擠出畫面。

## 11. 深度不是 AI 味；移除裝飾後要補回 hierarchy

`shadow`、`border`、color、gradient、round corner、separator、elevation **不是 AI 味本身，也不是一律禁止**。判斷標準是它是否有 semantic / interaction / hierarchy 理由。

例如：

- 普通 panel 的無理由重 shadow 可以降低；
- **Modal / Dropdown / Toast** 等 foreground surface 應保留足夠 **elevation**；
- primary action 可保留 Action Color；
- group boundary 可使用 restrained border / `1px` divider / surface tone / spacing。

移除 `gradient`、`glow`、`blur`、heavy `shadow` 後，必須重新確認 foreground/background 與 group **hierarchy**。不得留下白茫茫或黑乎乎的一整片；用最少但足夠的 border、divider、surface tone、alignment、spacing 或 elevation 補回資訊層級。

## 12. Text scale / scroll 是正式 layout contract

WHD 現有 text scale：

- 小：`1.0`
- 中：`1.2`
- 大：`1.4`

任何 Rewrite / New Design 至少檢查小、中、大三種：

- label 不 clipping；
- input/control 不互相覆蓋；
- required controls 仍可見或可 `scroll` 到；
- dialog 的主要按鈕不被擠掉；
- window resize 後仍可操作；
- monospace 數據區不因 scale 撐破欄寬。

只在「小」字型正常，不算 layout acceptance。

## 13. Surgical vs Structural

### Surgical

適合單一 setting group、button group、selector、dialog、toolbar。保留 interaction 結構，優先修 hierarchy、spacing、alignment、冗餘 chrome、button weighting。

### Structural

只有當整個 workspace 的 grouping / canvas-control split / scroll structure 本身妨礙使用時才採用。即使 Structural，也不能改 business behavior、domain semantics 或 manufacturing authority。

禁止把「去 AI 味」當成整份 `gui.py` 重建許可。

## 14. Re-audit

Rewrite 後重新檢查：

1. 是否仍有明顯 P0/P1 AI tell？
2. design direction 是否 coherent？
3. 是否只是換另一套模板？
4. Action Color / Brand Color 是否仍保有 semantic role？
5. Modal / Dropdown / Toast foreground depth 是否清楚？
6. decoration 移除後 hierarchy 是否還在？
7. monospace 是否造成 width / clipping / 換行 regression？
8. 小 / 中 / 大與 scroll 是否可用？
9. callback / state / Save→Reload / 2D/3D / manufacturing 是否未漂移？

已經夠好時允許「不改」。修改量不是品質指標。

## 15. 驗證與完成條件

若只是 presentation rewrite：

- relevant functional tests 必須 PASS；
- config / tracked-file invariants 依專案規則保持；
- 有 visual runtime 才能宣告 visual acceptance；
- 沒有 visual runtime 時明示 `source-level UI review completed; visual acceptance pending`；
- 需要 final project gate 時，focused GREEN 不能冒充 final acceptance。

主觀 UI 品質以 qualitative review 為主，不硬湊沒有 authority 的 numeric aesthetic score。Machine contract 用來鎖 identity、流程、防呆與責任邊界，不把「美不美」變成關鍵字計分。

## 16. Fail-closed

下列任一成立都不得宣告 UI redesign 完成：

- 不知道目前元件的功能 contract；
- 用全域 Search/Replace 當主要重構方式；
- 為了視覺簡化改了 domain / manufacturing / geometry authority；
- 把 editable 改 readonly 但沒有產品 authority；
- 無 visual runtime 卻宣稱畫面已驗收；
- 文字 scale / scroll 尚未驗；
- Modal / Dropdown / Toast 被 flatten 到和背景難以區分；
- 把品牌或 Action Color 無理由拔掉；
- monospace 導致 width / clipping / 換行問題仍未處理。

## Acceptance invariant manifest 防假紅

### INVARIANT_MANIFEST_CANONICAL_PATH_HASH

做 UI / visual acceptance 的 `config.ini`、`基準檔` 或其他 protected invariant 比對時，manifest 必須使用穩定的 **canonical path + SHA256**，或直接 diff canonical manifest 內容。禁止把 `sha256sum snapshot.before` 與 `sha256sum snapshot.after` 的 raw output 直接互比，因為 `sha256sum` output 會包含 transient snapshot 檔名；即使內容完全一致，也可能只因 `.before` / `.after` 名稱不同而假紅。若必須再雜湊 manifest，只比較 normalized hash value，不比較含 transient filename 的整行。QA harness false failure 必須先分類，不得冒充 production regression。


## #160/#163 展開工作區 ownership 與 viewport 邊界（2026-09-13）

<!-- ISSUE164_UNFOLD_WORKSPACE_OWNERSHIP -->
- 展開工作區上方只保留 `檔案` 與 `截角資料庫`。
- 左側整欄只負責板件選擇與目前板件輸入；整欄使用單一垂直 scroll owner。內容超高時必須可捲動，並在文字倍率 `1.0 / 1.2 / 1.4` 都能到達最底控制。
- 其他全域設定、3D 顯示、還原／transaction、全螢幕等控制放到右側控制區；搬移 widget 不得改 callback、state owner、Save→Reload、physical-part identity 或 manufacturing authority。
- Corner Data 進出 lifecycle 必須對稱；family / part switch 只有在 topology/state commit 完成後才 refresh，不得因 layout redraw 建立第二套狀態。

<!-- ISSUE164_VIEWPORT_PRESENTATION_ONLY -->
- 展開 canvas 的黑底、initial fit 與 `zoom / fit / pan` 全屬 presentation。
- 顯示 transform 只能讀 authoritative `PartRenderData` 與目前 physical part/material；不得修改 `PartRenderData`、`part_key`、`material WKB`、Save→Reload payload 或 DXF。
- fit ratio、像素 bbox、截圖與 viewport 量測只可作 validation evidence；不得回灌 manufacturing geometry。

## #186 critical operator control 的 real-GUI 驗收（2026-09-13）

<!-- ISSUE186_CRITICAL_CONTROL_VISIBILITY -->
- UI rehost / layout rewrite 的 structural contract（parent/container 存在、widget 已建立）**不等於** operator control 真正可用。對 Structure Tree、板件 selector、主要 action 等 critical control，驗收必須在可用 visual runtime 下直接驗 `mapped/viewable`、viewport overlap / reachability、interaction，以及 resize / scroll 後仍可操作。
- 文字倍率 `1.0 / 1.2 / 1.4` 都屬正式 contract；不得只驗初始大視窗或小字級。若 control 是固定導覽面、下方 inputs 需要 scroll，必須明確驗證捲到底時 critical control 不會一起消失。
- 修 layout regression 時優先保留既有 single authoritative selector / callback / stable identity；不得用新增第二顆 selector 掩蓋 mounting / scroll-owner 根因。
- 若較新的 accepted layout contract 已 rehost controls，舊測試仍硬鎖舊 parent/row ownership，該測試屬 superseded authority。必須先依 current accepted contract 分類並更新 stale assertion；**不得為了讓舊測試 GREEN 把 production UI 搬回舊 layout**。
- QA harness 的 FAIL 必須區分 production regression、stale/superseded test contract 與 harness false failure；只有 production regression 才能驅動 production fix。

## #187：3D Output rehost 的操作面契約

<!-- ISSUE187_3D_OUTPUT_REHOST_CONTRACT -->

把既有功能搬到 3D primary workspace 時，**rehost widget 不等於重建 state**：

- 若 application 已有正式 state owner / callback（例如既有 `BooleanVar`、SettingsService、export action），新 3D control 直接綁定該 owner；不得為了畫面方便建立第二份 presentation-owned state。
- `輸出` 這類 shop-floor critical controls，驗收不能只證明 Frame / container 被建立；必須在真 Tk/Xvfb 證明 control **mapped、reachable、interactive**。
- WHD current primary workspace 的 top command row 維持真正頂層命令；DXF/STOCK 等 output controls 放在正式 operator/workspace control region，不因搬家重新塞回 top toolbar。
- 對小／中／大 `1.0 / 1.2 / 1.4` 都要驗 control 仍可見或可到達，且 primary action 不 clipping、不被其他 surface 蓋住。
- UI refresh / presence projection 只能刷新 presentation；不得藉 redraw、reload 或 presence sync 偷改另一個獨立的 operator intention。

## #188：shared dark theme 的 runtime 契約（2026-09-13）

<!-- ISSUE188_SHARED_DARK_THEME_RUNTIME -->
- 暗色化只允許一個 `single shared WHD theme token/style provider`；2D/3D/Settings/Matplotlib 只能 consume 同一份角色 token，**不得複製第二套 raw palette truth**。
- 本契約是 presentation-only；不得因 theme apply / refresh 修改 geometry、manufacturing、DXF、Save→Reload 或 workspace state。
- `ttk.Style` 不會自動覆蓋 classic `tk.Menu`；Menu 必須獨立套用 `normal / active / disabled` 的 foreground/background，並保留 foreground-surface 的 focus/elevation 可辨識度。
- Matplotlib render path 若會 `ax.clear()`，constructor-only theme 不足；每次 `render refresh` / clear 後都必須重新套 figure/axes/pane/grid/tick/text 的 presentation theme，operator dimensions/warning/error 不得掉回黑字。
- generic 3D/workbench canvas 使用 shared canvas token `#0d0d0f`；已驗收的 `Corner Data / unfold` drawing viewport 是例外，必須保留 `#000000`，禁止 global canvas replace 覆蓋它。
- `primary operator text`、尺寸、current selection、warning/error 不得降成 muted gray；action/selection/focus/warning/error 等 `semantic colors` 必須保持可辨識角色。
- 真正 visual acceptance 要在 real Tk/Xvfb 驗有效 style/state 與 reachability，至少覆蓋 `1.0 / 1.2 / 1.4`、normal/selected/focus/readonly/disabled/active，以及 Matplotlib clear 後的文字可讀性；有 screenshot 能力才宣告 pixel review。
- theme / text-scale refresh 必須維持既有 `persist=False` 外部同步邊界，不得 trace-echo 回設定 owner；`config.ini` 前後必須保持 invariant。

<!-- WHD_SHEETMETAL_DUAL_PROJECTION_RULE_20260917 -->
## Modern 鈑金選單 / Structure Tree 共用 authority 規則

- UI 物件存在不等於 UI 驗收通過；modern `Phase6PrimaryApplication` 必須實際證明控制項已 mapped/managed，且 callback 可由操作路徑觸發。legacy startup 綠燈不能替代 modern startup 可見性證據。
- 「不要第二個 selector」的真正契約是：不得建立第二個 authoritative state owner / state machine；同一 authoritative workspace state 可以有多個 presentation projection。
- Compact 鈑金選單與 Structure Tree 可以同時可見，但都必須讀寫同一個 `designer_workspace.active_part`，不得各自保存真實狀態。
- 不同 projection 可以有不同粒度：Structure Tree 可指向 exact physical child；compact menu 可以只顯示 top-level parent label。禁止把 display `StringVar` 當成 physical-part authority 來做等值斷言。
- 任一 selector 改變 authoritative part 後，必須 refresh 其他已顯示 projection，避免畫面殘留舊 selection。
- 修復隱藏控制項時，優先恢復既有 widget/state/callback 的 layout 與 projection refresh；禁止為了讓 UI 出現而複製 state owner。

### REAL_PIXEL_VISIBILITY_GATE_V1
- Tk 控制項 `winfo_ismapped()` / geometry manager 非空，只能證明它被 geometry manager 管理，不能證明操作者真的看得到。若控制項與 Canvas / sibling 疊層共存，驗收至少要檢查：viewport 交集為正、實際寬高為正、控制項中心點 `winfo_containing()` 命中該控制項或其子元件，而不是被 Canvas / overlay 蓋住。
- 現代啟動 UI 的「可見」驗收必須包含 real-pixel / stacking hit-test；不得再以 object exists、`mapped == 1`、pack/grid manager 非空單獨宣稱可見。
- Canvas `create_window(window=...)` 若嵌入的是 Canvas 的 sibling/root child，必須明確處理 stacking order；mapped child 仍可能被 sibling Canvas 完整塗在下面。


### 截角資料庫中文展示邊界（WHD_CORNER_REGISTRY_CHINESE_PRESENTATION_RULE_20260917）

- 截角資料庫中所有使用者可見文字都必須以繁體中文呈現；內部 raw ID、enum、schema、規則 ID 可維持既有英文值，但不得直接漏到畫面。
- 中文化只能發生在 presentation adapter；不得為了 UI 驗收改寫 registry 原始資料、幾何 authority 或持久化契約。
- 公式、前置條件、來源備註、選單值、Treeview、Canvas 文字與視窗標題都屬 presentation boundary。
- 驗收必須逐筆選取資料庫中的全部規則並掃描實際 rendered text；只驗初始畫面或第一筆規則不算通過。


## #382：shared content area 與 presentation-only hierarchy（2026-09-20）

<!-- ISSUE382_SHARED_CONTENT_PRESENTATION_CONTRACT -->

- 同一操作區若依 mode 顯示不同內容，優先使用 **shared content area** 切換 presentation；不得因為舊 navigation widget 還存在，就讓 retired compatibility surface 持續 reserve / overlay operator pixels。
- UI 分組父項若只為閱讀層級存在，必須保持 **presentation-only**。不得為了顯示「門／底板」父層就發明 workspace part、project identity、manufacturing part 或第二份 visibility owner。
- 真實 physical child 的 `part_key`、visibility、read-only data、callback 與 domain owner 必須在 re-parent / regroup 前後完全相同。
- collapse/expand 與 show/hide 是不同狀態。收合不能改 visibility；visibility 不能刪除或遮斷資料；panel rebuild 只能延續 presentation stash，不得把 collapse state 寫成 domain/project truth。
- 若產品要求 default collapsed，驗收必須覆蓋 logical row、presentation parent、真實 multipart child；不能只改最外層 container。
- 「沒有新增編輯能力」要做 machine guard：組合體 read-only presentation 不得因 layout rewrite 偷加 `Entry / Combobox / Spinbox`。
- 跨平台 Tk MouseWheel event 欄位不能假設可直接轉整數；Windows `event.num` 可能為 `"??"`。scroll normalization 必須 fail-safe 且不改既有 delta 方向/速度。
- 較新的 product contract 取代永久可見舊 Structure Tree 時，舊測試若仍硬鎖 mapped/sticky surface，屬 superseded presentation contract；保留 state/identity/callback assertions，更新 stale layout assertion，禁止把舊 UI 搬回來討好測試。
- WHD 此產品規則的 canonical CURRENT owner 是 AI Library contract `phase6-assembly-shared-content-presentation`；本 Skill 保存可重用 UI engineering method，不複製 geometry/manufacturing authority。
