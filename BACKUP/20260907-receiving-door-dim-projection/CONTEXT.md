# Phase6 領域詞彙

## [CURRENT] 2026-09-02 Runtime semantic guard

- `OVERLAY = 貼外`。
- `包覆貼外 = 高階 preset`；`WRAP = 下方局部包覆 Joint`；**包覆貼外 ≠ OVERLAY ≠ WRAP**。
- Receiving EndCap D core = `D - 2T`。
- Vault EndCap D core = `D - 3T`。
- Active standard OVERLAY rule：`ENDCAP_TOP_OVERLAY_STANDARD_V1@3`，正式公式以 STANDARD + semantic delta 為 Source of Truth：`primary_u = side_fold + FW`、`primary_v = ytop1 + FW - T`、`secondary_u = side_fold`、`secondary_depth = T`。fixture `T=2 / side_fold=15 / FW=25 / ytop1=16` = **`40×39 + 15×2`**。
- `formed FW` 只保留作 3D shadow / collision evidence，**不得作 runtime CUTTING oracle**，也不得回寫 EndCap material FW。
- **`40×23 + 16×4` 只屬 linked-FW `INSERT_OVERLAY` fixture**（`ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1@1`），不是標準 OVERLAY oracle。

> 本檔只記錄已由使用者確認的領域名詞與語意；未確認細節不得自行補完。

## 箱身結構型態

### 一體成型
- 已知為目前既有程式主要支援的箱身結構型態。
- 一體成型、二件式、三件式都是正式箱身結構型態；**不得假設一體成型永遠優先**。
- 箱身結構型態有兩種來源：
  1. **型號／產品規劃預設**：某些類型原本就規劃為二件式或三件式。
  2. **板材限制拆件**：原本可一體成型，但因展開尺寸超過現有板材可用尺寸而改拆二件式或三件式。
- 不得單純依箱身總寬 `W` 大小判定是否拆件。板材限制只是其中一種來源，不是唯一原因。
- 若型號／產品規劃已帶入箱身結構型態，該型態**預設鎖定**；使用者可主動**解鎖**後變更。鎖定狀態不得被誤解為該型態永久不可變。

### 二件式箱身
- 箱身由 **左箱身** 與 **右箱身** 兩個板件構成。
- 二件式是由原本的 **一體成型箱身沿寬度方向切開**，形成左箱身與右箱身。
- 切開位置 **不固定、可調整**，不得假設一定由正中間等分。
- 左、右兩件的 **包外尺寸相加必須等於箱身總寬 `W`**。
- 左箱身與右箱身的包外尺寸 **兩邊都可以直接輸入**。
- 任一邊被使用者修改後，另一邊必須自動補全為 `W - 已輸入值`；兩邊不是彼此獨立的自由值，而是雙向可輸入、互相補全，且任何時候都必須維持合計 `= W`。
- 左箱身與右箱身的包外寬 **各自不得小於 50 mm**；因此可調範圍必須同時保證另一側自動補全後也 `>= 50 mm`。
- 二件式只拆原一體成型箱身中央的 `W` 段；兩側 `D` 完整保留。幾何關係為 `W左 + W右 = W`。
- 左箱身與右箱身在中央切口處 **各自都有一個焊接用接合折邊**。
- 中央接合折邊左右兩側 **尺寸連動**，預設值為 **12 mm**，且 **可調整但不得小於 12 mm**。
- 中央接合折邊不計入 `W左 + W右 = W` 的分配值；它是切口後額外形成的接合折邊。
- 中央接合方式為 **焊接**；2D／DXF 不需要另外產生焊接線或 MARKING。
- 中央接合折邊在資料模型與 Fold Chain 中就是**一般 BEND 折彎**，不得另創「焊接折邊」幾何類型；「焊接」僅描述用途，不是折彎種類。
- 其他既有折彎也有相當一部分是以後續焊接為目的，因此不得以「是否焊接」作為 BEND 類型分類依據。
- 中央接合折邊 **不設上限**；當尺寸 **>= 50 mm** 時視為異常值，系統必須顯示警告但 **不得阻擋操作**。
- 接合折邊異常警告必須同步反映於 **設定面板、2D 預覽、3D 預覽**，並由同一份狀態／規則來源判定，避免不同步。
- 存檔時只保存接合折邊的 **實際尺寸值**，不保存警告 UI 狀態；重載後依當前規則重新判定是否警告。

