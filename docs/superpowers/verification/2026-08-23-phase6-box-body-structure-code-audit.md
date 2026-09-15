# Phase6 箱身多結構規格 — 現有程式查核報告

時間：2026-08-23 16:58:19（Asia/Taipei）  
查核基線：`PHASE6_HOLE_EDITOR_CANVAS_VIEW_FULL_20260823_160603.zip` 解壓內容 `/mnt/data/phase6_hole_editor_view`

## 1. 查核目的

針對原規格／Buildable Spec／01～09 工單中仍可能讓實作者自行猜測的事項，優先回查目前 Phase6 source code。規則分成三類：

1. **程式直接證據**：現有正式行為或資料模型已能定案。
2. **既有 convention 推導**：新功能尚不存在，但現有尺寸／座標／持久化 convention 已限制可接受解法。
3. **程式查無既成答案**：不得冒充舊規則；只能保留為新 resolver 必須驗證的設計決策。

本輪沒有修改任何 production code 或 `config.ini`。

---

## 2. 舊 `.p6fold` migration

### 程式證據

- `phase6_project_file.py:86-111`
  - project schema 仍為 `phase6-fold-project-v1`。
  - validator 只要求 payload 是 dict、schema 正確、`snapshot` 是 dict；**沒有要求固定 snapshot keys**。
- `gui.py:1453-1535`
  - `_apply_phase6_project_snapshot()` 以 `dict(snapshot or {})`、`snapshot.get(...)`、`setdefault(...)` 恢復資料。
  - 註解明確表示現行 restore 已補上「old snapshot omitted」的 project-specific state。
- `phase6_fold_profiles.py:51-80`
  - 現有 BoxBody profile 唯一正式物理結構是連續 `D-W-D` core，外圍沿用既有 FW/Z folds。

### 結論

**直接可定案：** 新的 structure state 應以 additive optional snapshot field 加入，不需要僅為新增欄位改 project schema；舊檔缺欄位時不能破壞既有 restore。

**相容性決策：** 舊檔沒有 `box_body_structure` 時固定保留舊版一體成型／連續 D-W-D 結果。否則只是因新版增加型號多件式預設，就會讓同一舊專案重載後變成另一種物理箱身，違反既有 project restore 與 one-piece zero-regression。

**structure lock migration：** 現有程式沒有「箱身結構 lock」這個新欄位；只能沿用目前已存在的已知型號 vs `自訂` editability convention 作 legacy fallback，並在新版本第一次保存後持久化 explicit lock。這一項屬 code-derived migration decision，不是舊 structure-lock code。

---

## 3. 非法 W 人工輸入：reject/revert，不 clamp

### 程式證據

- `gui.py:3536-3544`
  - `_reject_door_layout_dimension()` 直接把欄位恢復 `previous_value`、顯示 warning、重畫。
- `gui.py:3546-3569`
  - `commit_door_layout_width()` 驗證超過可用總寬後，呼叫 reject/revert；沒有 clamp 成最大值。
- `ae_engine/sheetmetal_part_adapters.py:69-90`
  - `complete_partition()` 對超出總量回 `valid=False`，不悄悄重寫使用者數值。
- `ae_engine/sheetmetal_part_adapters.py:134-149`
  - 幾何 validator 對總和不合法直接 `ValueError`。

### 結論

W 二分／W 三分人工輸入沿用相同契約：

- commit-time validation；
- 不合法 → 拒絕、恢復上一 committed 合法值、提示；
- **不 silent clamp**；
- resolver 對損壞存檔／直接 API 的 invalid state 也 fail closed，不產生 manufacturing geometry；
- UI 的「人工只接受整數」不能否決 resolver 自動合法產生的 `.5`。

---

## 4. 十字截角「單邊留肉」真正語意

### 程式證據

- `ae_engine/sheetmetal_geometry.py:190-206`
  - `CornerTypeId.CROSS + CrossCornerMode.RETAIN` 預設 `CornerDirection.WIDTH`。
  - RETAIN 方向只能 WIDTH 或 HEIGHT，不能 BOTH。
  - 留肉量用 `amount_t`。
- `ae_engine/sheetmetal_geometry.py:251-267`
  - legacy C02 正規化為 `CROSS/RETAIN`；旋轉後 WIDTH/HEIGHT 互換。
- `ae_engine/sheetmetal_geometry.py:285-317`
  - direction 只影響局部 `du/dv`；RETAIN 將 delta 取負，代表減少該局部軸截角量。
- `ae_engine/sheetmetal_geometry.py:566-606`
  - canonical corner relief 由 placement 自動映射到 bottom-left/right/top-left/right；物理鏡射不靠 caller 指定「左板／右板 owner」。

### 更正

先前把「單邊留肉」理解成「W seam 兩片板要選一片留肉」是錯的。

正式語意是：**同一物理角落，在局部 WIDTH 或 HEIGHT 其中一軸保留指定 T 倍率**。W-split adapter 只需要把實際物理留肉軸映射到既有 `CornerDirection`；若局部座標旋轉就轉換 direction，不新增 mating-panel owner state。

本功能 0.5T 留肉應使用 `amount_t=0.5`。

---

## 5. `0.5T` 可調值的持久化單位

### 程式證據

