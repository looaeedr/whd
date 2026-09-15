# Phase6 深模組效能架構深化正式規格

- 文件狀態：正式設計規格／待使用者審閱
- 日期：2026-09-03（Asia/Taipei）
- 規格來源：`PHASE6_GUI_PERFORMANCE_KNOWLEDGE_FULL_20260903_124853.zip`
- 前置證據：Phase6 深模組架構掃描、GUI 效能 Knowledge Preflight、截角／3D 完整性 Gate
- 本規格性質：架構深化與效能完整性，不改既有機械公式、不改操作語意、不以縮行數為目標

---

## 1. Problem Statement

Phase6 已經具有 Scheduler、Transaction Guard、live-sync、FinalScene、DXF source cache、canonical manufacturing、collision solver 等重要元件，但目前幾個關鍵責任仍停留在「有模組、但 caller 仍可繞過」的狀態。

深模組掃描已確認以下結構性問題：

1. GUI 更新／重算管線存在多個直接完整重算與直接重繪入口，Scheduler 尚未成為不可繞過的唯一 calculation executor。
2. 單一 UI handler 已能確認存在「完整重算後又再直接 preview」的雙重重繪路徑，代表目前 caller 仍需知道更新順序。
3. Fold Designer Bridge 同時承擔 legacy patch、Workspace、live-sync、3D preview、settings、manufacturing／relief orchestration 與 render gating，caller 與 Bridge 共同知道過多交易順序與防回音細節。
4. DXF immutable source cache 已具正確 fingerprint，但 derived geometry cache 的 dependency invalidation 仍散在 GUI handler，造成失效權責不集中。
5. Manufacturing 與 Assembly Collision 之間存在雙向延遲 import／跨層 helper 依賴，兩個重要深模組仍彼此知道對方內部細節。
6. 現有一般 regression 可以全綠，但仍不足以證明真 GUI 的 burst 操作不會出現重算風暴、重複 render、重複 DXF I/O 或 live-sync echo。

這些問題的共同根因不是「檔案太大」，而是**更新、同步、失效與求解責任沒有完全被深邊界吸收**。

---

## 2. Solution

本規格採用「先深化責任邊界，再考慮任何檔案重整」的方案，依序完成四個工作流：

1. **Scheduler 唯一執行權**：所有 GUI／3D mutation 只能提交 dirty state 與 flush request；完整 calculation、FinalScene／manufacturing resolve、scene rebuild、render 的實際執行順序只由 Scheduler 決定。
2. **Bridge Orchestration 深化**：保留 Bridge 作 legacy compatibility boundary，但把 transaction、anti-echo、part switch、live-sync、preview／render decision 收進單一 orchestration seam，caller 不再理解 patch 疊加順序。
3. **DXF Derived Cache Owner**：保留目前 immutable source cache，新增／深化 derived geometry owner，以 dependency key 精準失效；普通尺寸修改不得清 parsed source cache。
4. **Manufacturing → Collision 單向依賴**：建立中立 canonical contract，使 manufacturing orchestration 可呼叫 collision solver，但 collision solver 不再回頭依賴 manufacturing 內部 helper。

整體目標是把下列規則從「文件要求」變成「架構本身無法輕易違反的事實」：

> 單一使用者 mutation，在同一 transaction 中最多一次完整重算、一次 FinalScene／manufacturing resolve、一次 scene rebuild、一次 render；等價 live-sync state 不得回音重算；普通尺寸修改不得重新讀取相同 DXF source。

---

## 3. 核心架構原則

### 3.1 不以縮檔案為目的

本次禁止用行數、函式數、類別數作拆模組理由。只有同時滿足以下條件才允許形成新深模組：

- 有明確 Source of Truth；
- 有真正共享的規則或 invariant；
- 至少有兩個實際 caller／adapter；
- deletion test 顯示若刪除該邊界，複雜度會重新散回 caller；
- 新 interface 能讓 caller 少知道交易順序、失效規則或內部幾何細節。

### 3.2 保護既有深模組

以下元件目前視為「應繼續加深，而非為縮檔硬拆」：

- FinalScene view：Final Material → 3D 顯示、折線、尺寸與 render owner。
- Fold Profiles：箱身與封頭／封尾 Fold Profile 共享語意 owner。
- Designer Workspace：板件生命週期與 workspace invariant owner。
- Assembly Collision：碰撞／穿透／backprojection solver owner。
- Manufacturing API：headless／GUI 共用 canonical manufacturing boundary。

