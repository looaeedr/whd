---
whd_doc_role: REFERENCE
whd_contract: common-parts-quantity-2d-settings-requirements
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD｜共用自訂板件、互斥數量模式與 2D 設定整合規格

- **版本**：v1.5（雙向模式初始化與共用箱體設定定版）｜2026-10-09
- **狀態**：**施工需求定版／REFERENCE 文件**。原 OPEN-01～05、受電箱雙向模式初始化來源與數量模式共用箱體設定均已選定；自訂板件物理裝配及 17／100 的 source-level mapping 仍須憑正式來源核對；尚未施工、尚未驗收、尚未寫入 GitHub 倉庫。此處「定版」僅指需求規格，不表示已發版程式。
- **適用**：所有 WHD 箱型，包含受電箱與金庫型。
- **程式查核基準**：`looaeedr/whd`／`cleanup/2d-3d-sync`，SHA `535b726203d818772f781926ccd9b6eb50de62eb`。
- **歷版變更**：v1.3 將原 OPEN-01～05 正式轉為 CPR-13～17；受電箱數量模式為獨立單箱體／單 Bay（不是套／連轉換），每個「孔型版本」有自己的正整數「件數」，共用箱身與非封頭尾板件，獨立覆寫封頭／封尾 Feature；所有實際製造板件按每箱片數 × 各版本件數彙總，完全等價料件合併 DXF 並標大寫 `Q{加工片數}`。補齊 UI 選取／件數與 AC、舊檔讀回要求。
- **v1.4 修訂**：受電箱數量模式首次進入時 W/H/D 由操作者在專用單箱體對話框明確確認（可用受電箱 Family 預設值預填，非舊 Bay 推論）；Session restore／saved quantity project restore 不重問；`＋` 插入目前選取版本後，刪除一律確認；合法件數立即更新當前編輯狀態但不等於存檔；修正 AC 用詞、增加尺寸與暫存驗收。
- **v1.5 修訂**：補上只有數量模式存檔時首次反向進入套／連的獨立 1 套／1 連初始化及取消閘門；數量模式增加可持續編輯的**共用箱體設定**，明示 W/H/D、背板形式、內門層數、品牌等權責與正式預設；修正 OPEN-05、AC-19、CPR-13～20 的引用及兩個 Receiving legacy projection 函式的分工，追加 AC-28～32。

## 1. Problem Statement

1. 受電箱既有「套／連」設定視窗內的 3D 預覽與選取刷新連動，選擇設定項目、選連或高亮可能反覆產生 3D mesh、重建 Matplotlib 場景，造成卡頓。
2. 新增與箱身／封頭／封尾同層的自由命名板件，現有 Workspace 雖支援任意 identity 的保存形態，但新增 UI 只開放既有固定板件，製造解析器對未知板件會報錯，不能只加 UI 選單。
3. 所有箱型需可在相同箱身結構下生產多個成品，各數量的封頭、封尾開孔可以不同；受電箱原有套／連與數量不得混成同一套配置。
4. 加工時需要將真正相同的料件合併成一份 DXF 並標明應加工的數量，以免重複檔案或漏件。

## 2. Confirmed Product Rules

以下列使用者已確認的需求及本輪定案的五項產品選擇；保留技術方案與產品規則的分界。訪談問答代碼統一為「D-1～D-8 決策題」；DXF 標註一律使用大寫 `Q{加工片數}`，不把二者混用。

| ID | 確認規則 |
|---|---|
| CPR-01 | 受電箱設定操作要減少卡頓；先選要修改的項目，才啟用高亮選取與編輯。 |
| CPR-02 | 全部箱型都能新增自由命名的自訂板件；它與**箱身、封頭、封尾同一頂層**，不在箱身或套／連下面。 |
| CPR-03 | 自訂板件預設**包外 17／100**；**X、Y 擇一作為折法方向，另一方向的尺寸由使用者輸入**。不自行猜測板件在組合體中的安裝位置。 |
| CPR-04 | 全部箱型（含受電箱）提供**數量模式**及設定入口；它由一個共同箱體設計製作多種封頭／封尾**孔型版本**，每版本有自己的製造**件數**。介面不得把版本數誤標為總件數。 |
| CPR-05 | **受電箱「套／連模式」與「數量模式」是兩套獨立操作，必須二擇一，不能同時啟用或將數量算進套／連。**其他箱型使用數量功能。 |
| CPR-06 | 按「＋孔型版本」時從**目前選取版本**複製封頭／封尾 Features；新版本立即獨立、不共用可變物件，且新增後自動成為目前選取版本。這是原「複製前一個」的正式操作語意。 |
| CPR-07 | **僅**受電箱原本「套／連」設定視窗內的 **3D 圖改成 2D 平面圖**；新增的「數量設定」也使用 2D。**其他主畫面 3D、板件功能與其他設定不在本次 2D 替換範圍。** |
| CPR-08 | 模式切換保留另一模式的設定，**但只在目前程式執行期間記憶體暫存**，切回可恢復；不自動將兩模式永久存入同一專案。 |
| CPR-09 | **手動存檔只保存當下啟用的模式**；想保留另一模式，須切換過去自行另存專案；關閉後未另存的模式暫存不恢復。DXF 只依目前啟用模式製造。 |
| CPR-10 | **真正相同的料件合併成 1 份 DXF**，製造數量為該群料件的總數；不同開孔或其他影響加工的差異不得合併。 |
| CPR-11 | 每份合併的料件 DXF 要有**大寫 `Q` 加數字**，例如 `Q5`／`Q10`，在 **`CHECK` 圖層**，位置優先為料件中心。**禁止小寫 `q`**；不能寫入 `CUTTING` 或製造打標 `MARKING`。 |
| CPR-12 | `Q{加工片數}` 文字與孔洞／加工圖元衝突時**自動避讓**到可清楚閱讀位置，以中心優先；此動作只改檢查文字，不改切割、開孔、折線或打標幾何。 |
| CPR-13 | **受電箱數量模式**只處理**一個獨立單箱體／單 Bay 製造基準**；不採用、不轉換、不繼承切換前套／連的任意多套／多連組合；數量模式不提供多連製造。本模式可在記憶體切回原套／連模式而完整恢復其資料。 |
| CPR-14 | **每個孔型版本代表一組相同封頭／封尾 Features 的製作需求**，並有「該版本件數」正整數欄位，初始值 1；**總件數＝所有版本件數加總**，不是版本筆數。 |
| CPR-15 | 所有實際出現於單箱體正式 BOM 的物理板件，按其**每箱片數 × 該版本件數**累計；包括箱身各分件、背板、門、底板、其他既有板件與頂層自訂板件。自訂板件另有「每箱片數」正整數設定（建立預設 1；未納入箱體者不得虛構數量）。 |
| CPR-16 | 同一數量模式內各孔型版本**只允許封頭／封尾開孔／Feature 差異**。箱身、封頭／封尾外形與折法、W/H/D/T、Corner／Relief、組裝結構及其餘板件均引用共同箱體；若要不同外形或結構，必須建立另一個產品／專案，而非另增孔型版本。 |
| CPR-17 | 「＋」複製**目前選取版本**，新項**插在來源版本之後**並自動選取；「－」刪除目前選取版本，**每次刪除皆要求確認並可取消**；至少保留一個版本，stable ID 不得復用。合法件數修改**提交至當前編輯狀態即時更新**總件數／DXF Q 預覽，但**不等於 `.p6fold` 已存檔**。 |
| CPR-18 | 受電箱**首次建立數量模式單箱體**時，開啟 W／H／D 尺寸確認視窗；可預填受電箱 Family 正式預設 W800／H1600／D350 mm，但只有使用者明確確認有效尺寸才建立獨立單 Bay 基準與首筆孔型版本。不得從舊套／連任一 Bay／Joint 推論。切回 Session 既有數量模式或載入已存的數量模式專案直接恢復其尺寸。取消／非法輸入不得切換或改動原模式。 |
| CPR-19 | **反向首次切換**：若載入的受電箱專案只有**數量模式**，而本次程式執行尚無套／連 Session buffer，首次切入套／連模式只能由明確確認的 W／H／D **新建獨立一套、一連**（1 Set × 1 Bay、0 Joint）；可預填受電箱 Family 正式預設 W800／H1600／D350 mm，禁止默默複製數量模式箱體／Features 或用已不存在的歷史 Bay 代替。取消／非法尺寸不切換、不修改數量模式。已存套／連專案或本次 Session 已有合法套／連暫存時直接恢復，不重建。 |
| CPR-20 | 受電箱數量模式需有**共用箱體設定**（所有孔型版本共同引用），至少提供 W／H／D、背板形式、內門層數，以及既有單箱體會影響 BOM／製造的合法共同設定入口（含開關品牌等適用項）。新建時背板形式 `FULL`、內門層數 `1`、品牌 `士林` 依現有正式預設初始化；其他設定遵守相應 Family authority／正規化，不從切換前任一 Bay 複製。W/H/D 在首次確認後仍可修改；共同變更作用於**所有版本**並重新驗證 Features／BOM，不能形成逐版本外形差異。 |

