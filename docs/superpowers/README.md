# Superpowers 接手說明 — 2026-08-21 截角類型／裝配語意

任何接手這次修改的代理或開發者，請依序閱讀：

1. `specs/2026-08-21-corner-type-semantic-assembly-design.md` — 已確認的工廠規則、資料責任與不可回退決策。
2. `plans/2026-08-21-corner-type-semantic-assembly-implementation.md` — 實作任務、修改檔案、介面與已完成項目。
3. `verification/2026-08-21-corner-type-semantic-assembly-verification.md` — 測試、DXF 製造驗證、原始 renderer 不變與行尾注意事項。
4. `../../修改日誌/20260821.md` — 人員可快速閱讀的修改摘要。

## 語言規則

- **使用者可見介面一律使用繁體中文。**
- 新增或修改的操作說明、錯誤訊息、固定截角摘要與交付文件應優先使用繁體中文。
- **程式內部識別字**（Python 類別、函式、enum、欄位、API 參數與相容代碼）為避免破壞相容性可保留英文，例如 `CornerTypeId`、`CrossCornerMode`、`INSERT_OVERLAY`。
- 文件若必須提到英文識別字，需同時用繁體中文說明其製造意義，不能只留下英文名稱讓操作人員自行猜測。

## 不可回退的關鍵決策

- 截角類型本身就是裝配關係；不要再新增另一套可獨立修改的裝配旗標。
- 新 GUI 禁止回到 `C01~C04` 或 `0°/90°` 的截角操作方式。
- 嵌入貼外型第二級參數在 UI 仍叫「嵌入留肉」，但**正確二級 CUTTING = 側折 + 嵌入留肉量**；`FW - 嵌入留肉量` 只是兩級切線之間剩下的材料寬度，不是切線座標。
- 純嵌入會讓箱身高度由 `H-2T` 變成 `H-T` 或 `H`；孔位與特徵基準必須同步。
- `fold_designer_original.py` 的製造幾何與操作模型保持不動；本次只允許為「全域文字縮放」增加字級倍率。
- 型號 UI 使用「自訂」；它是目前已知資料的可編輯副本，不是另一套空白預設。舊「未知類型」只做相容讀取。
- 指示燈盒與指示燈小門是共享固定板件，截角類型唯讀。

## 2026-08-21 晚間修正

- 已撤銷先前錯誤的 `39mm` 二級截角規格。`側折=15、T=2、嵌入留肉=0.5T` 時，正確二級 CUTTING 為 `16mm`、深度 `4mm`。
- 新增全域 **文字大小：小 / 中 / 大**。現有字級定義為「小」；中為 `1.2×`、大為 `1.4×`。
- 文字縮放只改 Tk/ttk/Canvas/Matplotlib 文字，不改 CAD 幾何、畫布座標、DXF 尺寸或折彎數值。
- 交付與 patch 不覆蓋現場 `config.ini`；使用者切換文字大小時才由程式寫入 `[UI] text_size`。
## 2026-08-23：Phase6 截角／貼外型後續修正

本輪接手時，除上列既有文件外，必須再遵守以下已確認規則：

- **上方 CornerType 是封頭／封尾裝配語意真值。** `assembly_type` 只能作 UI／相容 mirror，不得在載入時反向覆寫上方 CornerType。
- **貼外型（`OVERLAY`）的封頭／封尾沒有左右 X 向折彎。** 因此 2D／3D 不生成這些 X 向 BEND，Fold Designer 的 Head/Tail 不顯示 X 軸折彎頁。
- **OVERLAY 的 X 材料外框同樣沒有舊折邊寬。** Head/Tail flat span = `W`；不得保留 `W-4T+yl1+yr1` 的舊 INSERT 型材料寬。下方 `WIDTH+1.5T` 只屬角落 CUTTING。
- **使用者明確選擇 `OVERLAY` 時，下方截角帶入既有 CROSS 多切預設：`EXTRA_CUT + WIDTH + 1.5T`。** 這只是本次選擇時的初始值；之後使用者仍可改成高、寬＋高或其他既有 CROSS 設定。普通 refresh/load 不得把人工修改洗回預設。
- `CROSS + EXTRA_CUT` 是通用幾何手段，不等同單一機械目的；可用於避讓自身折邊，也可用於避讓組裝後另一片板金。不得因此新增重複 CornerType。
- 自訂模式不載基準 DXF，因此基準檔專屬開孔／固定孔設定不得在自訂模式顯示；也不得從「進階設定」繞路重新出現。
- 箱身「對稱折彎」入口放在 Fold/BEND 編輯區；對稱模式下刪除可刪折段時，鏡像段必須交易式同步刪除。
- 3D Fold Designer 是 modal transaction：開啟期間主 2D 不得同時修改；確定才提交，取消／關閉丟棄草稿。
- 2D CornerType 縮圖方向依 active target：上方維持垂直翻轉，下方恢復原始方向；只改 preview canvas，不改製造幾何。
- UI 數值不得露出 `400.0000000000006` 類浮點尾差；近整數只做文字正規化，合法小數保持。
- **不得碰 `config.ini`，除非使用者明確要求。** 交付固定提供完整包與只含本次變更檔的更新包，FULL/UPDATE 檔名共用 Asia/Taipei `YYYYMMDD_HHMMSS` 時間戳。