### 3.3 機械真值不進本次重構範圍

本次不得順手改動：

- Canonical Dimension Model；
- Assembly Intent 與 AssemblyJoint Graph 語意；
- `INSERT / OVERLAY / INSERT_OVERLAY`；
- 正式高階名稱「包覆貼外」及其局部 `WRAP` Joint relation；
- STANDARD 母規則；
- Certified Relief Registry 的公式與 revision；
- Head／Tail mirror、真实板厚、合法接觸／非法穿透判斷；
- 2D／單板 3D／組合 3D／DXF／NC 的 canonical manufacturing geometry。

Registry HIT 仍是正式製造答案；3D shadow 不得覆寫 Certified Rule。

---

## 4. 目標資料流

正式更新資料流統一為：

```text
使用者操作 / Tk trace / 3D callback / live-sync external apply
        ↓
Mutation Adapter
        ↓
Transaction + Dirty Set
        ↓
Scheduler
        ├─ canonical state normalization
        ├─ precise cache invalidation
        ├─ calculation / manufacturing resolve（若需要）
        ├─ FinalScene / scene rebuild（若需要）
        └─ render（若需要）
        ↓
GUI / 2D / 3D / export consumer
```

Save／Export／DXF／NC 不另開第二條資料鏈，必須先要求 Scheduler `flush_now()`，再讀 committed authoritative result。

---

# 5. Workstream A — Scheduler 成為唯一 Calculation Executor

## 5.1 目標

把目前「Scheduler 可用但可被繞過」改為「所有 mutation 都必須經 Scheduler」。

### 5.2 唯一執行權契約

一般 GUI／3D mutation handler 只允許做下列事情：

- normalization／actual delta 判斷；
- 更新 canonical input state；
- `mark_dirty(reason)`；
- `request_flush()`；
- 在明確 commit seam 使用 `flush_now()`。

一般 mutation handler **不得直接執行**：

- 完整尺寸 calculation；
- canonical manufacturing resolve；
- FinalScene build；
- scene rebuild；
- preview／canvas render；
- DXF source reload；
- 全域 cache clear。

允許的 direct executor 例外只限：

1. 應用程式 bootstrap／Scheduler 尚未建立前的相容 fallback；
2. Scheduler 自己的內部 executor；
3. 測試用明確 seam；
4. 不能接受 stale state 的 `flush_now()` commit seam，但 commit seam 仍只能要求 Scheduler 執行，不能自己重算。

所有例外必須有明確 allowlist，禁止用 broad fallback 擴張例外。

## 5.3 Dirty Reason

Dirty reason 至少具有以下分類：

| Dirty Reason | 典型來源 | Calculation | Manufacturing / FinalScene | Render |
|---|---|---:|---:|---:|
| `geometry` | W/H/D/T/FW、Fold topology、piece geometry | 是 | 是 | 是 |
| `assembly` | Assembly Intent、Joint、Corner/Relief manufacturing input | 視 canonical chain | 是 | 是 |
| `baseline` | baseline source/reload generation/基準模型變更 | 視 derived dependency | 視需要 | 是 |
| `display` | 顯示開關、透視、純視覺 option | 否 | 否 | 是 |
| `annotation` | 尺寸文字、標註顯示 | 否 | 否或 annotation-only scene | 是 |
| `camera` | pan/zoom/rotate | 否 | 否 | 是 |

實作可增加更細分類，但不得把所有 reason 再合成「全部重算」。

## 5.4 Transaction Semantics

Transaction Guard 只管理 nesting 與批次邊界，不自行 calculation。

- `begin`：開始收集 dirty set。
- nested mutation：只合併 dirty reason 與 actual delta。
- `end`：最外層 transaction 結束時通知 Scheduler 可 flush。
- transaction 內不得因每一個 `var.set()` 各自完整計算。
- 同一 transaction 的相同 dirty reason 必須 coalesce。

### 5.5 Debounce / Throttle

連續 Slider／Spinbox／drag 類事件使用短 trailing debounce；建議初始值 **75ms**，允許依壓力測試在 50–100ms 內調整。

以下事件不得等待 trailing debounce：