### 2.1 互斥模式與暫存的正式語意

- **套／連模式**：使用既有 `receiving_layout.sets[]/bays[]/joints[]` 及每連設定，保留目前套數、連數、品牌／接合等語意。
- **數量模式**：單一共用箱體，依封頭／封尾開孔切分「孔型版本」，每版本有獨立 Features 與正整數件數；受電箱以**獨立的單 Bay 製造 base**解析，但不顯示／啟用套／連操作，也不引用切換前多套多連結構。**首次切入必須先明確確認 W/H/D，已有 Session 暫存或合法存檔才可直接恢復。**
- **切換**：`active_mode` 在介面上只能是其中一個，暫存前一模式資料供本次程式執行內切回；**暫存不是持久化**。任一方向若對方模式的 Session buffer 不存在，必須走該方向的獨立初始化：進數量依 CPR-18、反向進套／連依 CPR-19；完成確認前不得提交模式切換。
- **Save / Save As**：只將當下的 `active_mode` 和該模式所需權威資料寫入該專案；不把另一模式暫存夾帶進去。切到另一模式後若要保留，使用者自行另存不同專案檔。
- **Load / Restart**：只從所載入的專案還原其已保存模式；另一模式不憑空復活、也不得將上一個程式階段的暫存偷帶進來。由已保存數量模式首次進入套／連時，需建立新的獨立 1 Set × 1 Bay，**不可直接用前一模式的單箱體當作既有套／連存檔資料**。模式切換及未保存變更是否提示，以既有未存檔確認機制處理。
- **受電箱切換模式不等於修改已保存的套／連組裝幾何**；作用中模式的製造輸出須明確單一化。

### 2.2 數量例子及 CHECK

假設有**2 個孔型版本**：版本 A 的件數為 3、版本 B 的件數為 2。兩版本共用相同箱體及其所有非封頭尾板件；封頭孔型 A/B 不同，封尾孔型 C 相同。**總件數＝5**。

| 合併後料件 | 匯出檔案數 | 標註於 CHECK 層 |
|---|---:|---|
| 同一個箱身料件（加工幾何全同） | 1 | `Q5` |
| 封頭孔型 A | 1 | `Q3` |
| 封頭孔型 B | 1 | `Q2` |
| 封尾孔型 C | 1 | `Q5` |

此例為邏輯示意。實際合併必須使用**每片正式物理料件**的完整製造結果比對，而非僅憑名稱、箱身外觀或成形包外尺寸判等。

## 3. Current State / RED Evidence

| 實際程式／測試 | 已確認的實作事實 | 本需求對應 |
|---|---|---|
| `gui_modules/application/receiving_set_bay_controls.py` | 每連設定 `refresh()` 呼叫選取後回呼；原設定視窗執行 `_render_preview()` 時清除 3D axes、逐連呼叫 renderer 並重掃三角形。 | 套／連設定改為 2D；選取不觸發昂貴 3D 全重繪。 |
| `gui_modules/application/receiving_set_bay_adapter.py` | Receiving 原 UI「套／連」Facade 使用正式 ReceivingSetBayAdapter 的 `set_count/bay_count`。 | 不可用它假裝數量。 |
| `ae_engine/receiving_shared_settings.py` | `head_features`、`tail_features` 已分開，具 `edit_setting`、`share_setting`、`unlink_setting`，並深複製 Feature 值。 | 原套／連功能沿用；數量獨立值複製，別重建 Hole Editor。 |
| `phase6_navigation_view_adapter.py`、`fold_designer_bridge.py` | 現有「新增 ▼」選單、頂層導航，但 `_fix11_add_part` 僅接受 `PART_LABELS` 固定鍵。 | 頂層自訂板件擴充既有入口。 |
| `phase6_workspace_state.py`、`phase6_designer_workspace.py` | Workspace 支援 `existing_parts` 與未知 identity 的 presence、profile、feature stash。 | 不另造板件顯示列表。 |
| `gui_modules/application/fold_designer_manufacturing_projection.py` | 未知板件在 `_fold_designer_part_spec_from_payload` 結尾報「未知 3D 板件」。 | 自訂板件須接到正式制造 geometry resolver。 |
| `phase6_settings_profile_projection.py` | 一般未知板件的 fallback X/Y 目前使用 `25 / 主尺寸 / 25`，不是本次指定的 `17／100`。 | 新自訂板件預設必須特別由合法 Fold semantics 建立，不能沿用 fallback。 |
| `phase6_hole_editor_canvas_view.py` | 已有利用正式 surface／reference guide 的 2D 編輯 Canvas。 | 2D 設定圖應盡可能沿用既有 Hole Editor 和座標投影。 |
| `phase6_project_file.py` | `.p6fold` 目前 v1／受電箱 v2 專案由 snapshot 保存 authority，derived geometry 不存。 | 新增單一作用中模式的保存與舊案兼容。 |
| `ae_engine/manufacturing_export.py` | 現有 batch DXF 可依 instance namespace 逐件輸出，**未實作相同物理料件 dedup 與加工數量歸併**。 | 新增製造等價分組與 Q 標記。 |
| `ae_engine/sheetmetal_drawing.py`、`ae_engine/dxf_serialization.py` | 已有 `TextPrimitive` 與 `CHECK` 圖層（Color 2／CONTINUOUS）；目前 `_check_text()` 預設放在料件上方。 | 額外新增「中心優先、碰撞避讓」的 Q 文字投影，而不是沿用上方位置。 |
| `tests/test_issue1331_receiving_shared_settings.py` | 現有測試已涵蓋每連獨立／共享開孔、DXF、Save→Reload。 | 新增測試不得破壞原行為。 |
| `ae_engine/receiving_shared_settings.py`、`ae_engine/cabinet_types/receiving.py`、`ae_engine/receiving_switch_layout.py` | 單 Bay 共用設定預設已有 `back_panel_mode=FULL`、`inner_door_layers=1`、封頭尾空 Features；Receiving Family 的 W/H/D 預設 800／1600／350；開關品牌列表首項為士林。 | 共用箱體新建使用這些現有正式預設，不得從他模式移轉；其他共同欄位仍由相應 Family／設定 authority 決定。 |
| `ae_engine/receiving_layout.py` | `project_primary_bay_legacy_aliases()` 是 Set1/Bay1 的載入相容包裝函式；`project_receiving_bay_legacy_aliases()` 可指定 Set/Bay，兩者均投影暫時的 W/H/D/Features。 | 兩個函式皆存在且職責不同，不得用其轉換舊模式的 runtime alias 為另一模式的初始製造真值。 |

