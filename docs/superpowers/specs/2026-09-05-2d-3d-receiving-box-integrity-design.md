# WHD 受電箱 2D／3D 組裝與幾何一致性修正規格

- 日期：2026-09-05
- 目標分支：`cleanup/2d-3d-sync`
- 性質：實作前設計／驗收規格
- 相關問題：受電箱 2D／3D、內門中隔、封頭尾孔位、底板、文字尺寸、選擇框、3D→2D 回寫

## 1. 目的

本規格用於把目前已確認的 9 項問題收斂成單一可實作、可驗收的規則。核心要求是：

> 幾何、組裝拓撲、3D placement、2D 展開與 DXF 必須從同一份 authoritative resolved state 產生；不得讓 GUI、3D viewer、DXF exporter 各自重新計算一套幾何。

本規格不以「先調到畫面看起來正確」為驗收方式，而以資料模型、組裝關係、座標基準、回寫一致性及製造幾何一致性為準。

## 2. 現況與已確認根因

### 2.1 中隔／內門框

受電箱 Door layout 已有上下門配置；內門位於 upper door。內門的上、左、右框由完成後 Door geometry 推導，下邊界使用 Box Body divider 作為共享結構，而不是另造一條獨立下框。

目前 `BoxBodyDividerPart` 有 stable id、owner、axis、boundary、span、thickness、formed depth、handle side、fold chain 等幾何資料，但沒有完整的 world placement／assembly parent／rotation／anchor／mate target。3D assembly placement registry 也沒有正式的 divider / inner-door-frame placement。因此 scene rebuild 或 resolve 後可能退回預設 offset，造成中隔跳動。

### 2.2 封頭尾孔位

目前 Vault endcap fixed features 由 `VaultEndCapFeaturePolicy` 與 `config.ini` `[HOLES]` 等來源共同決定，至少存在：左右吊掛孔、方孔、封尾底部中心圓孔。不同 feature 有不同 datum 與適用面，不能把「Receiving 共用 Vault 基準」解讀成「整份 Vault hole policy 無條件共用」。

### 2.3 底板

目前設定層存在 top/bottom/left/right 全域縮短，並以 `base_w = W-left-right`、`base_h = H-top-bottom` 直接生成較小底板。這與「只有在真正解析出的接縫交會處做局部 relief，不能全域縮短底板」的製造規則衝突。

### 2.4 3D→2D

3D confirm 現有 snapshot 只回傳 box body profile、head、tail、structure 等部分狀態；專案已有 workspace collector 可收集 parts、profiles、features、face features、workspace，但完整 workspace 尚未成為 3D→2D 的 authoritative export contract。

## 3. 不可違反的架構原則

1. **Geometry Single Source of Truth**：幾何由 authoritative geometry result 產生。
2. **Assembly placement Single Source of Truth**：3D 世界座標由共用 assembly geometry／placement layer 決定。
3. **Topology 與 Factory Policy 分離**：板材怎麼折與裝配／製造退讓不能混成單一硬編碼公式。
4. **Part identity 穩定**：每個實體板件必須有 stable id；resolve/rebuild 不得因重建而產生另一個不相干的 placement identity。
5. **Derived part 必須可回推**：中隔、內門框等 derived parts 必須能由 authoritative assembly geometry 重新得到相同的幾何與 placement。
6. **2D／3D／DXF 使用同一 resolved physical pieces**：不得在任一顯示層另造第二套座標演算法。
7. **孔位先追溯再共享**：只有確認 feature 語意、datum、face、適用 family 均相容後才能共享 rule；不允許以名稱或「Vault 已有」直接複製 policy。

## 4. 功能規格

### 4.1 中隔：位置與組裝優先

#### 4.1.1 定義

中隔是 Box Body 的正式結構板件，同時作為 upper inner door 的 shared lower frame boundary。它不是單純 GUI 裝飾，也不是只依 Door 高度產生的視覺線。

#### 4.1.2 Assembly relationship

必須明確建立：

```text
Receiving Box Body
  └─ Door layout
      ├─ Upper Door
      │   └─ Inner Door
      │       ├─ Top Frame
      │       ├─ Left Frame
      │       ├─ Right Frame
      │       └─ Lower Boundary = Shared Center Divider
      └─ Lower Door
```

中隔的 parent / owner 為 Box Body；Inner Door frame role 透過 stable id 指向同一中隔，不得複製成另一個幾何零件。

#### 4.1.3 Placement contract

中隔必須具有正式的 assembly placement contract，至少包含：

- parent assembly node
- anchor / datum
- world offset 或等價 transform
- rotation
- mate target / assembly relationship
- stable id