- Enter；
- FocusOut；
- MouseRelease；
- part switch commit；
- Family／Assembly Intent 完成選擇；
- Save／Save As；
- Export；
- DXF／NC／批次製造；
- 關閉／返回 2D 前的正式 commit seam。

最後一筆 mutation 必須保證被 flush，禁止 debounce 吃掉最終值。

## 5.6 單次工作上限

對單一 geometry edit，在一個 transaction 完成後：

- 完整 recalculation `<= 1`；
- manufacturing／FinalScene resolve `<= 1`；
- scene rebuild `<= 1`；
- render `<= 1`；
- 相同 DXF source disk reread `= 0`；
- live-sync echo `= 0`。

這些是架構 invariant，不是平均值目標。

---

# 6. Workstream B — GUI ↔ 3D Anti-Echo 與 Atomic Initialization

## 6.1 Sync Envelope

GUI ↔ 3D 的同步 envelope 至少包含：

- `origin`；
- `revision`；
- `transaction_id`；
- canonical actual delta／fingerprint。

### 6.2 Actual Delta

任何批次 state apply 在寫 Tk Variable 前必須 canonical compare。

- 值相同不得 `var.set()`；
- 等價 state 不建立新 revision；
- Main GUI → 3D 的 state 若沒有在 3D 被使用者實際修改，不得原封不動 publish 回 Main GUI；
- external apply 不得因 mirror field 造成第二輪 mutation。

### 6.3 Revision 規則

- 新 revision 只由真實 authoritative mutation 產生；
- stale revision 不得覆蓋較新 revision；
- 同 transaction 的多欄位批次變更只形成一個 commit revision；
- persistence mirror／compatibility field 不得提升為第二 Source of Truth。

## 6.4 3D Atomic Initialization

3D 初始化狀態固定為：

```text
INITIALIZING
    ↓ ingest authoritative current state
    ↓ build internal view state
    ↓ compare revision / fingerprint
READY
```

`INITIALIZING` 期間：

- 不 publish default；
- 不 publish intermediate state；
- 不以 persisted stale value 覆蓋目前使用者輸入；
- 不因 widget 建立過程觸發多輪 manufacturing／render。

權威優先順序固定：

```text
使用者目前輸入
> authoritative application state
> persisted state
> 3D default
```

初始化完成後若 3D 與 Main GUI 等價，publish 次數必須為 0。

---

# 7. Workstream C — Fold Designer Bridge Orchestration 深化

## 7.1 Bridge 的定位

Bridge 保留，因為它吸收 legacy Fold Designer 與現行 Phase6 架構之間的相容複雜度；本規格**不要求把 Bridge 拆成大量小檔**。

Bridge 最終責任分成兩層：

### 薄 Compatibility Layer

只負責：

- legacy method／attribute adapter；
- 舊 API shape 轉換；
- 舊 widget callback 接到新 orchestration interface；
- 不在此層決定 calculation／render 順序。

### 深 Orchestration Seam

集中負責：

- transaction boundary；
- dirty reason；
- live-sync ingest／publish；
- anti-echo；
- part switch；
- setting apply；
- preview gating；
- Scheduler flush policy；
- manufacturing query 時機；
- single render decision。

## 7.2 `do_update` 類責任

任何歷史 `do_update` wrapper／queue wrapper／preview-aware wrapper 的最終效果都必須收斂成「向 orchestration seam 提交 intent」，而不是多層 wrapper 各自可能呼叫真正更新。

目標不是把所有 legacy method 立即刪除，而是：

> legacy method 可以存在，但不能再擁有 calculation ownership。

## 7.3 Part Switch

箱身／封頭／封尾快速切換屬高風險效能路徑：

- 若 canonical geometry 未改，只變 active part，禁止完整 manufacturing solve；
- scene 可使用已 committed canonical material；
- 只需 active view／annotation／camera 的變更不得誤標 `geometry` dirty；
- Head ↔ Tail 切換不得造成全域 D、final material、展開料漂移。

## 7.4 設定批次套用

設定 snapshot 必須 schema-aware normalization，禁止「非 bool 一律 float」型 generic conversion。

整包 settings apply：

- canonical compare 後只寫 actual delta；
- 同 transaction 一次 flush；
- 純顯示設定不得 manufacturing solve；
- Family switch 必須原子更新 family topology、workspace state、live globals 與 GUI vars。

---

# 8. Workstream D — DXF Source Cache 與 Derived Geometry Cache