**可見現況不等於已上線新功能：**頂層自訂板件完整輸出、受電箱互斥數量模式、DXF 自動合併及 `Q` 文字均尚未由以上程式證實已實作。3D 設定重繪路徑存在，但效能耗時比例仍需真 GUI profiling。

## 4. Solution / 功能規格

### 4.1 受電箱套／連設定視圖及效能

- 原套／連設定的**預覽區**由 3D 改成 **2D 平面圖**，保留既有每連設定（背板、封頭孔、封尾孔、內門層數、尺寸、接合）所需控件及操作權限。
- 先指定修改項目，才啟用對應的 2D 選取／高亮；未選項目不可默默把點擊當成設定修改。套用才提交，取消不得污染正式製造狀態。
- 切換選取與高亮只更新 display/overlay；不得對等價幾何重跑 full manufacturing resolve／DXF reread；正式修改透過既有 Scheduler 進入唯一計算通道。
- 不影響主畫面的 3D、3D 組合檢視、正式 2D／DXF 來源。

### 4.2 頂層自訂板件

- 在現有頂層「新增 ▼」內提供自訂板件；新增後與「箱身／封頭／封尾」平行排列，可多片、自由命名、改名、刪除及重新載入。
- 以不可重複的 stable physical ID 與顯示名稱分開保存；不以中文顯示名稱直接當作製造識別或 DXF 名稱。
- 預設「包外 17／100」：**操作時選擇 X 或 Y 作為折法方向；另一個軸由使用者輸入尺寸**。17、100 的 profile row、折邊朝向和 2D 展開補正需按實際既有 Fold authority 對映，不能發明另套算法。
- 不自動猜測未提供的成形尺寸、板厚、接合面或 3D placement；缺必要製造資料時阻止生成虛假的 DXF，待完成合法指定後才輸出。
- 接入既有 Workspace／Hole Editor／Manufacturing／Save／Reload；不能僅在導航樹顯示名字，也不能另造一個獨立幾何運算引擎。

### 4.3 數量模式：孔型版本、件數與獨立性（正式產品規則）

- 所有箱型提供「**數量模式**」；其中 `孔型版本` 表示一組封頭／封尾孔位設定，`件數` 表示這個版本要製作幾套相同箱體，`總件數` 表示各版本件數之和。**版本數 ≠ 總件數**；例如版本 A 30 件、版本 B 20 件，是 2 種版本、50 件，不用建立 50 個版本。
- 數量模式最少一筆孔型版本；每筆具有不可重複且持久化的 `version_id`、正整數 `piece_count`（初始 1）、獨立 `head_features`／`tail_features`。每次新增先深複製選取版本的 Features，之後任何版本內修改不連動其他版本。
- 受電箱只能在「套／連模式」與「數量模式」間互斥切換；數量模式的箱身只由**單箱體產品基準**提供，不把先前套／連的 N 套 M 連配置轉成一組產量。
- 所有版本的共用箱體尺寸、結構與折法只有一份 authoritative owner；每個版本只是該箱體的**封頭／封尾 Feature overlay**和製造需求件數，不能有另外一份 W/H/D/T 或板件外形。
- 2D 設定頁先選孔型版本、封頭／封尾，再使用既有 Hole Editor 的正式 feature-surface／anchor 語意。只選取／高亮時不得重新建立 3D 全場景；套用才提交，取消不污染正式值。
- Legacy 相容：非受電箱的既有無數量欄位專案以**一筆版本、件數 1**載入；受電箱舊檔維持**套／連模式**，不得藉 migration 偷改成數量模式。

### 4.3.1 共用／覆寫邊界（已定案）

| 資料項 | 正式責任歸屬 | 各孔型版本能否不同 |
|---|---|---|
| 箱身結構／分件、W/H/D、T、Fold、裝配與 Joint | 共用箱體 authority | **不能** |
| 封頭、封尾實際成形外形、折法、Corner／Relief Policy | 共用箱體 authority | **不能** |
| 封頭 Features（孔位等） | `version_id` 對應的獨立清單 | **可以** |
| 封尾 Features（孔位等） | `version_id` 對應的獨立清單 | **可以** |
| 背板、門、底板、其他正式物理板件之幾何／Features | 共用產品/BOM authority | **不能** |
| 自訂板件之存在、幾何與「每箱片數」 | 共用頂層板件/BOM authority | **不能**，但仍隨版本件數計算數量 |
| 每個孔型版本的 `piece_count` | 該版本產量資料 | **可以** |

### 4.3.2 共用尺寸變更與 Feature Anchor

- 當箱體 W/H/D/T／Fold 變更，每個版本必須重新引用當前共同箱體以及封頭／封尾 finished-face guide，將保存的 `FeatureAnchor`、offset 與特徵形狀參數重新解析；**不得保存、復用過時 2D pixel／絕對展開座標**。
- 新尺寸可能使一個版本的孔位越界／干涉。遇到不合法 Feature 必須指出 `version_id`、端別（封頭／封尾）與 Feature identity；禁止靜默位移、刪孔、合併或輸出有誤 DXF。
- 如果修改尺寸會產生新的**封頭外形差異需求**，那已超過數量模式可覆寫的 Feature 範圍，必須分開建立另一種箱體，不得悄悄創建逐版本外形。

### 4.3.3 受電箱數量模式箱身（原 OPEN-01，已確認方案 A）

- **製造拓撲就是單一箱體**；與現有 Receiving 的一個完整 Bay 實體板件定義相容，必要時由既有單 Bay resolver 建立該模式的專用 base。此處「單 Bay」只是允許復用現有正式幾何能力，不代表介面仍顯示套／連或建立可操作的額外 Set/Bay。
- **不做**：把現有套／連 2 套 3 連誤解為 6 個「數量」；取套／連選取的某一連冒充數量箱身；將多連 Joint 帶入數量；讓兩模式同時輸出製造料件。
- **首次建立單箱體（含由舊受電箱套／連專案第一次切入）**：必須先顯示「數量模式單箱體尺寸」對話框，以明確標記為「受電箱 Family 預設」的 W=800、H=1600、D=350 mm 作**可編輯的建議初值**，不得冒充原專案量測尺寸，也不得自動採用。操作者確認後才把其指定的合法正尺寸提交成數量模式的**共用單箱體 authoritative W/H/D**；相依 T/Fold/Corner/Relief 沿用符合 Family 的正式規則，不能從套／連選取的任一 Bay／Joint 取得。此初值來自 `ae_engine/cabinet_types/receiving.py::BOX_BODY_DEFAULTS`，不是任何暫存 Bay。
- **確認閘門**：關閉對話框、按取消、W/H/D 不完整、非數值或非正數時，不切換模式、不建立單 Bay、不建立孔型版本、不改套／連資料；不能用零值、隱式 fallback 或未經確認的預設偷渡製造幾何。尺寸確定後建立**一個**獨立單箱體及初始一筆孔型版本（件數 1）；所有版本共用該 W/H/D。
- **切回既有數量模式**：若本次執行期的 Session buffer 已有合法單箱體與版本，直接無損恢復原尺寸／孔位／件數，不再以 Family 預設覆蓋，也不重新詢問。**讀取已存的數量模式 `.p6fold`** 亦直接恢復其專屬單箱體權威尺寸，不套用 Family 預設。
- **舊檔與保存**：舊受電箱檔案未有數量模式單箱體資料，載入仍以套／連模式呈現；首次使用上述確認視窗建立新資料。手動保存僅保存目前啟用模式；另一模式只保留當次執行的記憶體暫存。套／連資料放在 Session 暫存，切回時完整還原；**只有數量模式存檔、沒有套／連暫存時則必須另行初始化 1 套／1 連**（CPR-19）。
- **正式製造驗證**：透過獨立單 Bay 相容 resolver 確認完成箱體的有效幾何與 Family 約束，再准許 2D 編輯及 DXF；任何幾何驗證失敗應保留原模式／編輯資料並報錯，不能以範例尺寸替代。
- 使用者如要多連／多套受電箱，須使用**套／連模式**；本期數量模式不提供多連箱體不同孔型的批量版本。

