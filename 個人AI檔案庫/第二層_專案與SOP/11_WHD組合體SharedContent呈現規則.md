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