## 8.1 兩層快取不可混用

### Immutable DXF Source Cache

Source fingerprint 至少包含：

```text
normalized path
+ size
+ mtime_ns
+ parser/schema version
+ reload generation
```

此層保存解析後的不可變 source truth。

### Derived Geometry Cache

Derived key 必須由：

```text
source fingerprint
+ 真正會影響該衍生結果的 canonical dependency subset
```

組成。

不得把 W/H/D/FW/Joint 等所有 state 無差別塞成一顆全域 key；不同 derived product 應各自聲明 dependency。

## 8.2 Invalidation Matrix

至少遵守：

- W/H/D/FW 改變：只失效相關 derived geometry；不得清 source cache。
- Family／structure 改變：失效受 topology 影響的 derived geometry。
- Assembly Intent／Joint 改變：失效 assembly/manufacturing derived result；不代表 source DXF 變了。
- display／annotation／camera：不得清 geometry source／derived manufacturing cache。
- Force Reload：reload generation +1，必須繞過相同 path/size/mtime fingerprint。
- parser/schema 升版：舊 source cache 必須自然 miss。

## 8.3 網路磁碟安全語意

若 baseline 位於網路磁碟，暫時 stat/read 失敗：

- GUI preview 可使用 last-known-good；
- 必須標記 `SOURCE_UNVERIFIED`；
- 不得把 last-known-good 冒充 fresh authoritative source；
- Save authoritative manufacturing result、Export、DXF、NC、批次製造不得使用 `SOURCE_UNVERIFIED` 當正式 fresh truth。

網路 I/O 不以 UI 大鎖包住整個 transaction；source verification 與 GUI render ownership 必須分離，避免把網路等待放大成全 UI freeze。

---

# 9. Workstream E — Manufacturing 與 Collision 依賴單向化

## 9.1 目標方向

依賴方向固定為：

```text
Canonical Final Material / Scene Contract
      ├─> Manufacturing Orchestration
      └─> Assembly Collision Solver

Manufacturing Orchestration
      └─> Collision Solver（需要求解時）
```

Collision Solver 不得反向 import Manufacturing orchestration 內部 helper。

## 9.2 中立 Contract

共同 contract 至少能描述：

- physical part identity；
- final material polygon／holes／relief；
- fold topology；
- true sheet thickness；
- piece-level transform／UV owner；
- AssemblyJoint resolved relation；
- legal contact semantics；
- solver constraints；
- diagnostic metadata 與 manufacturing truth 的分界。

中立 contract 只表達資料，不擁有 UI callback 或 manufacturing orchestration 流程。

## 9.3 Collision Result

Collision solver 回傳結果必須能分清：

- legal contact；
- illegal positive-volume penetration；
- pre-solve evidence；
- candidate relief/backprojection；
- post-solve zero-penetration verification。

Registry HIT 仍直接使用 Certified manufacturing geometry，collision 只做 shadow／regression；Registry MISS 才允許 candidate discovery。

---

# 10. User Stories