### 4.3.4 「＋／－」及件數欄位（原 OPEN-02、05，已確認）

- `＋孔型版本`：取**目前選取**的版本深複製 head/tail Features；配置新 stable ID、件數初始 **1**，**插入目前選取版本的緊後方**並**自動選取新版本**。因此連按 `＋` 時，下一次複製來源就是剛新增的版本，列表順序可預測；顯示序號與 stable ID 分離，插入／刪除不改寫其他版本 ID。
- `－孔型版本`：刪除**目前選取**版本，**不論是否曾保存，每次都要求確認且可取消**；**最後一個版本不可刪**。刪除後優先選取原位置的下一版本，若沒有下一版本則選取前一版本；不重用任何 stable ID。刪除後資料先變更於本次編輯狀態，只有手動 Save 才寫入專案檔；取消刪除完全不改狀態。
- `件數`：目前選取版本的正整數（最少 1）。**合法輸入經確定／失焦驗證後，立即提交到目前記憶體編輯狀態**，更新畫面總件數及待輸出 DXF `Q` 計算；**絕不因此自動寫 `.p6fold`**。未確定／非法輸入不覆寫原值；視窗未存檔提示只反映「編輯狀態與磁碟最後存檔不同」，不可把「即時生效」誤認成「已持久化」。
- `總件數`：所有版本 `piece_count` 加總的只讀值；畫面同時顯示「版本數」，避免把 `N` 誤讀成總件數。**列表順序只控制使用者呈現與選取，不作 DXF 唯一識別或加工等價鍵**；不同料件輸出由 stable ID／正式等價群鍵產生確定性的穩定檔名與序列順序，避免在中間插入版本使不相關 DXF 全部改名。

### 4.3.5 其他板件與自訂板件 BOM（原 OPEN-03，已確認）

- 從**正式製造實體板件清單**及其 per-box multiplicity 統計，包含箱身分件、背板、門、底板、中隔及自訂板件；不以硬編碼三類（箱身／封頭／封尾）來計數。已不存在於該箱體的板件不應產生 DXF 或 Q。
- 對每個版本 i（件數 `k_i`），每一正式物理板件 p 的需求為 `k_i × m_p`，其中 `m_p` 為單箱體 BOM 中該板件的片數。跨版本製造完全等價時，再將所有 `k_i × m_p` 相加作為 DXF 大寫 Q。
- **自訂板件**：在頂層板件設定提供「每箱片數」，正整數，初始 1；該板件不屬於箱體（未啟用／已移除）時，不納入 BOM。自訂板件的份數為每箱片數，不要誤認為孔型版本數；若需要多張不同幾何的加強板，應建立不同板件 identity，而非將其混作同一類料件。
- 一個箱體若有兩片不同箱身分件，其 Q 應逐片分別合併；無法證明是相同實體板件的項目不可只因名稱相近就歸併。

### 4.3.6 雙向首次切換及數量模式「共用箱體設定」（v1.5 新增）

**A. 由已保存數量模式首次切回套／連，且沒有 Session 暫存時**

1. 使用者明確選擇「套／連模式」後先開啟「建立套／連基準」對話框；預告將建立**新的 1 套、1 連、無 Joint**，不會搬移當前孔型版本或其孔位。
2. W/H/D 輸入欄以受電箱 `BOX_BODY_DEFAULTS` 的 W800/H1600/D350 作**可改且清楚標示來源的建議初值**；不得當成數量專案的原箱尺寸或從數量模式的目前共用 W/H/D 偷帶值。**必須使用者確認有效尺寸**後才呼叫正式 1 Set × 1 Bay 建立與 Family normalization；未確認前不改 `active_mode`。
3. 初始化背板 `FULL`、內門層數 `1`、品牌 `士林`、封頭尾 Feature 空清單，其他共用設定使用正式 Family／normalizer 已有預設。**不移植**數量模式的 version Features、件數、1x1 共用箱體修改或不存在的舊套／連 Joint；模式仍各自獨立。
4. 使用者取消、關閉視窗、W/H/D 非正數／非法或 Family 幾何無法有效解析時，維持作用中的數量模式及完整編輯狀態（含未存檔件數）、不產生假 Set/Bay；若本次 Session 已有合法套／連資料，切回時**直接恢復暫存**而不是建立新 1x1。
5. 此首次建立不代表自動另存套／連；**只有手動 Save／Save As** 才把當前作用中套／連寫入 `.p6fold`。若反向前曾有不同套／連另存檔，必須由使用者另行開啟那份檔案，不能從當前數量專案猜測其內容。

**B. 數量模式的共同設定入口與預設**

- 在數量模式「孔型版本列表」**上方**固定提供 `[共用箱體設定]`；不需要選孔型版本即可進入，與下方目前版本 `[封頭孔]／[封尾孔]` 的 2D 編輯責任完全分離。設定視窗沿用既有單箱體 Family 合法欄位及 2D view，不額外開整個 3D 預覽。
- 共用欄位**至少**涵蓋：W／H／D（首次人工確認後仍可在此重新編輯）、背板形式（`FULL`／`HALF`／`BACK_OPENING`）、內門層數（1／2）、開關品牌，以及影響該單箱體 BOM／門分割／板件存在與製造的其他既有共同設定；不憑空創設新的製造數值或獨立設定引擎。
- **初始值**：W／H／D 僅由 CPR-18 的人工確認取得；`back_panel_mode=FULL`、`inner_door_layers=1` 與品牌 `士林` 依 existing Receiving defaults；其餘共用參數按其正式 Family defaults／正規化。**不取套／連任一 Bay 的背板／內門／品牌或孔位**。封頭／封尾的各版本 Features 另由孔型版本 owner 保存。
- **變更生效**：共同參數經合法確認後更新唯一共用箱體 editing state，所有孔型版本及其 BOM、預覽、DXF 待輸出結果一起更新；**不會建立逐版本背板／內門／W/H/D**。W/H/D 改變時每個版本所有 FeatureAnchor 依 §4.3.2 再解析；若有任何一個版本越界／失效，拒絕不合法 DXF 並指出版本／端別／特徵，不能默默略過。
- **保存**：共用箱體設定與作用中孔型版本共同保存於當前數量模式 `.p6fold`；未按 Save 仍只是編輯狀態。已載入合法的數量專案時不覆寫其共同設定為 Family 預設。套／連模式保持原本每連設定與獨立的保存權責。

### 4.4 製造輸出合併及 `Q` 的 CHECK 文字