### 三件式箱身
- 三件式至少有 **兩種幾何型態**，不得視為單一固定拓撲。

#### 三件式（W 三分） `THREE_PIECE_W_SPLIT`
- 沿用二件式的分件／接合邏輯，但將原本中央 `W` 拆為三段：`W左 + W中 + W右 = W`。
- 左右原有 `D / FW / Z` Fold Chain 完整保留。
- 預設 `W左 = 50 mm`、`W右 = 50 mm`，`W中 = W - 100 mm`；此 50 mm 預設可讓左右接縫避開底板而不需額外處理。
- `W左` 與 `W右` 連動且始終相等；修改任一側時另一側同步，`W中` 自動補足。
- `W中` 亦可直接輸入；修改 `W中` 時，左右自動平均補足：`W左 = W右 = (W - W中) / 2`。
- 系統自動計算值可保留 `.5 mm`；人工輸入只接受整數。
- 接合折邊、90° BEND、封頭／封尾十字截角、底板避讓與狀態保留等規則沿用二件式。

#### 三件式（側背分離） `THREE_PIECE_SIDE_BACK_SPLIT`
- 由 **左側板**、**後面板**、**右側板** 三個獨立板件構成。
- 左、右側板在後側各增加一條沿整個箱高 `H` 的縱向折邊；該折邊預設 **15 mm**，可調。
- 左、右側板的成型尺寸皆為 **`D`**。
- 後面板成型寬為 **`W - 0.5T`**；其中 `0.5T` 為預設補償量，且可調。
- 組裝時，**後面板放置在左右側板新增折邊的上方**。

### 二件式補充：狀態、精度與中央交會
- 一體式、二件式、三件式各自保留自己的暫存設定；切換型態不得清除另一型態已輸入值，目的是支援即時比較。
- 第一次由一體式切換為二件式且沒有歷史分配時，`W左`、`W右` 預設對半；若 `W` 為奇數，系統自動值可合法出現 `.5 mm`，例如 `1201 -> 600.5 + 600.5`。
- 人工輸入 `W左`／`W右` 只接受整數；一旦人工修改其中一邊，另一邊依 `W - 已輸入值` 自動補全並回到整數組合。
- 系統自動產生的 `.5 mm` 值若未被人工修改，必須完整保留到 2D、3D、儲存／重載與 DXF／NC，不得被四捨五入。
- 中央接合折邊要計入左右各自板件的實際展開／下料總寬，但不計入 `W左 + W右 = W` 的包外分配。
- 二件式僅拆中央 `W`；左右原有 `D / FW / Z` Fold Chain 各自完整保留於自己的板件。
- 中央新增接合 BEND 為一般 90° BEND。
- 二件式箱身中央縱向 BEND 與封頭／封尾屬不同板件；上下端需依組裝後的空間干涉關係，在箱身端部套用既有十字截角／單邊留肉幾何。不得誤解為同一張展開圖上的兩條 BEND 線直接相交。
- 上、下端交會須使用既有的十字截角／單邊留肉幾何概念處理。
- 十字交會的額外避讓量預設為 `5 mm`，可調；不得寫死。
- 十字交會的單邊留肉量預設為 `0.5T`，可調；`T` 取當前板厚 Source of Truth。
- 上端取封頭實際 `ybottom1`，下端取封尾實際 `ybottom1`；兩端均以實際封頭／封尾幾何為準。
- 十字截角結果必須由同一份 resolved geometry 驅動 CUTTING、BEND span、2D、3D、DXF、NC，不得各層自行重算。

### 二件式補充：底板折彎與中央接縫交會
- 底板為後方內側的安裝底板；其周邊折彎邊在組裝後會落到後面板表面。
- 二件式箱身中央接合折邊沿箱高方向位於後面板中央接縫；底板折彎邊與其在組裝後形成十字交會。
- 此交會使用與既有十字截角相同的「單邊留肉」概念處理，不得把整條底板折彎邊直接縮短。
- 單邊留肉預設為 `0.5T`，且可調；`T` 取當前板厚 Source of Truth。
- 底板此處的避讓長度預設總長 `20 mm`，以中央交會點為中心前後各 `10 mm`；總長度可調，調整時仍以交會中心對稱分配。