1. 作為 Phase6 操作員，我希望改一次 W/H/D/T 只觸發一次有效重算，避免輸入時卡頓。
2. 作為 Phase6 操作員，我希望連續拖曳 Slider 時畫面能跟上，但放開滑鼠後一定得到最後正確值。
3. 作為 Phase6 操作員，我希望快速切箱身／封頭／封尾不會每切一次都重新求完整 manufacturing geometry。
4. 作為 Phase6 操作員，我希望切 Family 或 Assembly Intent 後只計算真正受影響的資料，不要整頁反覆重畫。
5. 作為 Phase6 操作員，我希望開啟 3D 不會把我剛輸入的新尺寸蓋回舊值。
6. 作為 Phase6 操作員，我希望 GUI 與 3D 同步後不會互相回送相同資料造成卡頓。
7. 作為 Phase6 操作員，我希望純 camera rotate／zoom 不觸發尺寸重算或 manufacturing solve。
8. 作為 Phase6 操作員，我希望改文字大小或顯示選項時不會重新讀 DXF 或重建加工幾何。
9. 作為 Phase6 操作員，我希望同一基準 DXF 在普通尺寸調整時不會反覆從 Z: 網路磁碟讀取。
10. 作為 Phase6 操作員，我希望網路磁碟暫時斷線時 preview 可保留 last-known-good，而不是整個 GUI 卡死。
11. 作為 Phase6 操作員，我希望網路來源未驗證時，系統不會偷偷輸出可能 stale 的 DXF／NC。
12. 作為 Phase6 操作員，我希望 Force Reload 能真的強制重新讀來源，即使檔案大小與時間看起來相同。
13. 作為 Phase6 操作員，我希望 Save／Export 前系統一定把尚未 flush 的最後輸入提交完成。
14. 作為 Phase6 操作員，我希望 Head／Tail 快速切換不會讓全域 D 或展開料逐次漂移。
15. 作為 Phase6 操作員，我希望 2D、單板 3D、組合 3D、DXF／NC 永遠讀同一 committed manufacturing result。
16. 作為開發者，我希望所有 mutation 只需要告訴 Scheduler「什麼變髒了」，不需要每個 handler 自己決定重算順序。
17. 作為開發者，我希望新增一個 UI 控制項時，不需要知道 FinalScene、manufacturing、render 之間誰先誰後。
18. 作為開發者，我希望 Transaction Guard 只管理 transaction，不再藏有第二套 calculation ownership。
19. 作為開發者，我希望 Bridge 的 legacy patch 仍可相容，但 patch 不再擁有真正的更新執行權。
20. 作為開發者，我希望 live-sync 是否 publish 只由 actual delta/revision 決定，而不是依 callback 是否被觸發。
21. 作為開發者，我希望 derived cache 的 dependency 與 invalidation 集中管理，不必在每個 GUI handler 手動清 dict。
22. 作為開發者，我希望 source cache 與 derived cache 分離，避免修尺寸時不小心打網路 I/O。
23. 作為開發者，我希望 Collision solver 可單獨用 canonical contract 測試，不需要 import manufacturing orchestration 內部 helper。
24. 作為開發者，我希望 Manufacturing API 保持穩定 headless boundary，不因解循環依賴而把 solver 細節洩漏給 GUI。
25. 作為開發者，我希望新增 Assembly Intent 後，回歸矩陣可由 registry／semantics 自動加入，而不是再手工白名單。
26. 作為維護者，我希望大型模組只有在責任邊界真的能加深時才拆，不要為了行數製造更多 adapter。
27. 作為維護者，我希望效能修正不藉由降低幾何精度、延遲不更新或關掉必要求解製造假快。
28. 作為測試者，我希望能用 counters 直接驗證一次操作的 calculation／scene／render 次數。
29. 作為測試者，我希望一般 regression 之外還有真 GUI burst stress，能抓到短時間事件暴增。
30. 作為測試者，我希望 Headless 與 Xvfb 的長回歸都有 durable journal，不因外層 timeout 重頭跑。
31. 作為交付者，我希望正式 FULL／UPDATE 出包前能證明 `config.ini` 未改、封包重解壓後仍通過 gate。
32. 作為專案維護者，我希望新的踩坑一旦被確認，就同步寫入 Skill／踩坑庫，避免下一輪重新犯同一個更新風暴問題。

---

# 11. Implementation Decisions

1. Scheduler 是唯一 calculation executor；一般 mutation callback 不擁有完整 calculation／scene／render ownership。
2. Dirty reason 成為最小工作選擇的正式輸入，不允許名義上分類、實際上所有 reason 都走全重算。
3. Transaction Guard 與 Scheduler 分工：前者只管理 transaction nesting，後者管理 flush 與實際工作執行。
4. live-sync 使用 origin、revision、transaction_id 與 actual delta；等價 state 不回送。
5. 3D 初始化採 ingest-only atomic initialization；default／intermediate 不 publish。
6. Bridge 保留為 compatibility boundary，但新增／深化 orchestration seam，legacy wrapper 不再擁有 executor 權。
7. Immutable DXF source cache 沿用既有 fingerprint 契約；derived geometry invalidation 另設 owner。
8. `SOURCE_UNVERIFIED` 是 preview 可接受、正式製造輸出不可接受的來源狀態。
9. Manufacturing 與 Collision 透過中立 Final Material／Scene contract 溝通；solver 不再反向依賴 manufacturing orchestration internals。
10. FinalScene view、Fold Profiles、Designer Workspace 不因檔案大小被列為本輪硬拆目標。
11. 統一更新 seam 的第一優先級高於 Bridge 檔案瘦身；在 Scheduler ownership 未完成前禁止先大規模搬 code。
12. 本規格不變更任何 Certified Relief Rule 或 assembly mechanical semantics。
13. `config.ini` 不得因本工作修改。
14. UI 操作名稱、欄位與既有存檔格式保持相容；若為架構 migration 增加 persistence metadata，必須向後相容且不得把 compatibility field 提升成 Source of Truth。
15. 每一階段先建立外部行為與 counters 的 red test，再修改 production，避免先搬 code 後才猜效能是否變好。