- **合併粒度**：逐片正式製造物理料件，不因箱體組合不同而誤把不相同板件併在一起；比較須包含保留下料輪廓、所有 CUTTING 開孔／切口、BEND、影響加工的 MARKING／製造註記、適用板厚／材料／製程規則等。不可只比 `bbox`、檔名或孔數。
- **數量統計**：以每筆孔型版本的 `piece_count` 乘以該實體料件的 `per_box_count`，跨版本依加工等價性分群；每一相同料件群僅輸出單一 DXF，群內實際待製造片數加總為 Q 值。不同料件各輸出一張。
- **CHECK**：為合併後單張 DXF 新增大寫 `Q{正整數}`，如 `Q1`、`Q5`；寫入既有 `CHECK`，不改 layer 顏色、線型，不寫入 `CUTTING` 或 `MARKING`。用現有 `TextPrimitive`／正式 DXF serializer。
- **定位**：Q 文字首先置於料件中心附近的合法可讀區；遇開孔、割線、折線、打標或其他文字碰撞則依確定性規則自動避讓；不得修改實體幾何或藏到孔裡。中心可用位置的選擇只用正式 2D material／source feature 結果，不能從 3D 畫面 bbox 或 raw GUI 座標反推。
- **避免污染等價判定**：製造料件等價比較必須**排除 Q 自身與非加工顯示文字**，先分群再生成 Q；改 Q 不應造成切割幾何差異。檔名能穩定區分不同製造料件，DXF re-open 必須確認 Q 文字符合群數量。
- **模式範圍**：只按作用中模式匯出；不混入記憶體中未啟用模式。若批次全套輸出，遵循所選模式正式輸出範圍。

### 4.5 UI 草圖（結構示意；正式術語已更新）

```text
受電箱｜操作模式： (● 套／連)  (○ 數量)   ← 嚴格二擇一

套／連模式（原功能）：
    [－套] [＋套]    第 N 套：[－連] N [＋連] [設定]
    設定內：2D 平面圖（原 3D 預覽改用 2D）

數量模式（受電箱為單箱體；其他箱型也使用同款控件）：
    首次切入：單箱體尺寸 [W: 800] [H: 1600] [D: 350] mm  [確認] [取消]
              ↑ 受電箱 Family 預設僅供參考，可修改；未確認不建立箱體
    [共用箱體設定]   ← 不依賴版本選取，可再次修改 W/H/D、背板、內門、品牌等
      W：[900] H：[1700] D：[400] mm   背板：[全板▼]  內門層數：[1▼]
      開關品牌：[士林▼]  其他原有單箱體共同設定…    [套用] [取消]
      ↑ 這些是各版本共用的資料；各版本不能自行改外形／背板／內門
    孔型版本   [－版本] [＋版本] [設定]
    ● 版本 1     件數：[30]  [封頭孔] [封尾孔]
    ○ 版本 2     件數：[20]  [封頭孔] [封尾孔]
    版本數：2     總件數：50     ← 兩個欄位明確分開
    [設定]：目前選取版本之封頭／封尾 Features，2D 平面編輯
    +：複製目前選取版本（新件數 1）、插在它後面、自動選取新版本
    -：刪除目前選取版本（每次都需確認；不能刪至 0）
    件數：確定合法值後立即更新畫面／DXF Q 計算；仍須手動 Save 才持久化

反向首次切換（已載入數量模式專案，且沒有套／連 Session 暫存）：
    [切至套／連] →「將建立獨立的 1 套／1 連；不複製目前孔型」
    W：[800] H：[1600] D：[350] mm  ← Family 預設僅作可編輯初值
    [確認建立] [取消]  → 確認後 1 Set × 1 Bay、0 Joint；取消留在數量模式
    已有套／連 Session 暫存則直接恢復，不跳出首次建立對話框

頂層板件導覽（不巢狀於箱身或套／連）：
    箱身 / 封頭 / 封尾 / 其他既有板件 / 自訂板件 1 / 自訂板件 2 / 新增 ▼
    自訂板件設定：名稱／折法 X 或 Y／另一軸尺寸／每箱片數：[1]

DXF 相同料件合併後：CHECK 層中心優先，碰到孔位才避讓，例如 Q50
```

術語必須固定：**「數量」只用於模式名稱**；列表單位稱「孔型版本」，版本的產量稱「件數」，加總稱「總件數」；DXF 的大寫 `Q` 是**該張物理料件應加工的片數**，不一定等於總箱體件數。「編輯狀態即時生效」是 session/working state，不是已保存到磁碟。

### 4.6 已定案的五項產品分支（原 OPEN-01～05）

| 原代碼 | 定案 | 主要規格／驗收 |
|---|---|---|
| OPEN-01 | **A：受電箱數量模式為獨立單箱體／單 Bay**，不轉換／不繼承套／連的多套多連結構；首次必須人工確認 W/H/D。 | CPR-13／18、§4.3.3、AC-15／16／21／25／26 |
| OPEN-02 | **B：每一孔型版本附正整數件數**，初始 1；版本數與總件數分別顯示。 | CPR-14、§4.3.4、AC-05／20／22 |
| OPEN-03 | **完整 physical BOM × 件數**；自訂板件另外設定「每箱片數」，預設 1。 | CPR-15、§4.3.5、AC-17／23 |
| OPEN-04 | **只覆寫封頭／封尾 Feature**；尺寸、外形、折法及其餘板件共用。 | CPR-16、§4.3.1、AC-18／24 |
| OPEN-05 | `＋` 複製目前選取版本、插在來源後並自動選取；`－` 刪目前選取版本，**每次都要求確認**且最低保留一項（與是否存檔無關）。 | CPR-17、§4.3.4、AC-05／19／22 |

**狀態：五項原 OPEN 與 v1.5 兩個模式切換／共同設定產品分支均已定案，不再作為 OPEN。** 實體 placement、折法 segment 對映與 performance profiling 屬仍需由合法製造資料／程式驗證的工程工作，不能推定已有解答。

### 4.7 數量衍生與 DXF 分群（設計不變式）

- 以正式 **physical part identity** 和 BOM 的「每箱片數」計數；含各片真實 BoxBody 分件／內門／中隔／自訂板件，而非僅箱身／封頭／封尾。**不存在的板件不產生需求**。
- 每個版本 i 的需求係數 `k_i=piece_count`（正整數）。若該箱體需 m 片某物理料件，當版本 i 被製造 k_i 套時需要 `m×k_i` 片；先展開需求，再以相同製程參數及完整幾何比對跨版本 dedup。
- 僅封頭／封尾 Features 可以使版本間料件不同；沒有 Feature 差異的箱身、門、背板、自訂板件等按 BOM 共用設計後可跨版本累計 Q。任一板件若幾何、材質、厚度或加工層不同，不可誤併。
- Dedup 前排除 `Q` 與顯示用 CHECK 註記本身，分群完成才插入大寫 `Q{片數}`；位置中心優先並合法避讓。`Q` 的字高與版面不得進入製造等價鍵。
- 數量模式與套／連模式絕不混合輸出；非受電箱的舊檔按一個版本、件數 1，相容載入並允許調整。

## 5. User Stories