詳細截角層級與 OVERLAY 規則見 `specs/2026-08-21-corner-type-semantic-assembly-design.md` 的 2026-08-23 補充。


## 操作員使用說明書

- `../../使用說明書.md` — 使用者操作手冊；現已包含正式截角類型、十字截角模式、方向、xT、封頭／封尾上下截角用途與舊 C01~C04 對照。

- **板件存在狀態全鏈規則**：`existing_parts` 是 physical presence 單一真值；輸出 checkbox 不得決定存在性。刪除板件要同步從左側尺寸、右側 2D、3D、FinalScene、保存/重載與 DXF/NC/批次輸出消失，profile stash 只供重新新增恢復。
- **除錯範圍規則**：修一個症狀必須主動追完整資料鏈，不等待使用者逐層提醒相依問題。

## 2026-08-23：全域專案檔案操作（取代舊 3D Footer 讀／存入口）
- `.p6fold` 是**整個專案**；主視窗左上角固定提供「開啟專案 / 儲存專案 / 另存新檔」。3D 是 modal，因此 3D 視窗左上角也提供同一組全域入口；不得綁在某一板件頁或 3D Footer。
- 各板件頁／3D 編輯器只負責自己的 draft 交易：`套用 / 確定 / 取消`；不得把局部交易按鈕命名或實作成全專案存檔。
- `開啟專案` 與 Windows 雙擊 `.p6fold` / argv 共用主 GUI 的 authoritative `load_phase6_project()`；不得建立第二套 restore 邏輯。
- `儲存專案`：已有目前路徑時直接覆存完整 `.p6fold`；無路徑時轉入「另存新檔」。`另存新檔` 才詢問新路徑。
- GUI 全域「開啟專案」只還原主專案，不強迫跳進 3D；雙擊 `.p6fold` 的啟動流程可依既有 argv 行為開到保存的 active part。
- 讀檔後 `existing_parts`、2D/3D、輸出資格、CornerType/Fold/features 與全域尺寸必須同步來自同一 snapshot。

## 2026-08-23：CornerType 細參數鎖
- CornerType 細參數預設 **鎖定並真正隱藏**；2D/3D 都必須有明確 `參數鎖定 / 參數解鎖` 文字。鎖定時細節 frame 與 `左右相同` 等進階控制零佔位，只保留 CornerType/摘要供辨識。
- 鎖只是 UI 防誤觸，不是製造資料；鎖定／解鎖不得修改 `CornerTypeSelection`，也不保存成 `.p6fold` 機械狀態。載入專案後 UI 一律回到鎖定。
- 自訂盤型：CornerType 類型照既有規則可選；細參數需解鎖才可改。
- 已知盤型：factory CornerType **類型固定不可改**，但同一類型的細參數可解鎖微調；人工細參數必須走完整 Save/Load、2D/3D、baseline manufacturing 鏈而保留。
- 已知盤型細參數覆寫不得讓板件退化成自訂 builder；基準 DXF、固定孔、MARKING 等 secondary entities 必須保留，只替換由 Corner policy 決定的 structural outline / BEND。
- `indicator_box` / `indicator_door` 是固定共享板件：維持真正唯讀，不提供解鎖。

