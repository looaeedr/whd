---
whd_doc_role: CURRENT
whd_contract: fold-designer-bridge-ownership
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD Fold Designer Bridge Ownership 規則

## 目的

本文件只定義 Fold Designer / Phase6 UI 邊界目前由哪個模組擁有，以及 `fold_designer_bridge.py` 最終仍允許保留哪些 bootstrap / compatibility responsibility。

它**不定義機械尺寸、截角公式、製造幾何或 DXF 真值**。Geometry、manufacturing、Certified Registry、project persistence 等 domain authority 仍由各自 CURRENT owner 決定；本文件不得以 acceptance 數值或測試輸出覆蓋它們。

## Canonical ownership

### Bridge root

`fold_designer_bridge.py` 是 **composition/bootstrap compatibility root**，不是所有 Phase6 presentation 與 domain 行為的集中實作檔。

Bridge 可保留的責任：

- lifecycle phase / INITIALIZING → READY；
- authoritative mapping/bootstrap orchestration；
- narrow owner-action installation；
- predecessor init invocation 與 install order；
- legacy host compatibility；
- initial mode selection；
- 已核准 compatibility delegates / aliases；
- 尚未形成更深 owner 的 Part Editor compatibility orchestration。

Bridge 不得重新吸回已抽出的 presentation implementation，也不得建立第二個 Settings / Registry / Bending / manufacturing / FinalScene owner。

### FinalScene composition ports

CURRENT composition owner：既有 `Phase6FoldDesignerComposition`。

- FinalScene 的完整 port assembly / wiring 由 application composition owner 建立；bridge 只保留 narrow delegate / bootstrap handoff。
- `Phase6FinalSceneViewAdapter` / renderer owner 不因 composition wiring 搬移而改變。
- manufacturing owner 不因 FinalScene composition wiring 搬移而改變。
- 禁止在 bridge 重新建立 deep `FinalSceneCompositionPorts(...)` constructor；禁止第二個 composition root；owner 不得 reverse-import bridge。

### Derived-part projection / apply

Pure planning owner：`phase6_derived_part_projection.py`。

- Door / BasePlate / BoxBody / Divider / InnerDoor 的 derived projection 必須先形成 immutable `DerivedPartProjectionRequest`，再產生 `DerivedPartSyncPlan`。
- pure planner 不得 import bridge / Tk，不得擁有 `DesignerWorkspace`、workspace/navigation mutation 或 manufacturing geometry formula。
- mutation/apply owner：`Phase6WorkspaceNavigationController.apply_derived_sync_plan`；bridge 不得直接 apply workspace/navigation mutation。
- physical-part identity、project persistence 與 manufacturing authority 不因 projection seam 改變。

### Linked endcap

**Decision：KEEP_COMPATIBILITY。**

Linked-endcap compatibility orchestration 可留在 bridge；不得因此建立新的 domain owner。Derived sync apply 仍由 `Phase6WorkspaceNavigationController.apply_derived_sync_plan` 擁有，bridge direct apply mutation 必須維持為 0。

### Bending UI

CURRENT owner：`phase6_bending_ui.py`。

它擁有：

- `Phase6BendingUI` presentation implementation；
- profile-key presentation resolver implementation；
- symmetry capability/presentation policy；
- BendingUI-only presentation helpers。

Bridge 只可保留必要 compatibility transaction delegate、暫時 monkey-patch / restore seam 與 direct host construction；不得重新定義 BendingUI implementation。

### Settings presentation

CURRENT owner：既有 `phase6_settings_panel.py`。

**Phase 4 decision：KEEP_BRIDGE_COMPATIBILITY。** Exact-six Settings projection/dataflow compatibility functions不另建 competing Settings owner；既有 Settings presentation owner維持不變。

規則：

- Settings presentation cluster 在該 owner 內深化；
- 不建立第二個 Settings panel/module；
- canonical Settings mutation / transaction / state authority 不因 presentation ownership 改變；
- Registry mutation、manufacturing mutation、AssemblyJoint mutation owners 不因 compatibility projection 改變；
- symmetry presentation 已屬 BendingUI 的部分不得在 Settings 重複實作；
- compatibility seam 不得新增 edit capability。

### Registry diagnostics presentation

CURRENT presentation owner：`phase6_registry_diagnostics_panel.py`。

Existing controller/domain owners 繼續擁有 diagnostics/rule/promote/manufacturing semantics。

Presentation panel 不得擁有：

- Certified Registry formula；
- promote semantic；
- manufacturing geometry；
- AssemblyJoint canonical mutation；
- 其他 Registry domain truth。

### Workspace shell

**Decision：NO_EXTRACTION。**

不得僅為縮 LOC 建立 `phase6_workspace_shell.py` 或其他 shallow forwarding wrapper。