| ID | 情境 | 可觀察結果 |
|---|---|---|
| US-01 | 受電箱在套／連設定切換封頭孔，選第 2 連。 | 2D 正確標示該連的封頭孔，選取不重建 3D。 |
| US-02 | 受電箱先設套／連，切到數量，再切回。 | 同一程式執行內回復套／連修改狀態，不會被數量覆蓋。 |
| US-03 | 受電箱儲存數量模式，退出再載入。 | 載入所存的數量模式；之前未另外存檔的套／連暫存不復原。 |
| US-04 | 兩個孔型版本：版本 1 件數 1、版本 2 件數 2；版本 2 的封頭孔不同。 | 箱身結構完全共用；僅第二版本孔位不同；箱身合為一張 `Q3`，封頭依孔型分開。 |
| US-05 | 新增「加強板」，折法用 Y，X 輸入尺寸。 | 與箱身、封頭、封尾同層，Fold/2D/DXF 有真實板件資料。 |
| US-06 | 正中心有孔。 | `Q3` 自動移到合法可讀位置，孔位、切割及打標全部不變。 |
| US-07 | 受電箱已編輯 2 套各 3 連，切換到數量模式。 | 數量模式只有獨立單箱體，不會生成 6 個版本／多連 Joint；切回套／連完整恢復。 |
| US-08 | 50 個箱體，僅封頭兩種孔型，分別 30 與 20 件。 | 兩個孔型版本即可製造 50 件；所有相同實體板件只輸出一份並標正確 Q。 |
| US-09 | 新增每箱 2 片相同的「加強板」。 | 板件保持頂層 identity；總箱體件數 50 時，相同加強板的 DXF 標 `Q100`。 |

## 6. Implementation Decisions（實作建議；非新產品真值）

1. **資料隔離**：對受電箱建立互斥 `active_mode`；另一模式為**in-memory session buffer**，不得加入正式持久化 snapshot。切換作用中模式時從 mode buffer 做無損深複製／恢復，不能共用 mutable Feature 參照；首次建立數量模式要在 W/H/D 明確確認後才 commit mode switch。
2. **儲存範圍**：對 `.p6fold` 延伸或版本化 snapshot，儲存單一作用中模式與其完整 authority；保留舊專案 migration，不以 mode buffer 當製造真值。切換到數量模式時不得先刪除正在記憶體暫存的套／連資料。
3. **版本資料模型**：建議採 immutable/stable `version_id`／正整數 `piece_count`／獨立 `head_features`／`tail_features` 與共用箱體 ID；`＋` 對選取版本 deep copy Features 並給新 ID。**`version_id` 為建議欄名，不是既有上線 schema。**受電箱只透過獨立單 Bay 解析單箱體，不擴增正式套／連 topology。
4. **自訂板件**：以既有 `Phase6DesignerWorkspace`、navigation、Fold profile、features、manufacturing resolver 連通，而不是繞過 `_fold_designer_part_spec_from_payload()` 的未知板件例外。
5. **合併製造**：按正式 BOM `per_box_count × version.piece_count` 展開實際片數，從既有 `ResolvedManufacturingGeometry` physical parts 建立 deterministic manufacturing-equivalence key，對每組只序列化一次，最後以 CHECK TextPrimitive 插入大寫 `Q{片數}`。不得用已插入 Q 的 DXF 反向判等。
6. **顯示效能**：復用 2D scene/canvas；只改選取 overlay 時不得更新 canonical geometry。真 GUI profiling 確認操作時間與計算次數。
7. **Legacy migration／尺寸 authority**：非受電箱舊檔缺版本欄位時，建立相容投影 `version_count=1, piece_count=1`，並原樣承接舊 Feature；受電箱舊檔仍判作套／連。**首次**切入數量模式以專用尺寸確認對話框的有效 W/H/D 建立單箱體；只能以 `BOX_BODY_DEFAULTS` **預填且必須人工確認**。實際存在的兩個函式分工為：`project_primary_bay_legacy_aliases()` 在專案讀回時包裝 **Set1/Bay1** 相容投影；`project_receiving_bay_legacy_aliases()` 則可指定 `set_index`／`bay_index` 產生某連的 runtime-only 投影。兩者的 transient W/H/D 均不可當作另一模式首次初始化的權威尺寸。Session restore／已保存數量模式尺寸優先於首次初始化；首次反向切套／連也依 CPR-19 自行確認獨立新基準，不能複製當前數量專案。
8. **自訂板件 multiplicity**：在獨立頂層板件 authority 保存正整數 `per_box_count`（預設 1）；存檔及讀回可重建相同 BOM 與 DXF `Q`。未參與製造的板件不得冒充已上線加工物件。
9. **反向初始模式**：已載入數量模式、缺套／連 Session buffer 時，由確認後的合法 W/H/D 呼叫 `new_receiving_layout()`（或同等正式入口）建立 **1 Set × 1 Bay、0 Joint**，初始化既有各欄位與預設；在成功前不得寫入 session 切換／保存範圍。不得把數量模式的 saved snapshot 直接解碼成套／連結構。
10. **共用箱體編輯 authority**：在數量模式保留獨立單箱體共同設定 owner，供共用設定頁存取；由現有 Receiving Family / `SETTING_DEFAULTS`／品牌設定做合法預設與驗證，封頭尾 Feature 只由各 `version_id` 持有；共同尺寸提交時必須對所有版本重驗證孔位與 BOM，並更新現有 Scheduler 所擁有的製造結果，而非在 UI 另算一份。

## 7. Testing Decisions / Acceptance Criteria