## 2026-08-23：ProjectSession 專案交易所有權
- `phase6_project_session.py` 是 `.p6fold` 專案交易生命週期的唯一協調層，正式區分 `project_path / loaded_baseline / committed / draft`。
- `loaded_baseline` 只代表最近一次成功載入的原始 snapshot；主 GUI 後續修改與 3D 確定不得反向改寫它。
- `committed` 是正式專案 Source of Truth；全域 Save / Save As 只可保存 committed 機械狀態。
- `draft` 是 3D transaction 的隔離種子／生命週期標記，不是每個 Tk 欄位的 live mirror。Fold Designer 在自己的 defensive copy 編輯；取消丟棄，確定後先套回 main GUI，再以 canonical main snapshot commit。
- active draft 存在時 `capture_committed()` 必須拒絕，防止 caller 繞過 transaction；明確的 `load_project()` 才能取代舊交易並清除 draft。
- main-connected 3D `儲存專案 / 另存新檔` 必須委派 main GUI committed save；不得由 Bridge 把 staged 3D workspace 直接寫成正式 `.p6fold`。
- `active_part` 是純導航 metadata：3D Save 時可保存目前板件位置，但僅限該板件已存在於 committed `existing_parts`；尺寸、CornerType、Fold Profile、開孔與板件增刪仍不得從未確定 draft 滲入。
- `_runtime_project_path` 只屬執行期資訊，不得持久化進 `.p6fold`。
- 詳細設計：`specs/2026-08-23-phase6-project-session-design.md`；驗證：`verification/2026-08-23-phase6-project-session-verification.md`。

## 2026-08-23：Settings 單一 Runtime 狀態來源
- `phase6_settings_center.py` 的 `SettingsService` 是 Phase6 **已確認 Runtime Settings** 唯一所有者；`Phase6Settings` 提供 immutable / defensive snapshot。
- `config.ini` 只代表**下次啟動的 persisted defaults**，不是目前 Runtime Source of Truth；寫入預設值不得順便提交目前 Runtime。
- `ae.default_config` 繼續是「還原初始值」唯一 Factory Defaults 來源，不受目前 Runtime 或 `config.ini` 後續變更影響。
- Main GUI 的 Tk 變數只是 UI mirror；主畫面設定變更必須經 `SettingsService.update()` 正規化並同步 AE compatibility globals。
- Fold Designer `_settings_values` 保留為 3D transaction-local draft；取消不提交，確定後才由 main GUI 經 `SettingsService.update()` 成為 committed runtime。
- 3D「儲存為預設值」使用 `SettingsService.persist_defaults(...)`：可把 draft 寫入 `config.ini` 供下次啟動使用，但當下 service 與 AE runtime 必須保持原 committed 值。
- `save_defaults_to_ini(..., apply_runtime=True)` 僅保留舊 caller 相容；新 production ownership 路徑由 service 以 `apply_runtime=False` 呼叫。
- 詳細設計：`specs/2026-08-23-phase6-settings-single-source-design.md`；驗證：`verification/2026-08-23-phase6-settings-single-source-verification.md`。


## 2026-08-23：GUI Project Controller seam
- `phase6_project_controller.py` 是主 GUI 的**專案 use-case Controller**；它隱藏 `.p6fold` 持久化與 ProjectSession ordering，GUI 不得重新實作 active-draft Save 判斷。
- `ProjectSession` 仍是交易 Source of Truth；Controller 不得保存另一份 committed/draft/path mirror。
- GUI 是 View adapter：`_compose_phase6_project_snapshot_from_main_gui()` 負責 View → canonical snapshot，`_apply_phase6_project_snapshot()` 負責 snapshot → View；不要把 Tk widget 或 renderer 搬進 Controller。
- Controller 的 `snapshot_provider` 是刻意的 interface：active draft Save 時 provider 不會被呼叫，讓「未確認資料不得進正式檔」成為模組 invariant，而不是 caller 默契。
- `active_part` 仍是導航 metadata，只有 committed `existing_parts` 內既有板件可覆寫；不得擴張成提交機械 draft 的旁路。
- 詳細設計：`specs/2026-08-23-phase6-gui-project-controller-design.md`；驗證：`verification/2026-08-23-phase6-gui-project-controller-verification.md`。