## FW 連動語意
- 箱身 FW 是上游主控；初始時封頭／封尾同步跟隨箱身。
- 使用者先手動修改封頭 FW 時，封尾同步跟隨封頭；持續修改封頭時仍維持此連動。反向亦同。
- 在封頭主導時再手動修改封尾，或在封尾主導時再手動修改封頭，兩端解除連動並各自獨立。
- 無論目前由哪一端主導或已獨立，只要使用者重新提交箱身 FW，即使數值未改，也視為箱身重新接管：封頭／封尾一起回到箱身 FW。
- 一般 redraw、refresh、切頁、載入或非 FW 欄位更新不得擅自改變控制權。
- 封頭／封尾 FW 欄位保持可人工輸入；控制權由狀態機管理，不靠把 FW 欄位鎖死。

## 受電箱 Cabinet Family
- 「受電箱」與「金庫型」是同層 Cabinet Family，不是箱身一體／二件／三件式的結構選項。
- 使用者介面的「基準型號」就是盤體類型的唯一選擇與 Source of Truth；不得再另外建立「盤體類型」選單或獨立 state。`受電箱` 必須直接出現在既有「基準型號」選單中。內部 Cabinet Family registry 只負責依目前 `model` 派送 policy，不是第二份使用者資料。
- 受電箱箱身固定使用「三件式（側背分離）」：左側板、後面板、右側板；沿用既有側板後折規則，後折預設 15 mm 且可調。
- 受電箱箱身主折列沿用金庫型既有幾何與折向，但移除 `zr1`；操作員預設值為 `-24 24 29 350 800 350 29 18`，對應 `zl1 / zl2 / FW左 / D左 / W / D右 / FW右 / zr2`。
- 受電箱封頭／封尾的 `ybottom1` 預設 15 mm；成型後貼在後面板 `W` 的外側接合區，不包住 `W`。
- 因 `ybottom1` 改為外貼 `W`，封頭／封尾 D 向材料核心使用 `D - 2T`。
- 受電箱封頭／封尾下方截角使用既有「嵌入貼外型」；其等價 FW 依據為「側板後折 + 1T」。
- 下方嵌入貼外型預設參數為：貼外留肉 `0.5T`、嵌入留肉 `0.5T`、二級截角深度 `2T`，三者皆可調。
- 受電箱門四邊折預設皆為 19 mm；左右／上下門縫皆為 3.5 mm；四角沿用 C02；門尺寸補償沿用金庫型。

## 2026-08-29 封頭／封尾上方單級 INSERT Relief 真值

- 上方 `INSERT` 的最終截角尺寸必須由實際折後 3D mating geometry 求得；舊固定 CornerType 尺寸只能作 compatibility/search hint，不是 Source of Truth。
- 真板厚 solid 會有 ±T/2 兩張 skin。**skin 與箱身的正常面接觸／邊接觸不得視為材料穿透**；relief solver 必須分離 contact 與 penetration。
- 單級 `INSERT` 不得因多輪 solver evidence 長成第二級階梯；迭代只可改變同一合法 topology 的實際尺寸。
- `自訂(9).p6fold`（W400/H600/D250/T2/FW25、單級 INSERT）已確認的幾何結果為：Head 左右上方角 `38×27`、Tail 左右上方角 `38×27`。此數字是該組幾何的 regression evidence，不是硬編碼公式。
- 同一 resolved relief 必須同步驅動：主 2D CUTTING / BEND clip、單板 3D、組合圖、尺寸文字、DXF/NC。任何一處顯示 40、39，而其他處為 38，都代表資料鏈分叉，不能用顯示 rounding 掩蓋。

## 2026-08-29 組合碰撞顯示與 Assembly Intent 自動驗收
- 組合圖碰撞紅區的 Source of Truth 是 **solver 求解前的 pre-solve physical probe**；已套 relief 的 final material 只能用於 production display / refold verification，不能拿來回推「原本有沒有碰撞」。
- `INSERT / OVERLAY / INSERT_OVERLAY` 都走同一套 collision display / solve / verify pipeline，不得各自做 UI 特例。
- 3D solver 只允許改變合法 corner topology 的實際尺寸；原本單級不得長成二級，原本二級不得被壓成單級。
- 真正 X 向鏡像對稱的 Box Body / EndCap / corner component，左右 relief 必須鏡像一致；只有 profile 與 component 都通過幾何 symmetry check 才可 harmonize，非對稱件禁止強制左右相同。
- `BOX_ASSEMBLY_TYPE_IDS` 是 assembly intent 回歸矩陣的 registry Source of Truth。未來新增 intent 時，測試必須自動新增 Head/Tail + collision + topology + 2D/3D/assembly + Save/Reload 驗收；新 intent 未通過不得交付。