| ID | 必測案例 | 預期 |
|---|---|---|
| AC-01 | 受電箱在套／連視窗選取與高亮。 | 只有 2D overlay 更新；等價 state 全量 geometry calc=0／DXF reread=0。 |
| AC-02 | 先不選修改項目就點 2D 孔位。 | 不進入編輯選取／不提交正式資料。 |
| AC-03 | 受電箱由套／連切數量、再切回套／連。 | 前一模式在本次程式執行內完整回復，兩模式不混用。 |
| AC-04 | 切到數量模式 Save→重啟→Reload。 | 只還原數量模式；未另存套／連暫存不還原。另將套／連另存則可獨立恢復。 |
| AC-05 | 選版本 1 後連按 `＋` 新增兩版，修改第二版封頭 Feature 與第三版件數。 | 每次複製**當前選取版本**、新項插於來源後並自動選取、Feature deep copy 不連動；各版件數獨立，總件數精確反映加總。 |
| AC-06 | 新增自訂板件、選 X 或 Y、輸入另一方向尺寸。 | 頂層身份穩定、合法 Fold Profile 和尺寸正確，可存檔及生成真 2D／3D／DXF。 |
| AC-07 | 同一箱身 5 件，封頭 A 3 件、B 2 件。 | 箱身 1 份 `Q5`，封頭 A 1 份 `Q3`、B 1 份 `Q2`；封尾依實際等價分組。 |
| AC-08 | 相同外框但孔位／折彎／材質不同。 | 不合併為同一 DXF。 |
| AC-09 | 正中心有孔、切割線、既有檢查註記。 | 大寫 Q 自動避讓、CHECK 層；切割與工藝幾何未變。 |
| AC-10 | DXF 輸出後用 CAD parser reopen。 | 每群只有一份檔；Q 大寫且數值與實際群件數一致，沒有小寫 q 與重複 Q。 |
| AC-11 | 舊 `.p6fold` 金庫型與受電箱專案開啟。 | 原箱身、封頭尾 Feature、套／連關係與畫面操作無損；非受電箱舊檔有效視為一版、件數 1，受電箱維持套／連。 |
| AC-12 | 快速切換設定、取消／套用後立即 Save 與 DXF。 | 只有已提交 active state 進入製造；無 stale geometry、暫存洩漏。 |
| AC-13 | **非受電箱**孔型版本 1／2／3 的封頭／封尾 Feature 互不相同，Save→關閉→Reload。 | active mode 與每個孔型版本的 stable ID、獨立孔位、anchor、2D 與 DXF 一致；無引用互相覆寫。 |
| AC-14 | 舊版**非受電箱** `.p6fold` 沒有任何孔型版本／件數欄位。 | 載入時以相容投影視為**一個孔型版本、該版本件數 1**；不應臆造 2+ 項，舊 Feature 完整保留。 |
| AC-15 | 舊版**受電箱** `.p6fold` 沒有孔型版本／件數欄位。 | 仍載入既有**套／連模式**且配置無損；不得被非受電箱 N=1 相容規則擅自改成數量模式。人工切入數量模式時必須先**明確確認 W/H/D**，之後才建立**獨立單箱體**一筆孔型版本、件數 1，不能帶入前一模式的 Bay 尺寸或 Joint。 |
| AC-16 | 受電箱已編輯 2 套／3 連，切到數量模式並修改孔位，再切回。 | 作用中模式與記憶體暫存互不污染；所有未另存數量資料重啟後不復原；各自 Save As 的專案獨立。 |
| AC-17 | 10 個相同箱體的背板、門、底板及頂層自訂板件都存在；另有多片箱身。 | 按正式 BOM 每箱片數 × 版本件數逐個計算真實 physical part 的 `Q`；自訂板件每箱片數設定可 Save→Reload、不得遺漏。 |
| AC-18 | 修改共用 W/H/D，孔型版本 1／2 有不同 Anchor／offset 孔位。 | 重新以新 reference guide 解析，每項孔位正確；超界孔明確報錯、不暗移、不輸出不合法 DXF。 |
| AC-19 | 選中間版本進行 `＋`、`－`；分別驗證**已存檔**版本和**有未存檔差異**的版本，並測試刪除時按取消。 | 複製／刪除只作用於目前選取；新增插入來源緊後方且選取新項；**不論是否已存檔，每次刪除都需確認且可取消**；刪除後先選下方鄰項、無下方則選上方；stable ID 不重用；最少保留 1 版。 |
| AC-20 | 兩個孔型版本分別件數 6 和 4。 | 兩版總件數 10，共用箱身需求合併為 `Q10`，封頭不同孔型分開為 `Q6`／`Q4`，相同封尾也為 `Q10`；不硬產生 10 張同形 DXF。 |
| AC-21 | 受電箱已編輯 2 套各 3 連，切數量模式後輸出，再切回原模式。 | 數量模式只用獨立單箱體；沒有多連 Joint／沒有 6 倍錯算；切回原套連時資料完全還原，兩模式分別另存互不滲漏。 |
| AC-22 | 2 個孔型版本件數 30／20；選中版本 1 再 `＋`；把件數改為 7、輸入 0／負數／小數、刪至僅 1 版。 | UI 明示**版本數**與**總件數**；`＋` 新項件數預設 1 且插在選取版本之後並自動選取，件數必須正整數；不可刪至 0 版；輸出 Q 隨合法件數變更。 |
| AC-23 | 2 版本件數合計 50、自訂加強板每箱 2 片；Save→Reload→DXF。 | 自訂板件保持頂層與 BOM 身份，若幾何完全相同則加強板只輸出一張 DXF、`CHECK` 大寫 `Q100`；其他板件按真實每箱片數獨立統計。 |
| AC-24 | 試圖在孔型版本 2 獨自修改封頭外形／折法／W/H/D，與修改版本 2 封頭 Features 對照。 | 前者不得產生逐版本獨立板形；共用箱體外形只能一次共同提交，後者只覆寫版本 2 的 Feature；Save→Reload 保持一致。 |
| AC-25 | 由只有 2 套／3 連 Receiving layout 的舊專案首次切入數量模式，打開尺寸確認後取消、輸入 0／空白／非法 W/H/D、再輸入 W=900／H=1700／D=400 並確認。 | 取消／非法輸入不切換、不建立版本、不修改舊套／連；合法明確確認後建立**單一**獨立箱體與一筆件數 1 的孔型版本。尺寸採確認的 900／1700／400，不能偷偷用 2 套任一 Bay 或 Family 預設。 |
| AC-26 | 先確認一個非預設 W/H/D 的數量模式，切回套／連又切回數量模式；另存數量模式，關閉後開啟該檔。 | 同 Session 切回無須再次輸入、W/H/D 與 Feature／件數完整恢復；已存檔 Reload 精確讀回所保存尺寸，不再被預填預設覆蓋；未另存模式的資料在重啟後不恢復。 |
| AC-27 | 某孔型版本原件數 4，編輯為 7 並確定但尚未手動 Save；刪除另一版本時取消、再確認。 | 件數 7 **立即生效於目前編輯狀態**的總件數與 Q 預覽，但讀取未更新的舊磁碟檔仍為 4；刪除操作每次先確認，取消時編輯狀態完全不變，確認刪除後只有 Save 才持久化。 |

| AC-28 | 由**僅保存數量模式**的受電箱 `.p6fold` 重新開啟，本次 Session 完全沒有套／連暫存，第一次要求切入套／連並明確確認 W900／H1700／D400。 | 先告知將新建獨立 1 套／1 連；確認前不變更 active mode；確認後建立**恰好 1 Set × 1 Bay、0 Joint**、尺寸正確，無數量版本孔位／件數洩漏；保存套／連再 Reload 得到同一基準。 |
| AC-29 | 同 AC-28，但依序取消／關閉視窗、輸入 0／空白／負值／非法 W/H/D，再輸入有效尺寸確認。 | 取消與非法尺寸完全維持原數量模式的共用設定、所有版本／件數及未存檔編輯狀態，絕不產生偷存的 Set/Bay；有效確認後才完成切換。 |
| AC-30 | 首次建立受電箱數量模式後進入 `[共用箱體設定]`，查看背板／內門／品牌預設；建立兩個版本再把背板改為半截、內門由 1 改 2、品牌改為合法選項。 | 初始背板 `FULL`、內門 1 層、品牌士林均來自現有預設；設定入口不依賴版本選取；合法變更對**兩個版本共用**，各版只有 head/tail Features／件數獨立。正式 BOM／Q 與 Save→Reload 正確且不遺失共同設定。 |
| AC-31 | 數量模式已建立兩個孔型版本後，在 `[共用箱體設定]` 改 W/H/D，再取消另一筆非法更改；其中一個版本含邊緣 Anchor／offset 開孔。 | 新尺寸合法確認後唯一共用箱體更新，兩個版本的 feature guide 均重新計算、UI／BOM／DXF 一致；違法尺寸及超界 Feature 不生成錯誤 DXF；取消不變更任何版本和已提交共同尺寸；未按 Save 的改動不寫入磁碟。 |
| AC-32 | 同一 Session 已有合法**多套／多連**的套／連暫存，切數量模式後再切回套／連；與關閉後只讀入已保存數量模式而無套／連暫存的情境對照。 | 同 Session 必須原樣恢復原多套多連（含尺寸、品牌、背板、內門、Features／Joint），**不得誤重建 1×1**；重啟後無套／連暫存則僅能經 AC-28 首次初始化。兩種來源不得混淆。 |

效能驗收需收集計算次數、DXF disk read、FinalScene rebuild、render 次數與 GUI wall time；不得只靠 headless 測試或縮減幾何精度宣稱改善。**AC-14／15／25／26／28／29 為向後相容與雙向初始尺寸來源的明示產品要求，不等於目前寫檔器已支援新版本／件數 schema。**所有驗收表均為待實作測試，並非宣告 GREEN。

## 8. Out of Scope / Open Items

### 8.1 明確不做

