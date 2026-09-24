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

### Derived-part projection / request assembly / apply

CURRENT pure projection/request owner：`phase6_derived_part_projection.py`。

- Door / BasePlate / BoxBody / Divider / InnerDoor 的**domain derivation**仍由既有 canonical domain/application owners完成；Bridge 可負責蒐集/呼叫這些 authoritative derivations，但不得複製公式。
- 已完成的 derived projections 必須封裝成 `DerivedPartRequestAssemblyInput`，由 `build_derived_part_projection_request(...)` 統一組裝 namespace replacement、remove/add/stash intent 與 legacy active/selected repair，產生 immutable `DerivedPartProjectionRequest`。
- `build_derived_part_sync_plan(...)` 繼續把 immutable request 轉為 `DerivedPartSyncPlan`。
- pure projection/request owner 不得 import bridge / Tk，不得擁有 `DesignerWorkspace`、workspace/navigation mutation 或 manufacturing geometry formula。
- mutation/apply owner仍是 `Phase6WorkspaceNavigationController.apply_derived_sync_plan`；Bridge 不得直接 apply workspace/navigation mutation。
- `fold_designer_bridge.py::_phase6_sync_authoritative_derived_parts` 不得重新建立本地 `remove_part_keys / add_parts / stash_profiles / stash_features / active_repair / selected_repair` ownership；它只保留 domain projection assembly → pure request owner → immutable plan → navigation apply 的 narrow orchestration。
- physical-part identity、project persistence 與 manufacturing authority 不因 projection seam 改變。
- Phase 6 / #530 Deletion-Test 已 supersede「request assembly 留在 Bridge」的舊實作邊界；CURRENT decision = `DEEPEN_DERIVED_PROJECTION_OWNER`。

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

## Phase 5 — Settings mutation / dataflow ownership

Phase 5 收斂的是跨 owner 的 Settings application sequencing 與 pure planning 邊界；它**沒有建立第二個 Settings domain owner**，也沒有改變既有 geometry / manufacturing / Registry / persistence authority。

### Application sequencing / effect owner

CURRENT application sequencing owner：`gui_modules/application/fold_designer_settings_coordinator.py::Phase6FoldDesignerSettingsCoordinator`。

- 它擁有跨 owner 的 effect ordering / orchestration：canonical Settings commit 前後的 compatibility effect、profile/dimension plan、workspace/profile apply、UI projection、update intent、host/live notification 等 sequencing。
- 它只透過 `phase6_settings_contracts.py` 的 bounded typed contracts / ports 取得能力；不得持有 full bridge/app service bag，也不得用 arbitrary `getattr(self, ...)` 擴張權限。
- 它**不擁有** W/H/D/T/FW、Corner、Registry、AssemblyJoint、manufacturing geometry、workspace identity、project persistence、family-model semantic normalization 或 canonical Settings transaction semantics。
- 唯一 composition root 仍是既有 `Phase6FoldDesignerComposition`；不得因 Settings coordinator 另建第二個 composition root。
- `fold_designer_bridge.py` 在這條路徑只保留 narrow compatibility delegate / bootstrap handoff，不再擁有 deep Settings apply/update effect ordering。

### Settings → Profile pure projection owner

CURRENT pure planning owner：`phase6_settings_profile_projection.py`。

- Settings → part-dimension / profile projection 必須先形成 deterministic immutable plan，再交給既有 workspace/navigation owner apply。
- pure projection 不得 import Tk / bridge，不得擁有 `DesignerWorkspace`、workspace mutation、render、live publish 或 mechanical/manufacturing formula。
- authoritative dimension/profile builders與既有 family / topology policy 仍是語意來源；planner 只能組合/投影，不得複製公式。
- workspace/profile mutation 與 derived-part apply 仍由既有 `Phase6WorkspaceNavigationController` / derived-part planner+apply seam 擁有；physical-part identity authority 不變。

### Baseline transition / factory reset

- `commit_family_model_transition(...)` 與既有 Settings transaction/transition owner仍是 baseline/family semantic authority。
- `Phase6FoldDesignerSettingsCoordinator` 只擁有 baseline/model transition 與 factory reset 的 cross-owner effect sequence，不得取代 semantic owner。
- factory source 仍是 immutable AE factory defaults / existing SettingsService factory snapshot contract；reset 不得繞過 typed Settings application flow，也不得偷偷清除既有 baseline/corner transaction state。