---

# 12. Testing Decisions

## 12.1 測試原則

主要測試以**外部行為與可觀察 invariant**為準，不以「某個私有函式被呼叫」冒充正確性。

可觀察指標包括：

- committed canonical state；
- final material fingerprint；
- 2D／3D scene fingerprint；
- calculation count；
- manufacturing／FinalScene resolve count；
- DXF disk read count；
- render count；
- live-sync publish／echo count；
- wall time；
- process／Tk grab／Xvfb orphan 狀態。

另設 architecture conformance gate，用於防止一般 mutation handler 再出現 direct executor bypass；此 gate 屬架構防線，不取代行為測試。

## 12.2 Scheduler Contract Tests

至少覆蓋：

1. 單一 geometry edit：calc <=1、scene <=1、render <=1。
2. 同 transaction 多個 `var.set()`：只形成一次 committed calculation。
3. display-only：calc=0、manufacturing=0、render<=1。
4. camera-only：calc=0、scene rebuild=0、render<=1。
5. Enter／FocusOut／MouseRelease：最後值立即 committed。
6. trailing debounce：burst 中可 coalesce，最後值必定落盤。
7. Save／Export：若仍有 pending dirty，先 flush，再讀 authoritative result。

## 12.3 Anti-Echo Tests

至少覆蓋：

1. Main GUI → 3D 等價 ingest：3D publish=0。
2. 3D 真實修改：只 publish 一個新 revision。
3. Main GUI 收到自己的等價 transaction：不再 write Tk vars、不重算。
4. stale revision：reject。
5. 3D 初始化：不得 publish default/intermediate state。

## 12.4 Part Switch／Family Stress

至少覆蓋：

- 箱身 → 封頭 → 封尾 → 箱身快速循環；
- Head ↔ Tail 10 次以上；
- Vault ↔ Receiving Family；
- INSERT／OVERLAY／INSERT_OVERLAY 與正式「包覆貼外」相關 Joint state；
- part switch 前後 final material fingerprint／全域 D／展開料不漂移。

## 12.5 DXF Cache Tests

至少覆蓋：

1. 相同 fingerprint：disk read=0 additional。
2. W/H/D/FW change：source reread=0，只 invalid derived。
3. source mtime_ns／size／parser version change：source miss。
4. Force Reload：相同 stat 仍 reread。
5. 網路 stat/read failure：preview 使用 LKG + `SOURCE_UNVERIFIED`。
6. `SOURCE_UNVERIFIED`：Export／DXF／NC fail closed 或要求 fresh verification。

## 12.6 Manufacturing／Collision Contract Tests

至少覆蓋：

- true thickness；
- legal contact 不算 penetration；
- illegal positive-volume penetration 可見；
- solver 前 collision evidence 存在；
- solver 後零非法穿透；
- Head／Tail 各自驗證；
- 多片箱身 piece-level transform／UV；
- Registry HIT 不被 3D candidate 覆寫；
- Registry MISS candidate 不冒充 Certified；
- 2D／單板 3D／組合 3D 共用 final material。

## 12.7 真 GUI 壓力 Gate

一般 pytest 全綠仍不算效能完成。至少實跑：

1. W/H/D/T 各 20 次 burst；
2. FW 連續修改；
3. 箱身／封頭／封尾快速切換；
4. Family 快速切換；
5. Assembly Intent 快速切換；
6. 3D 開／關；
7. 3D camera rotate／zoom；
8. 連續開啟／返回 2D；
9. 網路 DXF source warm-cache 情境；
10. Force Reload 情境。

每段都保存：wall time、calc、DXF disk read、manufacturing resolve、scene rebuild、render、publish/echo、最終 state/scene fingerprint。

## 12.8 長回歸與 Durable Evidence

正式長測必須使用 resumable release runner：