## 2026-08-23：Workspace Controller seam
- `phase6_workspace_controller.py` 是主 GUI committed workspace 的唯一狀態模組，擁有 `existing_parts / active_part / part_profiles / box_body_profile` 與其 invariant。
- `box_body` 永遠存在；authoritative workspace 建立後，export checkbox 或 legacy indicator fallback 只能影響顯示／輸出選擇，不能反向改寫 physical presence。
- 刪除板件只改 presence，不刪除 profile stash；重新新增可復用原 profile。若刪到 active part，Controller 自動回退到合法板件。
- `fold_designer_part_bundle / _phase6_existing_parts / _fold_designer_last_part_key / fold_designer_box_body_profile` 只保留 compatibility property，不能再有 backing state；production method 不得依賴這些 alias。
- Head/Tail linked profile 的幾何推導仍在既有 geometry resolver；Workspace Controller 只保存最終結果，不得 import Tk 或 AE。
- 專案 workspace replacement 要區分：`box_body_profile` 欄位存在且為 `None` = 明確清除舊 Fold Chain；欄位不存在 = partial update，保留現況。
- 詳細設計：`specs/2026-08-23-phase6-workspace-controller-design.md`；驗證：`verification/2026-08-23-phase6-workspace-controller-verification.md`。

## 2026-08-23：Fold Designer Bridge domain ownership seam
- `phase6_endcap_semantics.py` 是 EndCap assembly/FW/raw CornerType 狀態的 owner；`assembly_type` 仍只是由 Head/Tail 上方 CornerType 推導出的相容／顯示 mirror。
- `phase6_fold_profiles.py` 是 BoxBody/EndCap Fold Profile 與 linked mating chain 的 owner；profile build/read/merge 與 outside-dimension compensation 不再實作在 Bridge。
- `fold_designer_bridge.py` 保留 Fold Designer/Tk transaction、View/Scene adapter 與 compatibility re-export；不得重新實作已移出的 domain 規則。
- `gui.py` 直接 import 真正 owner，不能把 Bridge 當成 domain facade 再把所有規則集中回同一大檔。
- Compatibility re-export 必須是同一 function object，不可新增 wrapper 或 alternate branch。
- 詳細設計：`specs/2026-08-23-phase6-fold-designer-bridge-slim-design.md`；驗證：`verification/2026-08-23-phase6-fold-designer-bridge-slim-verification.md`。

- 2026-08-23：FinalScene 3D View ownership → `phase6_final_scene_view.py`；Bridge 只保留 query/request adapter。詳見 `specs/2026-08-23-phase6-final-scene-view-design.md`。

## 2026-08-23：診斷快照所有權接縫
- `phase6_diagnostics.py` 是 Phase6 診斷 schema、JSON-safe、Scene／Material／FoldGuide 序列化與 all-part Final Geometry diagnostics 的 owner。
- `fold_designer_bridge.py` 只保留 Designer state → diagnostic context、manufacturing payload/provider adapter 與 Tk 檔案對話框；不得重新實作 diagnostics serializer。
- standalone diagnostic 與 `.p6fold.final_geometry` 共用同一序列化規則，避免 schema／error handling 雙軌漂移。
- Diagnostics 不擁有 ProjectSession、Settings、CornerType、Fold Profile 或 manufacturing build；診斷資料不能反向成為機械 Source of Truth。
- 詳細設計：`specs/2026-08-23-phase6-diagnostic-snapshot-design.md`；驗證：`verification/2026-08-23-phase6-diagnostic-snapshot-verification.md`。

## 2026-08-23：3D Designer 草稿工作區所有權
- `phase6_designer_workspace.py` 是 Fold Designer 內部草稿工作區的唯一生命週期 owner，集中管理板件 presence、active/selected、profile/feature stash、dirty 與 switching 狀態。
- `fold_designer_bridge.py` 保留 Tk／Editor／manufacturing adapter：從 Bend UI、孔位 editor 與 Settings draft 收集資料後寫入 Workspace；Workspace 不得 import Tk、AE、renderer、ProjectSession 或 SettingsService。
- `available_parts / active_part_key / selected_part_key / _phase6_part_profiles / _phase6_part_features / _phase6_part_face_features / _phase6_workspace_dirty / _phase6_switching_part` 僅保留 compatibility property，禁止形成第二份 backing state。
- 板件切換 ordering 固定為：先保存 outgoing draft，再 `begin_switch(target)`，最後完成 target UI／holes／settings／FinalScene 同步後 `finish_switch()`；Workspace 不負責任何 UI 副作用。
- 刪除板件只移除 presence，不刪 profile／feature stash；重新加入時優先恢復 stash。`box_body` 永遠不可刪。
- Project snapshot、Diagnostics 與 Scene query 的 presence／active／profile／features 必須從同一 `designer_workspace.snapshot()` 或同一 owner 取得，不可重新手拼 legacy state。
- 詳細設計：`specs/2026-08-23-phase6-designer-workspace-design.md`；驗證：`verification/2026-08-23-phase6-designer-workspace-verification.md`。