### Part Editor Settings commit seam

Phase 4 / #448 的 `C_KEEP_BRIDGE_COMPATIBILITY` 與 Linked Endcap `KEEP_COMPATIBILITY` 仍受保護。

- `_fix11_save_current_part` / `_fix11_activate_part` 可保留 compatibility orchestration，但 canonical Settings mutation 必須走既有 Settings coordinator/controller seam。
- editor-value save 只提交實際 changed Settings delta；no-op 不得產生 host notification。
- FW explicit operator takeover 仍由既有 EndCap/FW semantic owner決定；linked Head/Tail refresh 只能經 narrow compatibility port 觸發。
- 不建立 `phase6_part_editor_session.py`，也不把 Part Editor compatibility 誤升格成新的 domain owner。

### Live-sync pure planning owner

CURRENT pure publication-plan owner：`phase6_sync_envelope.py`。

- fingerprint / delta / revision / transaction-id / immutable envelope / anti-echo / host-relief repair intent 必須由 pure plan 產生。
- planner 不得呼叫 host callback、不得 mutate app/bridge、不得寫 status/project state、不得 mutate manufacturing state。
- callback execution、成功/失敗 bookkeeping 與 application effects 留在 application/coordinator layer；callback failure 不得先提交 success bookkeeping。
- unchanged fingerprint 不 publish；`force=True` 不等於 unconditional resend；revision/transaction identity 必須維持 accepted parity。

### Phase 5 permanent structural invariants

- Settings presentation owner仍是 `phase6_settings_panel.py`；Phase 5 application coordinator不形成 competing panel/domain owner。
- root owner modules不得 reverse-import `fold_designer_bridge.py`。
- second composition root = 0。
- bridge facade / compatibility surface只能收斂；Phase 5 Combined Acceptance 的 facade binding ceiling 為 69，但該數字只是 ratchet evidence，不是 domain truth。
- config / DXF protected objects與 Phase 4 protected owner decisions不得因 Settings dataflow 收斂而漂移。

### Phase 5 accepted provenance

- #497：T0 ownership census / fixed baseline；
- #498：typed Settings application coordinator / bounded ports；
- #499：Settings apply/update sequencing ownership；
- #500：Settings→Profile pure projection ownership；
- #501：baseline transition + factory reset application flow；
- #502：Part Editor editor-value Settings commit seam；
- #503：live-sync envelope pure planning ownership；
- #504：Combined Acceptance；final RUN `35746442145` @ `65d670285a7f5bfb1a4b0ae9fb9ffb4815d601ce` GREEN，Headless / Xvfb candidate-only failures 均為空，structural/protected gates GREEN。

以上 ticket / RUN 只提供 provenance；本節定義的 stable ownership boundary 才是後續 routing 要沿用的 CURRENT contract。



## Phase 6 C1 — Permanent Bridge anti-regrowth machine guard

CURRENT permanent structural ratchet for the accepted Phase 6 Bridge surface:

- The anti-regrowth gate is a **permanent machine guard**, not a one-shot acceptance workflow. It must remain runnable after C1 acceptance and must continue protecting later changes.
- Bridge LOC/facade limits must read their accepted durable record/symbol authority; do not duplicate stale numeric literals in a second policy source.
- Any net-new top-level Bridge body greater than 40 lines requires explicit architecture review/evidence before acceptance.
- Facade compatibility surface is non-growth by default; new bindings require explicit compatibility authority and must not silently restore removed wrapper ownership.
- Extracted-domain implementation must not be redefined in `fold_designer_bridge.py`; reverse-import Bridge count must remain 0; second composition root count must remain 0; full-app owner/service-bag interfaces remain prohibited.
- A GREEN anti-regrowth run validates structural invariants only. It does not become geometry/manufacturing/persistence domain truth and does not replace domain-specific final acceptance when those domains change.

Accepted C1 provenance: owning Issue #533, tested HEAD `09e19c06cffcee6521483eb84b16d47cf7d5ad3c`, permanent anti-regrowth RUN `35867336375` GREEN. Provenance identifies the accepted ratchet; the rules above are the durable authority.