- Headless 與 Xvfb 分開 journal；
- exit 75 是安全 checkpoint，不是 fail；
- collection SHA/count 必須綁定 journal；
- timeout batch 未 completed；
- aggregate timeout 先縮批，不先判 production failure；
- complete teardown timeout 與真正 test timeout 分類；
- process group 必須清乾淨；
- durable checkpoint 保存來源包、patch/hash、collection、completed/pending/failed、journal、效能 counters 與下一步命令。

---

# 13. 回歸矩陣

本次架構深化不得降低既有幾何與製造 gate。正式驗收至少包含：

- 所有 registry/semantics 自動枚舉的 Assembly Intent；
- Head／Tail；
- INSERT；
- OVERLAY；
- INSERT_OVERLAY；
- 局部 WRAP／正式「包覆貼外」相關案例；
- 求解前碰撞顯示；
- 求解後零非法穿透；
- 2D／單板 3D／組合 3D 尺寸與截角一致；
- Fold/BEND line 與 retained material 一致；
- 二件式／三件式逐片展開料；
- Save／Reload；
- DXF／NC／批次輸出；
- 真 `.p6fold` canonical fixture 與 synthetic matrix；
- Receiving Head/Tail D 不漂移；
- 受電箱 Family 本身不得自動擁有 WRAP；只有 resolved Joint Graph 決定 WRAP。

---

# 14. 架構 Conformance Gate

完成 Workstream A 後，必須有 fail-closed 防線阻止舊問題重新進入：

1. 一般 mutation handler 不得直接完整 calculation。
2. 一般 mutation handler 不得直接 FinalScene/manufacturing solve。
3. 一般 mutation handler 不得在 calculation 後再直接 redraw 形成重複 render。
4. display/camera callback 不得標 geometry dirty。
5. ordinary dimension change 不得 source cache clear／force reload。
6. Bridge compatibility wrapper 不得重新取得 executor ownership。
7. Collision solver 不得重新 import manufacturing orchestration internals。

例外必須集中 allowlist；新增例外需要測試與理由，不接受「先讓它跑」型 broad exception。

---

# 15. 遷移順序

## Phase A — Executor Ownership

先完成 Scheduler 唯一執行權與 counters，不改 Bridge 大結構。

完成條件：

- 已知雙重 redraw 路徑消失；
- mutation handlers 只提交 dirty/flush；
- 單一 edit counters 達標。

## Phase B — Sync / Bridge Orchestration

在唯一 executor 穩定後，把 Bridge 的 do_update／queue／preview gating 收到 orchestration seam。

完成條件：

- 等價 sync echo=0；
- initialization publish=0；
- part switch 不做不必要 full solve；
- legacy compatibility 行為保持。

## Phase C — Derived Cache Owner

集中 dependency key 與 invalidation matrix。

完成條件：

- ordinary geometry edit source reread=0；
- Force Reload 正常；
- SOURCE_UNVERIFIED fail-safe 完整。

## Phase D — Manufacturing / Collision Direction

在更新 seam 與 cache 穩定後再解雙向依賴，避免同時搬兩個高風險邊界。

完成條件：

- solver 可從中立 contract 獨立測；
- manufacturing → collision 單向；
- 既有 3D／registry／zero penetration gate 不變。

## Phase E — Full Stress / Release Gate

最後才跑完整真 GUI stress、Headless／Xvfb 全套與打包後 fresh extraction gate。

---

# 16. Out of Scope

本規格明確不做：

- 不重新設計 Phase6 GUI 版面；
- 不新增新的 Assembly Intent；
- 不修改 INSERT／OVERLAY／INSERT_OVERLAY／WRAP 的製造公式；
- 不修改 STANDARD 母規則；
- 不因架構整理重寫 Certified Registry；
- 不為了縮行數拆 `FinalScene view`、`Fold Profiles`、`Designer Workspace`；
- 不把大型 hole editor 單函式列為本輪優先拆分目標；
- 不用降低 3D 幾何精度換效能；
- 不用大 debounce 隱藏重算風暴；
- 不關掉 collision／manufacturing 求解製造假快；
- 不修改 `config.ini`；
- 不把一次性 `/mnt/data/自訂*.p6fold` 重新變成永久測試依賴。

---

# 17. Acceptance Criteria

以下全部成立才算本規格完成：

### 更新管線