Fold Designer 左側仍維持**單一 shared content surface**；一般板件、組合體、截角資料在同一 physical slot 互斥呈現。不得新增：

- 第二個 Assembly region；
- 第二個 Corner Data region；
- 永久 visible wrapper；
- duplicate event binding；
- callback multiplication。

Shared-content 呈現細節由
`個人AI檔案庫/第二層_專案與SOP/11_WHD組合體SharedContent呈現規則.md`
擁有。

### Part Editor

**Decision：C_KEEP_BRIDGE_COMPATIBILITY。**

目前不建立 `phase6_part_editor_session.py`，也不把 `_fix11_activate_part` / save-load 路徑整塊 move-only 到新 class。

Bridge 可保留相容 orchestration，但必須遵守既有 canonical owner：

- part/navigation identity 不得由 UI convenience 改寫；
- project persistence 仍由 project/session owner 擁有；
- update scheduling 仍由 command router / existing update owner 擁有；
- render handoff 不得建立第二個 render authority；
- multipart physical-child identity 仍由 topology/workspace/manufacturing authority 決定。

未來若要改成 A/B extraction，屬新的 ownership-boundary change，必須另有規格與工單 authority；不得把本輪 T9 writeback 當成預先授權。

## `_fix11_init` lifecycle boundary

`_fix11_init` 必須維持 **bootstrap-only lifecycle root**。

允許：

- lifecycle phase；
- authoritative mapping bootstrap；
- narrow owner-action installation；
- predecessor init；
- owner install order；
- legacy host compatibility；
- INITIALIZING → READY；
- initial mode selection。

禁止：

- 深層 Settings construction；
- FinalScene deep-owner construction；
- BendingUI implementation；
- Registry diagnostics implementation；
- 另建 second composition root。

DoD 是 ownership / lifecycle 語意，而不是 LOC threshold。

## Reverse-import / composition boundary

- root `phase6_*.py` owner 不得 reverse-import `fold_designer_bridge.py` 形成依賴環；
- composition root 必須維持單一；
- facade / compatibility binding 只准收斂，不得因抽模組增加第二套 service-bag ownership；
- owner module 可接受 narrow callback/action seam，但不得依賴完整 bridge/app surface 才能工作。

## Validation 與 domain truth 邊界

下列內容只能當 validation/evidence，不會因寫進 test、checkpoint、Issue、RUN artifact 或本文件而升格成 production mechanical authority：

- pytest expected；
- screenshot / bbox / pixel measurement；
- current runtime output；
- candidate/baseline pass counts；
- DXF verifier reconstruction；
- temporary QA probe；
- acceptance RUN id / artifact；
- LOC / AST census 數字。

真正的 geometry / manufacturing / persistence / Registry domain answer 必須由對應 CURRENT owner 產生；validation 只判斷是否漂移。

## Integration / future change contract

變更本 ownership boundary 時：

1. 先讀 Canonical Authority Map 與本文件；
2. 若是新 extraction / new owner / new composition boundary，必須先有 accepted spec；
3. 保持 branch-first、single execution claim、non-force integration；
4. owner 搬移必須同一變更完成新 owner、舊 owner降級/刪除、reverse-import guard 與直接回歸；
5. 不得用「bridge 太長」本身作 extraction authority；
6. focused GREEN 不等於 final acceptance；若改動影響實體板件、2D/3D、DXF、persistence，仍須走對應 final acceptance。

## Accepted lineage provenance

本 CURRENT contract 由 #441 ownership-refactor chain 與 #486 Phase 4 ownership chain 的已接受 decisions 收斂而成。

既有 #441 stable decisions：

- Bending UI owner：#444；
- Settings presentation owner：#445；
- Registry diagnostics presentation owner：#446；
- Workspace shell NO_EXTRACTION：#447；
- Part Editor C_KEEP_BRIDGE_COMPATIBILITY：#448；
- `_fix11_init` bootstrap-only：#449；
- Combined invariant acceptance：#450。

Phase 4 #486 stable decisions：

- FinalScene composition ports owner → existing `Phase6FoldDesignerComposition`：#479；
- immutable derived-part projection planning → `phase6_derived_part_projection.py`：#480；
- derived sync apply → `Phase6WorkspaceNavigationController.apply_derived_sync_plan`，linked endcap `KEEP_COMPATIBILITY`：#481；
- Settings exact-six decision → `KEEP_BRIDGE_COMPATIBILITY`，existing `phase6_settings_panel.py` presentation owner unchanged：#482；
- compatibility ratchet / dead-glue cleanup與 Combined Acceptance由 #483/#484 驗證，沒有建立新的 domain authority。

以上 issue/run/commit 只提供 provenance；**本文件的 stable ownership contract 才是後續 routing 要讀的 CURRENT 規則**。