- `phase6_settings_center.py:78-85`
  - Relief 等 T-relative 設定保存的是 `*_factor`（0.5、2.0），不是解析後 mm。
- `ae_engine/sheetmetal_geometry.py:295-317`
  - CornerType `amount_t` 在解析時才乘 `thickness`。

### 結論

所有本功能 `xT` 參數保存 dimensionless factor，再乘當前 T：

- endcap retain 0.5T；
- base-plate retain 0.5T；
- side/back rear-panel compensation 0.5T。

例如 compensation factor=0.5：T=2 → 1.0 mm；T=3 → 1.5 mm。resolved mm 是派生值，不應變第二份 Source of Truth。

---

## 6. 側背分離 assembly：能從程式確定什麼、不能假裝確定什麼

### 程式直接證據

- source tree 搜尋不到 `THREE_PIECE_SIDE_BACK_SPLIT`、`SIDE_BACK`、`box_body_structure` 等既成 multi-structure implementation。
- `ae_engine/sheetmetal_features.py:116-167`
  - `BoxBodyFaceContext` 明確定義 user-facing 是 enclosure **outer dimensions**。
  - side face = `(D,H)`、back face = `(W,H)`。
  - thickness compensation 只在 user coordinates → manufacturing/unfolded coordinates 的 boundary 套用。
- `ae_engine/sheetmetal_part_adapters.py:187-238`
  - 現有任意 BoxBody Fold Profile 仍要求 ordered D-W-D core。
- `ae_engine/sheetmetal_part_adapters.py:240-264`
  - 現有 default flat core 以 `D-2T / W-2T / D-2T` 做 manufacturing compensation；使用者 outer D/W 與展開材料長度不是同一層概念。
- `phase6_final_scene_view.py:11-20,57-66`
  - 3D 以 semantic core segment 作 base plane；BoxBody 的中間 W core 是 semantic base。

### 可由既有 convention 約束的新規則

- 側板 formed/outer depth 必須仍是 D；15 mm 後折是額外材料／BEND，不得把成品外深改成 D+15。
- 分件組裝後整體 outer W/D/H envelope 必須仍對應同一箱體 Source of Truth；不得因疊板在某一 renderer 臨時變成 D+T。
- rear-panel compensation 是總寬補償 `c=factor*T`，rear finished width=`W-c`。
- 為保持既有 back-face centerline，audited spec 採中心對稱 `c/2` + `c/2` 作預設 resolver 決策，並要求 golden geometry 驗證。

### 仍不得冒充舊程式答案的部分

現有 source **沒有** side/back 三片板的既成 local origin / assembly transform，因此不能宣稱舊程式已規定「後板固定 D-T、D+T、偏移 1T」等數字。

正確作法是讓新的 resolved geometry 一次輸出三片板 assembly transform/reference plane，再以 golden 3D envelope、mating 無穿透與 2D/3D/output 同源驗證。若未來真實基準檔提供不同證據，再修正中心對稱／reference-plane 決策。

---

## 7. 跨分件 feature clipping 必須保留 process/layer

### 程式證據

- `ae_engine/sheetmetal_features.py:338-345`
  - 互動 process toggle 僅允許 CUTTING/BLIND_HOLE，ProfileFeature 會把 layered profiles 的 layer 一起維持指定 process。
- `ae_engine/sheetmetal_drawing.py:209-240`
  - resolved feature 轉 DrawingPrimitive 時保留 `CUTTING / BLIND_HOLE / MARKING / DATUM` layer；`layered_profiles` 每個 sub-layer 各自帶 layer。
- `ae_engine/manufacturing_api.py:906-924`
  - final material subtraction boundary 明確只處理 `layer == CUTTING` 的 primitive。

### 結論

05 不應只寫「孔輪廓照切」，而要明確成 operation-aware clipping：

- CUTTING：clip 後仍 CUTTING，可切材料；
- BLIND_HOLE：clip contour 後仍 BLIND_HOLE，不得升級成 CUTTING；
- MARKING/DATUM：保留 layer，不可用 seam 補成假封閉 CUTTING；
- layered profile：各 sub-layer 獨立 clip；
- feature Source of Truth 不搬移、不複製。

這個 primitive 應供所有 resolved multi-part topology 共用，因此 07 側背分離不能在 05 尚未完成時另做一套 feature split。

---

## 8. 工單依賴修正

原工單所有票都標 `ready-for-agent`，同時又存在 `Blocked by`，狀態自相矛盾。audited 版已改為：

- 01：ready-for-agent
- 02～09：blocked，前置票完成後再轉 ready

另外只有一項依賴拓撲修正：

- 07 側背分離由「只依賴 01」改為「依賴 01 + 05」。

理由不是為了拆票，而是避免側背分離在 05 operation-aware clipping 尚未存在時自行長出第二套開孔／process split 規則。

---

## 9. 本輪已更新文件

- `PHASE6_BOX_BODY_STRUCTURE_SPEC_CODE_AUDITED.md`
- `PHASE6_BOX_BODY_STRUCTURE_BUILDABLE_SPEC_CODE_AUDITED.md`
- `CONTEXT.md`
- `README.md`
- `tickets/01-...md` ～ `tickets/09-...md`

所有原先已確認的機械規則均保留；新增內容集中在「程式查核補充」區段，方便追溯哪些是本輪由 source code 補定的契約。