## 2026-08-23：統一開孔編輯器交易狀態機
- `phase6_hole_editor_session.py` 的 `Phase6HoleEditorSession` 是統一開孔編輯器 transaction state 的唯一 owner，集中管理 context、selection、active edit before snapshot、Undo 與 Confirm/Cancel ordering。
- Tk/Canvas 仍只負責事件、顯示與幾何 candidate 計算；孔位 surface、hit-test、reference distance、round-fill、Indicator geometry 仍由既有幾何 owner 負責。
- transient edit 使用整個 active context 的 before snapshot，因此插入、拖曳、旋轉、十字基準、reference distance、圓孔排列 preview 共用同一 Cancel/Undo 語意。
- process toggle、delete 是 immediate committed action；Session 先處理未完成 active edit，再推 Undo snapshot，禁止 caller 各自維護第二份 `active_snapshot / undo_history`。
- context switch 一律先取消未確認 transient edit，切換後 selection 與 Undo scope 重置；Cancel All 恢復所有已登錄 context 的 original snapshot，Confirm All 保留現況。
- `_open_unified_hole_editor()` 不得再直接 `append/del/item assignment` 修改 `feature_list`；mutation 必須經 Session action。
- 詳細設計：`specs/2026-08-23-phase6-unified-hole-editor-session-design.md`；驗證：`verification/2026-08-23-phase6-unified-hole-editor-session-verification.md`。


## 2026-08-23：統一開孔編輯器 Canvas View ownership
- `phase6_hole_editor_canvas_view.py` 的 `Phase6HoleEditorCanvasView` 是統一開孔編輯器 Canvas transform、resolved-feature cache、hit-test 與浮動參考框 placement 的唯一 View owner。
- `Phase6HoleEditorSession` 仍是開孔 transaction Source of Truth；Canvas View 只讀 feature list，不得修改孔位資料。
- `_open_unified_hole_editor()` 保留 Tk 組裝、domain adapter、Door/Indicator extension 與 event orchestration，但不得再自行維護 `transform_box`、重做 `resolve_surface_features()` 或 hit-test。
- Door enclosure／indicator manufacturing preview 透過 `draw_extra` callback 注入，View 不 import `manufacturing_api`，避免顯示層變成第二個製造幾何 owner。
- mouse event 固定走 `canvas_view.canvas_to_world()`／`canvas_view.hit_test()`，因此 redraw 與點擊命中共用同一 transform／resolved cache。
- 詳細設計：`specs/2026-08-23-phase6-hole-editor-canvas-view-design.md`；驗證：`verification/2026-08-23-phase6-hole-editor-canvas-view-verification.md`。


