---
name: UI設計與去AI味
description: 當工作要新增、重整或審查 WHD UI，尤其使用者要求 UI 設計、介面重整、去 AI 味、AI slop audit、視覺層級、layout、typography 或「像真正工程軟體」時使用；只負責 presentation / hierarchy / interaction presentation，不取代產品、幾何、製造與資料 authority。
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

兩者**只作輸入**，WHD 不建立第二套 canonical `frontend-design` / `avoid-ai-design` Skill；Web-specific class、framework、hero、mobile-first 假設不能覆蓋 Tkinter/ttk 與 WHD 工程操作需求。

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
