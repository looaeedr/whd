---
whd_doc_role: CURRENT
whd_contract: phase6-assembly-shared-content-presentation
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 組合體／板件功能 shared-content 呈現規則

## Canonical UI ownership

Fold Designer 左側的板件輸入、組合體清單與特殊功能頁面使用**同一個 shared input/display content area**。

### 一般鈑件

- 一般鈑件模式直接顯示該鈑件既有輸入／顯示內容。
- 不再另外保留永久可見的「板件／功能」Structure Tree 區。
- 不以額外的「輸入區」「顯示區」大標籤包覆既有內容。
- layout rehost 不得改 callback、workspace、geometry、manufacturing、persistence 或 sync authority。

### 組合體

只有選到「組合體」時，shared content area 才顯示組合體的板件／功能 presentation。

每個真實板件 row 必須同時保留：

- 原本的顯示／隱藏控制；
- 原本的唯讀成形尺寸；
- 原本的唯讀展開料資訊；
- 原本的唯讀截角尺寸／資料。

資料位於該板件下方，可收合／展開；**fresh 組合體預設全部收合**。收合時顯示／隱藏控制仍須立即可操作。

組合體資料 presentation **不得新增 Entry / Combobox / Spinbox 或其他編輯能力**。組合體只提供既有 show/hide 與 read-only data。

### 多件式 presentation hierarchy

真實 physical-part identity 仍由 workspace / topology / manufacturing authority 擁有。

- 箱身 physical children 保持真實 `box_body:...` identity，畫面上收在「箱身」下。
- 多門 `door_cN_rM` 在組合體畫面可收在 presentation-only「門」父項下。
- 多底板 `base_plate_cN_rM` 在組合體畫面可收在 presentation-only「底板」父項下。
- presentation parent **不得**被插入 workspace、project payload、manufacturing request 或 visibility state map。
- child 的 show/hide、data、part key 與 physical identity 不得因分組改變。

若 topology 中不存在真實 `door` / `base_plate` aggregate，UI 只能建立 presentation group，不得為了畫面方便發明 domain part。

### Collapse / visibility / data state boundary

Collapse/expand 是 presentation state。

- collapse 不得改 visibility；
- visibility 不得刪除、遮蔽或重算板件資料；
- hidden part 的 read-only data 仍可被展開查看；
- runtime page switch / panel rebuild 應保留已存在的 presentation stash；
- collapse state 不得被寫成 geometry/manufacturing/project truth；
- topology refresh 不得把 presentation group 或 collapse state升格成 domain state。

### Navigation / special modes

「組合體」與「截角資料」可由主 selector 進入，但都只是既有 authoritative navigation state 的 presentation projection。

- 組合體沒有第二套 child selector authority。
- 截角資料只搬入口；內部功能、registry authority 與幾何語意不因入口位置改變。
- retired compatibility Structure Tree 物件若暫時仍存在，只能做 hidden compatibility/state projection，**不得 reserve / overlay operator layout pixels**。

### MouseWheel

組合體 scroll handler 必須安全處理 Tk 平台差異；Windows `<MouseWheel>` 的 `event.num` 可能是 `"??"`。非數值 `num` 必須安全視為無 Button-4/5 語意，不得 `int("??")` crash；既有 delta 方向與速度不變。

## Validation boundary

Acceptance 可以驗證 layout、identity、visibility、data availability、navigation、protected files 與 callback parity；不得把 screenshot、reference fixture、expected dimensions 或 test output 回灌 production geometry/dataflow。

## Accepted evidence

#382 T0–T4 最終 combined acceptance RUN `35455382053`：
- relevant headless ownership/persistence：30 PASS / 9 SKIP
- Xvfb layout/navigation：26 PASS / 1 SKIP
- Xvfb physical identity/visibility：5 PASS
- LAYOUT_ONLY = true
- NEW_EDIT_CAPABILITY = 0
- GEOMETRY_OWNER_DRIFT = 0
- DATAFLOW_OWNER_DRIFT = 0
- PROTECTED_DRIFT = 0

## Receiving 後面板 selector / Viewport Overlay 整合契約（CURRENT）

### 後面板形式 selector 可達性

Receiving 箱身的後面板形式是 canonical family state 的操作員 presentation。正式 UI 必須在**箱身的一般輸入區**直接提供且只提供一個可達 selector，選項為「全板／半截／背開孔」；不得要求先解鎖參數、不得把功能藏進第二個 Structure Tree，也不得為了呈現它發明 `box_body:back` 之類新的 operator/domain part identity。

- selector 只投影／提交既有 Receiving family state，不建立第二份 state owner；
- selector 切換後，FinalScene、正式 DXF export、Save→Reload 都必須消費同一 canonical state；
- 「widget 物件存在」不算可達：正式 acceptance 必須驗 normal operator path 上實際 mapped/reachable，且 projection 數量為 1；
- physical multipart identity 仍由 workspace/topology/manufacturing authority 擁有，selector 不得改寫 physical inventory。

### Settings / Diagnostics 的單一 viewport overlay

Settings 與 Registry Diagnostics 共享 `phase6_workspace_shell.py::WorkspaceShellOwner` 所擁有的**單一 viewport overlay host**。它們是 mutually-exclusive presentation overlays，不是新的永久 layout region。

- overlay 顯示／切換不得縮小、重新分配或永久保留 3D viewport/canvas 的 layout pixels；
- overlay host 不得成為第二個 shared-content surface、second composition root 或 application state owner；
- overlay 的存在、focus、scroll 與 diagnostics/settings presentation state 不得改 geometry、manufacturing、workspace identity 或 project persistence authority；
- 驗收除了 `winfo_manager()`，還必須比較實際 viewport allocation / geometry，避免「有 pack 但 viewport 已被吃掉」的假綠燈。

### Scope boundary

Receiving Joint Placement `MARKING` 不屬此 selector / overlay integration contract；不得把 MARKING production 或 renderer 行為偷帶進這條 acceptance chain。

### Accepted provenance

#622 B5 Combined Acceptance：run `36212566772` @ `fc9ad5fcc5c231888b9628eca31df8470affcbb0` GREEN；Headless owner/source gate `21 passed / 1 skipped`，Xvfb integrated operator-path/export/persistence gate `70 passed / 1 deselected / 0 failed`。這些 run/count 只作 provenance；以上 stable presentation contract 才是後續 CURRENT authority。