- 不改主畫面 3D 或其他板件一般編輯器為 2D。
- 不更改受電箱現有 Set/Bay/Joint 的幾何真值，亦不得同時啟用兩種模式。
- 不將未啟用模式的記憶體暫存自動存入專案；不在關閉程式後偷偷恢復暫存。
- 不重新發明 CAD layer、孔位 anchor、Fold 成形尺寸或 DXF serializer。
- 不把 `Q` 當實體打標線或雷射加工字。

### 8.2 尚缺的資料／必須按正式製造來源解決

| 項目 | 狀態及施工約束 |
|---|---|
| 自訂板件 17／100 的折邊方向、既有 UI 欄位到 Fold Profile segment 的精確 mapping | **需要 source-level geometry contract 查證**；已確認 X/Y 擇一與另一方向人工尺寸，**不再問使用者重新選**。 |
| 自訂板件與組合體的實際接合／定位 | 尚無使用者指定的實體 mating/placement，不得靠 renderer bbox 猜。先允許獨立自訂板件，若要自動納入組裝與碰撞，需合法 placement authority。 |
| 大量版本的文件命名與輸出檔名碰撞 | `＋／－` 選取及插入位置已於 CPR-17 定案；輸出檔名不能使用易位移的畫面序號作唯一身分，仍由 deterministic stable identity / equivalence-group namespace 和 atomic save 處理，不准默默覆寫。 |
| `Q` 無任何合法可讀位置時 | 以驗證失敗提示，不允許無聲省略或移出物理料件而誤導加工；優先採納現有 annotation/collision planner 規則。 |

### 8.3 決策關閉與施工邊界

- **已確認產品規則／本版定案**：受電箱套／連與獨立單箱體數量模式互斥、切換只暫存；**缺另一模式 Session 暫存時，兩個方向首次建立皆須明確確認 W/H/D**，可引用 Family defaults 作可編輯初值但不可靜默採用；反向新建套／連必須是獨立 1 套 1 連，數量模式可於「共用箱體設定」變更 W/H/D／背板／內門／品牌等共同參數；版本有正整數件數，`＋` 複製目前選取版本、插在來源後並自動選取；`－` 刪目前選取版本且一律確認；只允許封頭／封尾 Feature 覆寫、所有正式物理板件按 BOM × 件數計量，以及 CHECK 大寫 `Q` 和自動避讓。
- **程式已查證能力**：Receiving Set/Bay、每連 Features、Hole Editor anchor、Project Snapshot 保存 authority、namespaced batch DXF；完整孔型版本 schema／全部 BOM 計量／等價 dedup 與 Q 仍待實作。
- **剩餘技術責任**：自訂板件 17／100 精確 Fold 映射、無指定組裝位置時如何維持獨立板件製造、各 Family physical BOM 枚舉、實際 DXF 和 GUI 測試。這些不得重新包裝成前述五個 OPEN 產品問題。

## 9. Evidence / Traceability

- **v1.4～1.5 尺寸與共同設定 source readback**：`ae_engine/cabinet_types/receiving.py::BOX_BODY_DEFAULTS` 定義受電箱 Family 建立初值 W=800／H=1600／D=350；`ae_engine/receiving_layout.py::new_receiving_layout()` 接收明確 width/height/depth 建立 1 Set × 1 Bay、0 Joint。`ae_engine/receiving_shared_settings.py::SETTING_DEFAULTS` 明定背板 `FULL`、內門 1、封頭尾空 Feature；`ae_engine/receiving_switch_layout.py::RECEIVING_SWITCH_BRANDS` 首項為士林。**以上是新模式的建議初值／既有正式預設，不是舊存檔實際尺寸。**
- **兩種函式不是筆誤**：`ae_engine/receiving_layout.py::project_primary_bay_legacy_aliases()` 是讀檔相容的 Set1/Bay1 convenience wrapper，內部使用 `project_receiving_bay_legacy_aliases(..., set_index=0, bay_index=0)`；後者可為任意合法 Set/Bay 產生 runtime projection。它們都不是雙向新模式初始化的 authority；此限制已在 §6.7 與 CPR-18／19 定義。


- **使用者確認**：前輪 D-1～D-8 決策題，包括「套／連與數量二擇一」、「新增版本複製封頭／尾 Features」、「X/Y 擇一另一邊輸入尺寸」、「受電箱套／連的 3D 改 2D」、「另一模式只 session 暫存」、「CHECK 大寫 Q」、「中心優先避讓」、「要永久保留就自己存檔」；本輪五項 OPEN 經審查及受電箱獨立單箱體最終確認，依 CPR-13～20 及本版雙向初始化／共用設定條款定案。
- **當前 GitHub 程式**：[`AGENTS.md`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/AGENTS.md)、[`fold_designer_bridge.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/fold_designer_bridge.py)、[`phase6_navigation_view_adapter.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/phase6_navigation_view_adapter.py)、[`phase6_workspace_state.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/phase6_workspace_state.py)、[`phase6_designer_workspace.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/phase6_designer_workspace.py)、[`phase6_settings_profile_projection.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/phase6_settings_profile_projection.py)、[`ae_engine/receiving_layout.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/ae_engine/receiving_layout.py)、[`ae_engine/receiving_shared_settings.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/ae_engine/receiving_shared_settings.py)、[`gui_modules/application/receiving_set_bay_controls.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/gui_modules/application/receiving_set_bay_controls.py)、[`gui_modules/application/fold_designer_manufacturing_projection.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/gui_modules/application/fold_designer_manufacturing_projection.py)、[`phase6_hole_editor_canvas_view.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/phase6_hole_editor_canvas_view.py)、[`ae_engine/manufacturing_export.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/ae_engine/manufacturing_export.py)、[`ae_engine/sheetmetal_drawing.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/ae_engine/sheetmetal_drawing.py)、[`ae_engine/dxf_serialization.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/ae_engine/dxf_serialization.py)、[`phase6_project_file.py`](https://github.com/looaeedr/whd/blob/cleanup/2d-3d-sync/phase6_project_file.py)。
- **現有測試**：`tests/test_issue1112_receiving_set_bay_editor.py`、`tests/test_issue1331_receiving_shared_settings.py`、`tests/test_issue45_dynamic_parts_2d_roundtrip.py`、`tests/test_phase6_project_file.py`、`tests/test_issue1301_receiving_preview_holes.py`。
- **AI Library / SOP**：`個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md`、`個人AI檔案庫/第二層_專案與SOP/01_DXF與CAD自動化全域規範.md`、`個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`、`.agents/skills/engineering/phase6-gui-performance-integrity/SKILL.md`、`.agents/skills/engineering/驗證板件與DXF/SKILL.md`。
- **證據分類**：CPR 為使用者確認的產品規則；Current State 是現有程式事實；Source-level geometry contracts 及物理 placement 尚未驗證的部分保持 OPEN。尚未做實體 GUI profiling、程式修改、CI、Save→Reload／DXF 新功能測試；本文**不宣告實作完成**。

---

**摘要**：原 OPEN-01～05、受電箱雙向模式**無 Session buffer 時的首次 W/H/D 明確確認來源**及數量模式的共用箱體設定入口／預設均已定案；受電箱數量模式**只做單箱體**，切回套／連首次建立**1 Set × 1 Bay、0 Joint**，兩模式永不混用資料。孔型版本與實際件數分離，其他板件按 BOM × 件數且自訂板件另有每箱片數。§4.5 UI 與 AC-05／13～32 已更新；合法件數即時生效於編輯狀態但不自動存檔，`＋` 插於來源後，`－` **每次**確認。尚須依正式資料核對 17／100、板件 placement 並執行產品回歸，**本文為施工需求定版，不代表程式已施工、已驗收或已合併 GitHub**。