placement 必須由共用 assembly geometry layer 產生。禁止在 GUI 中以滑鼠座標、畫面座標或固定 `(0,0,0)` fallback 重新定位。

#### 4.1.4 尺寸來源

在 placement 與 assembly 關係確認前，不得硬編碼新的中隔尺寸。尺寸應由 authoritative Door layout、Box Body topology、板厚及已認定的裝配關係推導。若完成程式追溯後仍存在製造端未定義的唯一尺寸，才列為待確認製造規則。

#### 4.1.5 驗收

- 預設建立時中隔位於正確組裝位置。
- 重新 resolve、重繪、切換 2D/3D 後，中隔世界座標不漂移。
- 拖動／調整後再次 resolve 不得跳回原點或其他錯誤位置。
- upper inner door 的 lower frame 與中隔仍指向同一 stable id。
- 中隔在 2D FinalScene、3D assembly、DXF 對應實體板件一致。

### 4.2 2D 必須顯示中隔與相關 3D 資訊

2D FinalScene 必須呈現 3D assembly 已存在且屬於 authoritative resolved state 的中隔、內門框與必要結構資訊。

「3D 有、2D 沒有」視為資料同步失敗，不得用額外的 2D 假圖補救。

2D 顯示資料必須由同一 resolved physical pieces 產生；若某項資訊是 3D assembly 的正式資訊，必須有對應的 2D projection／label contract。

### 4.3 3D→2D 完整回寫

3D Confirm 的輸出必須升級為完整 resolved workspace snapshot，至少涵蓋：

- parts / stable ids
- part profiles
- part features
- part face features
- workspace state
- box body structure
- head / tail geometry state
- divider / inner-door-frame placement
- 其他已在 3D 中被修改且屬 authoritative state 的 assembly 資訊

2D session 收到 snapshot 後，必須以該 snapshot 更新 authoritative state，再由 state 重建 2D；不得只挑幾個尺寸欄位回填。

驗收流程固定為：

```text
2D state
 → 3D resolve
 → 3D modify
 → Confirm
 → authoritative snapshot
 → 2D apply
 → 2D redraw
```

回到 2D 後再次進入 3D，resolved state 必須與 Confirm 前一致；不能出現第二次 resolve 又改變 placement／geometry 的情況。

### 4.4 封頭尾孔位：完整追溯後再決定共用

本項實作前必須建立 hole provenance table，逐一記錄所有實際產出的封頭／封尾孔與 secondary feature：

| Feature | Source | Semantic purpose | Face | Datum | Coordinate basis | Family applicability | Share status |
|---|---|---|---|---|---|---|---|
| 左吊掛孔 | 待程式追溯 | 吊掛／組裝基準 | 待追溯 | 待追溯 | 待追溯 | Vault / Receiving | 待判定 |
| 右吊掛孔 | 待程式追溯 | 吊掛／組裝基準 | 待追溯 | 待追溯 | 待追溯 | Vault / Receiving | 待判定 |
| 方孔 | 待程式追溯 | 組裝／設備開孔 | 待追溯 | 待追溯 | 待追溯 | 待判定 | 待判定 |
| 封尾底部中心圓孔 | 待程式追溯 | 封尾專用 | 待追溯 | 底部／展開基準待追溯 | 待追溯 | Tail only / family | 待判定 |

每一個 feature 必須能回答：

1. 誰定義它？
2. 用哪個 policy／registry／config？
3. 它的製造語意是什麼？
4. 它在哪一個 face？
5. 基準線是哪一條？
6. 座標從哪裡量？
7. relief / bend / thickness 是否參與計算？
8. Vault 與 Receiving 是否真的具有相同語意？
9. 可以共享的是公式、feature definition、registry rule，還是整份 family policy？

**未完成上述追溯前，不得以「共用 Vault」直接改 Receiving 孔位。**

### 4.5 底板

底板的 nominal blank 必須依正式尺寸語意產生，不得因一般 seam relief 而全域縮短 W/H。

Receiving bottom 的 WRAP / seam relief 僅在 resolved seam 真正與底板邊界相交時套用，預設 relief 總量 20 mm，並依 canonical rule 保留單側 0.5T。不存在真實交會時不得產生 relief。

驗收：

- 底板未命中 seam intersection 時維持完整 nominal blank。
- 命中時只有交會區被切除／退讓。
- 不得出現整條左、右、上、下邊都縮短的結果。
- 2D 與 DXF 的底板 CUTTING 必須相同。

### 4.6 Medium 文字

Medium 文字不可只透過降低字級解決。UI layout 必須讓字體尺寸、row height、padding、widget minimum size 與 canvas/layout geometry 一致縮放。

驗收：