## 2026-08-27：Shared Assembly World Geometry 與最新 3D Designer 導航
- `ae_engine/assembly_geometry.py` 是 Folded Mesh 與 Assembly Placement 的共同 Source of Truth；`phase6_final_scene_view.py` 與 `ae_engine/assembly_collision.py` 都委派同一套 world geometry。
- 第一階段 assembly scene 僅包含 `box_body / head / tail`，不混入 door / base plate。
- 最新 UI 不再使用獨立 `單件 / 組合體` 模式按鈕：`組合體` 直接是左側 `板件選擇` 第一項，第一次進 3D 預設顯示組合體；選實際板件自動切 single-part editor。
- 最上列固定：檔案、3D 顯示（文字大小/折彎透視/面板透視）、全螢幕、還原初始值/取消/確定。全域設定固定兩行：基準型號/參數鎖定/儲存預設值；W/H/D/T/結構/組合方式。
- 右側不再有 duplicate control bar；只保留解鎖後板件設定／組合體診斷與 3D canvas。組合體模式不顯示一般板件設定；解鎖時顯示組合體診斷。
- UI 驗收使用真 Tk，檢查 menu 第 0 項、初始 assembly mode、widget master/grid row 與切換實際板件後 single mode。
- 詳細驗證：`verification/2026-08-27-3d-layout-assembly-entry-verification.md`。
- 2026-08-28 組合體接合／實體板最新語意：assembly placement 必須消費 `組合方式 -> CornerType -> resolved Fold Profile`；EndCap local `z=0` 是板厚**中心面**、local `+z` 是折邊朝箱內方向。Head +Z 向下；Tail 保持 authoritative native X/Y orientation（禁止二次上下鏡射），+Z 向上。組合體以真實 `T` 將 mid-surface 生成內外兩個 skin；中心面向箱外偏移 T/2，使內側 skin 貼箱身、外側成型面位於箱外。`OVERLAY` X flat、`INSERT / INSERT_OVERLAY` X folded。viewer 與 collision 共用 `ae_engine.assembly_geometry` physical-sheet geometry；不得再把零厚度 z=0 中心皮當 mating face。另保留 `組合體 -> 箱身` 不得 early-return 的 UI 切換規則。詳細驗證：`verification/2026-08-27-assembly-semantic-mating-and-switch-verification.md`、`verification/2026-08-28-endcap-physical-sheet-assembly-verification.md`。

- 2026-08-28：EndCap physical-sheet 組合體孔／折彎稜線顯示回歸已修正；closed solid 不再被誤當唯一 edge source，孔輪廓與真實 crease 從 folded mid-surface 抽取。驗證：`verification/2026-08-28-endcap-assembly-edge-visibility-verification.md`。
- 2026-08-28 06:49：EndCap 孔口顯示再修正：mid-surface hole outline 會被 physical skin 遮蔽，因此組合體改由 thickened solid 的非共面 physical feature edges 顯示真正位於 ±T/2 skin 的 through-hole rim；3D BEND guide 全部改為 solid `-`。同一 verification 文件已追加 RED/GREEN 與真 GUI 驗證。

- 2026-08-28 08:00：組合體參數解鎖新增診斷面板；固定截角診斷的碰撞 probe 已收斂為 `restored - production` relief delta，禁止整片 EndCap surface crossing，避免正常 mating seam 整圈誤紅。標準金庫型由早期無效的 947 段整圈交線收斂為 454 段局部角落交線（Head/Tail 各 227）；命中的 delta triangles 可畫半透明紅面並疊紅色實線。關閉忽略固定截角時不執行此 probe。正式 CUTTING/DXF 暫不刪固定截角；renderer 不得依賴 `assembly_collision` solver，純診斷 geometry 位於既有 `assembly_geometry.py`。AI 交付前須自行檢查 Head/Tail 視角。驗證：`verification/2026-08-28-assembly-interference-diagnostic-verification.md`。


## 2026-08-28：3D 干涉反投影正式截角
- 設計：`specs/2026-08-28-assembly-relief-backprojection-design.md`
- 實作計畫：`plans/2026-08-28-assembly-relief-backprojection.md`
- 驗證：`verification/2026-08-28-assembly-relief-backprojection-verification.md`
- 固化結論：固定截角只保留作 corner topology/search domain；正式 Head/Tail CUTTING 尺寸由 world-space physical interference 反投影 flat UV 後求得，加入 A 後再折回 3D，零材料穿透才可 verified。verified cut 進 `EndCapPartSpec` / Manufacturing API，2D/3D/DXF 共用；BEND 依新 material 重新 clip。

## 2026-08-28 19:00 組合體介面同步修正
- Verification: `docs/superpowers/verification/2026-08-28-assembly-scene-contract-sync-verification.md`
- 重點：UPDATE 必須成對同步 `fold_designer_bridge.py` caller 與 `phase6_final_scene_view.py` 的 `AssemblySceneRenderData` contract；交付前必須用舊 FULL 疊 UPDATE 的真主 GUI 路徑驗證。


## 2026-08-28 參數解鎖面板可見性
- 組合體/單件右側可切換設定面板必須透過 `_phase6_pack_right_panel_above_canvas()` 插在 Matplotlib canvas 前方；`winfo_manager()==pack` 不足以證明可見。
- 真 Tk 回歸必須 `parameter_lock_button.invoke()` 後驗 `winfo_viewable()==1` 且高度 > 1。
- 驗證：`verification/2026-08-28-parameter-lock-panel-visibility-verification.md`。