## 2026-08-29 Certified Relief Registry 第一階段
- 已新增 `ae_engine/certified_relief_registry.py` 作為已認證截角公式資料庫。
- 已認證規則優先於 3D discovery；3D 僅做 shadow validation。
- 首筆規則：`ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1`，適用 linked-FW INSERT 拓撲，公式為 `EndCap side fold + (effective FW - T)` 與 `EndCap FW + INSERT amount_t*T`。
- precondition 很重要：若 EndCap Y profile 仍含 `ytop1` row，該規則不得套用，必須走 fallback，避免把 38×27 錯套到未認證拓撲。

## 2026-08-29 Certified Relief Registry 完整化
- 已知截角公式採 certified-first；3D 是 registry MISS 的 fallback 與已知公式的 shadow validator。
- 金庫型與受電箱固定規則已 registry 化。
- linked-FW INSERT `自訂(9)`：`ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1@1`，38×27。
- linked-FW INSERT_OVERLAY `自訂(10)`：`ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1@1`，`CERTIFIED`，公式推導 40×23 + 16×4 fixture。
- Save/Reload 保留 rule revision/trust；ambiguous/stale rule 不得靜默使用。
- 新增 assembly rule 時必須讓 registry-driven GUI matrix 自動新增案例。

### [HISTORICAL/SUPERSEDED — 不可作 runtime oracle] 2026-08-29 OVERLAY flat-X / formed FW 裝配記錄
- OVERLAY EndCap X 方向沒有實體 BEND；legacy `yl1/yr1` 不得再成為 flat-X manufacturing CUTTING basis。
- 但上方裝配 X relief 也不能只取 EndCap nominal FW；必須避讓箱身 Fold Profile 折後的 formed FW occupation。
- `金庫型貼外.p6fold`：W400/T2/nominal FW25，箱身 formed FW=29，因此上方每側 U=29、中央 342，單側 `29+371=400`；V 仍用 EndCap FW25 得 39。下方 1.5T 每側 3、中央 394。
- [HISTORICAL/SUPERSEDED — 不可作 runtime oracle] 當時 Registry：`ENDCAP_TOP_OVERLAY_STANDARD_V1@2`、geometry input=`BOX_BODY_FORMED_FW`、X=`primary_u=mating_width`；現行請讀 v3。
- `.p6fold` 舊 committed relief 是 cache；contract/version/formed-FW/profile/rule revision 不合必須失效重算。

## 2026-08-30 — 受電箱下方 WRAP / 展開料 / Skills

- 箱身側背分離與封頭尾組合方式是不同層級；WRAP 只屬受電箱封頭／封尾下方，不出現在組合方式選單。
- 封頭尾仍可任選 INSERT / OVERLAY / INSERT_OVERLAY；下方 WRAP 對三者使用同一獨立 Joint/Registry 語意。
- WRAP 設定通常 Head/Tail 連動；各端 final material、截角與展開料仍獨立求值。
- X/Y 預留為可調 mm：預設 reserve_u=2、reserve_v=1，位於參數鎖定解鎖區。
- 所有板金 Blank 從 canonical final material 量，不另算一套展開公式；多片箱身逐片列料。
- 受電箱 EndCap 使用 core-origin placement；其他 Family 保留既有 placement 契約。
- Skills 已搬至 `.agents/skills/`，截角／3D 變更必跑 phase6-corner-3d-model-integrity gate。


## 2026-09-07 — Receiving Door FW dimension semantic

- 金庫型 Door 的 `FW` 維持 MATERIAL 語意；例如 `FW=25, T=2`，成形框占位為 `25 + 2T = 29`。
- 受電箱操作員/Family state 的 `FW` 是 FORMED_OCCUPATION；預設 `FW=29` 已包含 25 mm 材料折邊的兩側板厚補償。
- Door 共用幾何仍只接受 MATERIAL FW，並在成品尺寸 resolver 內加 `2T` 一次。受電箱必須先由 Cabinet Family policy 做 `material_fw = formed_fw - 2T`，不得直接把 29 傳給共用 resolver 再變成 33。
- 外門 2D / baseline stretch / DXF / 3D、內門板與內門框衍生、assembly placement 必須消費同一 family-aware Door FW resolver。