- Medium 所有重要標籤在預設視窗尺寸可見。
- 不得因 clipping、row height 不足或 widget 寬度不足而消失。
- Small / Medium / Large 皆不得破壞既有操作。

### 4.7 封頭尾四向選擇框

TOP / BOTTOM / LEFT / RIGHT 的選擇 widget 可縮窄，但只能調整 UI layout 尺寸，不得修改 corner type 語意、geometry rule 或 relief registry。

驗收：

- 四向皆可辨識與點選。
- 窄化後不截斷必要文字／狀態。
- 選取結果與原本 geometry resolution 完全相同。

## 5. 資料流與介面要求

### 5.1 Authoritative state

推薦狀態流：

```text
User parameters / config
        ↓
Geometry + Topology + Factory Policy
        ↓
Resolved physical parts
        ↓
Assembly placement
        ↓
┌───────────────┬───────────────┐
│ 2D projection │ 3D assembly   │
└───────────────┴───────────────┘
        ↓
DXF / Save / Reload
```

3D 操作後：

```text
3D modified resolved state
        ↓
Complete workspace snapshot
        ↓
Authoritative session state
        ↓
2D projection / DXF
```

### 5.2 禁止雙重座標演算法

Geometry 與 assembly placement 必須只有一套 authoritative 座標定義。現有專案已具備共用 assembly geometry layer；本任務應將中隔、內門框及其他受影響零件納入該層，而不是再建立 GUI-only 或 viewer-only 的第二套算法。

以下方式禁止：

- 3D viewer 自己計算中隔位置、2D 再算一次。
- 2D 為了顯示中隔另造 fake polygon。
- DXF exporter 重新猜 3D placement。
- scene rebuild 使用 unknown part 的 `(0,0,0)` 作為有效 placement。
- 以 widget / canvas pixel 座標當製造幾何座標。
- 在一次遷移中直接刪除所有既有座標 workaround，卻沒有先建立 authoritative transform 並逐層替換消費者。

#### 5.2.1 大規模重構風險：座標演算法遷移

消除重複座標演算法本身是高風險重構。舊有 GUI、2D、3D、DXF 或 workaround 可能雖然架構上不應存在，卻仍暫時承擔既有行為；若一次全部刪除，容易造成「座標系統陣痛期」的大量回歸。

實作必須採**漸進式遷移**：

1. 先建立／確認 authoritative geometry + assembly transform contract。
2. 先讓單一 authoritative transform 成為新消費者的唯一來源。
3. 依 GUI → 2D → 3D → DXF／其他消費者逐層替換舊座標算法。
4. 每替換一層，保留並執行既有 regression tests，確認 geometry、placement、projection 與 collision 沒有偏移。
5. 舊 workaround 只有在所有消費者已遷移且測試證明不再需要後才能刪除。
6. 任何涉及 Geometry、Topology、Assembly placement、2D/3D sync 或 DXF 的遷移，視為高風險變更；不能只以局部 UI／單元測試判定安全，必須進入 Headless + GUI Gate 的完整驗證門檻。

驗收重點不是「新算法能算出一個位置」，而是**所有既有消費者最後都只剩同一個 authoritative placement source，且遷移過程沒有製造新的第二套座標邏輯**。

### 5.3 Complete workspace snapshot 的效能風險

3D → 2D 必須採完整、可還原的 resolved workspace snapshot，才能避免只回傳少數尺寸欄位而遺失 divider、frame、features、placements 或其他 3D 修改。然而完整 snapshot 若在互動期間反覆深拷貝、序列化或跨 UI 邊界傳輸，可能造成拖曳／操作延遲與 UI serialization/transfer lag。

因此 snapshot 的效能設計必須遵守：

1. **互動期間不做完整 snapshot 序列化**：拖動、旋轉、即時預覽等操作直接作用於記憶體中的 authoritative resolved state，不得每一幀 deep-copy 整個 workspace。
2. **Confirm 時才凍結 snapshot**：只有使用者確認 3D 修改時，才建立 immutable／stable 的完整 snapshot 作為 3D→2D 邊界資料。
3. **snapshot 不重新計算幾何**：snapshot 的責任是攜帶已 resolved 的 state；不得因建立 snapshot 又重跑一套 geometry algorithm。
4. **跨 2D/3D 邊界才序列化**：能以同一 process 的 authoritative object/state 傳遞時，不應無必要轉成大型文字或 JSON payload。
5. **保持完整性優先於過早壓縮**：第一版不得為了效能退回「只傳尺寸欄位」的 partial snapshot。若後續量測證實 payload 過大，才可研究 diff、lazy materialization、copy-on-write 或其他增量策略，但不得破壞完整可還原的語意。
6. **效能驗收與一致性驗收分開**：snapshot 的建立成本、UI response time、payload size 可量測，但不能以省略 authoritative state 來換取表面效能。