- [ ] Scheduler 是唯一 calculation executor。
- [ ] 單一 geometry edit recalculation <= 1。
- [ ] 同 transaction FinalScene/manufacturing resolve <= 1。
- [ ] 同 transaction render <= 1。
- [ ] 已知 double-preview path 已消失。
- [ ] display/camera 不觸發 manufacturing solve。
- [ ] Save/Export/DXF/NC 前一定 flush authoritative state。

### 同步

- [ ] GUI → 3D → GUI 等價 state echo = 0。
- [ ] actual delta 才 write Tk vars。
- [ ] stale revision reject。
- [ ] 3D initialization intermediate/default publish = 0。

### Cache

- [ ] ordinary W/H/D/FW edit 對相同 DXF disk reread = 0。
- [ ] Force Reload 可繞過 fingerprint。
- [ ] derived invalidation 由單一 owner 決定。
- [ ] SOURCE_UNVERIFIED preview 與正式輸出權限分離。

### 架構

- [ ] Bridge compatibility 與 orchestration ownership 分離。
- [ ] Manufacturing → Collision 依賴單向。
- [ ] FinalScene/Fold Profiles/Workspace 沒有因縮檔被硬拆。
- [ ] 無第二套 mechanical Source of Truth。

### 幾何／製造完整性

- [ ] Registry HIT 仍為 canonical manufacturing answer。
- [ ] 求解前 collision evidence 存在。
- [ ] 求解後零非法穿透。
- [ ] Head/Tail 都過。
- [ ] 2D／單板3D／組合3D／DXF／NC 一致。
- [ ] Save/Reload 一致。
- [ ] 二件式／三件式逐片展開料一致。

### 效能／Release

- [ ] 真 GUI stress 全部通過，無事件暴增。
- [ ] 無 Tk grab／pytest／Xvfb orphan。
- [ ] Headless full suite 綠。
- [ ] Xvfb full suite 綠。
- [ ] durable evidence 完整。
- [ ] `config.ini` SHA256 不變。
- [ ] 正式封包從 fresh extraction 再驗證通過。

---

# 18. Failure Conditions

任一條成立都不得宣告完成：

- 為了達到 wall-time 目標直接跳過必要 manufacturing／FinalScene；
- 用 200ms 以上大 debounce 掩蓋單 transaction 多次重算；
- GUI 看起來變快，但 Save／DXF／NC 讀到 stale state；
- headless PASS 就宣稱 GUI 順暢，未跑真 GUI stress；
- 只改 callback 次數，未驗最終 geometry/scene；
- source cache 命中但 derived geometry 使用錯 dependency 而 stale；
- 網路來源失聯時仍允許 authoritative manufacturing export；
- 為了解 import cycle 把 solver logic 複製一份到 manufacturing；
- 只為縮 Bridge/gui 行數新增大量一層 wrapper；
- 改動 Certified Registry／機械公式卻沒有另立幾何規格與完整 3D gate；
- 任何新增 regression failure 尚未 root-cause 就打包交付。

---

# 19. Further Notes

1. 深模組掃描已確認現有 GUI 效能契約與 baseline source cache 目標測試共 7/7 通過；本規格的目的不是推翻現有成果，而是補上目前測試沒有鎖住的 bypass。
2. 實作時第一個 red test 應優先覆蓋「單一 handler 造成 calculation + double preview」的可觀察 counters，因為這是目前最直接、最確定的架構違規證據。
3. 第一階段完成後再決定 Bridge 內部是否需要實體搬檔；若 orchestration seam 已能充分吸收複雜度，檔案行數本身不是缺陷。
4. 每次本規格解掉一個可重現的效能坑，必須同步更新 Phase6 GUI performance Skill 與全域踩坑庫，不等使用者再次提醒。
5. 正式實作計畫必須依本規格拆成可驗證 checkpoint；不得同一刀同時改 Scheduler ownership、Bridge 大搬移、Cache owner 與 Collision dependency 四個高風險 seam。

---

# 20. Definition of Done

**完成不是「GUI 感覺比較快」。**

完成必須同時證明：

```text
唯一 executor
+ transaction coalescing
+ anti-echo
+ precise cache invalidation
+ 單向 solver dependency
+ canonical geometry 不變
+ 真 GUI stress
+ full regression
+ durable evidence
+ fresh-package verification
```

只有以上全部成立，才能進入正式 FULL／UPDATE 交付。