驗收至少包含：

- 3D 互動拖動期間不因每幀 snapshot 造成明顯卡頓。
- Confirm 後產生的 snapshot 能完整重建同一 workspace state。
- 2D apply 不需要重新猜測或補算 3D placement。
- Save/Reload 後仍能還原 snapshot 所代表的 stable ids、geometry、features、placement 與 structure。
- 若後續引入 diff／lazy snapshot，完整 snapshot 仍須可由 authoritative state 無歧義重建，且 round-trip 結果與完整 snapshot 相同。

## 6. 測試規格

### 6.1 中隔與 Assembly

新增／補強測試：

- divider placement contract
- divider stable id 在 resolve/rebuild 前後不變
- inner door lower frame 指向 shared divider
- 3D rebuild 不跳位
- assembly collision 使用同一 placement
- 2D projection 使用同一 placement

### 6.2 2D↔3D round trip

至少覆蓋：

```text
2D → 3D → Confirm → 2D
2D → 3D → modify divider → Confirm → 2D
2D → 3D → modify head/tail → Confirm → 2D
2D → 3D → modify structure → Confirm → 2D
2D → 3D → Save/Reload → 3D → 2D
```

驗收不是「畫面大致一樣」，而是比較 resolved state：stable id、geometry、features、placement、structure。

### 6.3 孔位

建立 hole provenance / surface contract 測試，確保每一個 feature 有合法 source、face、datum 與 family policy；禁止未知 feature 靜默落入 Receiving。

### 6.4 底板

至少測：

1. 無 seam intersection → full blank。
2. 單一真實 intersection → local relief。
3. 多個 intersection → 各自局部處理。
4. relief 不應改變 nominal outer dimension 語意。

### 6.5 UI

Medium text 與四向 selector 屬低風險 UI 修改時可先跑 targeted tests；若與 geometry／2D-3D sync 同一批變更，依高風險規則升級完整 Headless + GUI Gate。

## 7. 測試分級與回歸門檻

依已核准的 `phase6-release-packaging` 測試分級：

- 單檔小型 UI / 文字／style 且不影響核心行為：targeted test 或 syntax/import/static/direct quick check。
- 累積 5 個小修改，或 3 個以上相關 production modules，觸發完整回歸。
- Geometry、Topology、Factory Policy、solver、collision、2D/3D sync、DXF、Save/Reload、data format、core API 等高風險變更立即完整回歸。
- 完整 Headless + GUI Gate 成功後清除測試債。

Release 前仍必須跑相關完整驗證矩陣。

## 8. 實作順序

1. 完成中隔／內門框 assembly placement contract。
2. 補 2D projection 與 3D placement 共用資料來源。
3. 將 3D Confirm 升級為完整 authoritative workspace snapshot。
4. 完成 2D apply 與 round-trip regression。
5. 完整追溯封頭尾每一個 hole / feature，建立 provenance table，再決定 Receiving 的共享 policy。
6. 修正底板全域縮短為局部 seam relief。
7. 修正 Medium text layout。
8. 窄化四向 selector UI。
9. 跑高風險完整回歸與 GUI Gate。
10. 更新每日修改日誌、驗證證據與 release artifacts。

## 9. 完成判定

本任務只有在以下全部成立時才算完成：

- [ ] 中隔位置與組裝關係有正式資料模型。
- [ ] 中隔 resolve/rebuild 不跳位。
- [ ] 2D 能顯示中隔與必要 3D assembly information。
- [ ] 3D→2D 使用完整 authoritative snapshot。
- [ ] 2D→3D→2D round trip state 一致。
- [ ] 每一個封頭尾 hole / feature 都完成 provenance trace。
- [ ] Receiving 不再無條件複製 Vault 完整 hole policy。
- [ ] 底板不再因一般 seam relief 全域縮短。
- [ ] Medium text 在正式尺寸可見且不靠錯誤縮字補救。
- [ ] 四向 selector 變窄但功能與 geometry semantics 不變。
- [ ] 新增 regression tests 通過。
- [ ] 高風險完整 Headless + GUI Gate 通過。
- [ ] Git 備份、commit、修改日誌與 verification evidence 完整。

## 10. 非目標

本規格不在尚未追溯完成前直接指定：

- 中隔某一個新的製造尺寸常數。
- 封頭尾所有孔位的新 XY 數字。
- 未經 canonical reference 證實的 relief 常數。
- 以 GUI 顯示效果取代 authoritative geometry。

這些內容只有在程式、canonical rules、registry、既有基準檔與製造語意均追完後，仍有不可解決的製造規則缺口時，才列為需要人工確認的項目。
