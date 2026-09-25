---
title: "WHD Fold Designer Bridge Ownership Phase 6 — Residual Reduction + Protected Boundary Reconsideration 規格"
version: "v1.4"
status: "USER_ACCEPTED_FOR_EXECUTION"
date: "2026-09-23"
accepted_via: "user dispatch instruction after RED/breakdown approval gates"
repository: "looaeedr/whd"
target_branch: "cleanup/2d-3d-sync"
publication_head: "adbfa95092a35183b3b64d0d38ea8cb68be64b65"
bridge_blob: "17c4254c6aac960980c8ecfadfcd7e0ca03fc0d6"
bridge_loc: 7806
bridge_top_level_symbols: 347
bridge_facade_bindings: 69
supersedes_spec: "WHD Fold Designer Bridge Ownership Phase 6 — Residual Reduction + Protected Boundary Reconsideration 規格 v1.3"
---

# WHD Fold Designer Bridge Ownership Phase 6
## Residual Reduction + Protected Boundary Reconsideration 規格 v1.4

> 狀態：**DRAFT_FOR_USER_ACCEPTANCE**
>
> 本文件是一份 **boundary-changing specification**。
>
> 在使用者明確接受本規格以前，只允許 read-only census、規格修訂、test/owner characterization 與 evidence 整理；不得依本文件建立 implementation branch、修改 production、改寫舊 ownership test oracle 或宣告舊 KEEP 決策已失效。
>
> 一旦使用者接受本 v1.4，本文件即成為本 Phase 的 requirement authority，允許依本文件定義的 Stage B decision gate，重新審議並在證據成立時 supersede 先前已接受的：
>
> - Workspace Shell `NO_EXTRACTION`
> - Part Editor `C_KEEP_BRIDGE_COMPATIBILITY`
> - Linked Endcap `KEEP_COMPATIBILITY`
> - Phase 4 exact-six Settings `KEEP_BRIDGE_COMPATIBILITY`
>
> 但 **LOC 只可觸發「必須繼續審議」；LOC 本身不能直接決定某段程式應搬去哪裡。**
>
> 本文件 supersede v1.0。v1.0 的「若 protected boundary 仍大就另寫下一份 spec」做法過度保守，可能造成實際只減少數百行仍能結案；本 v1.4 明確修正此缺口。

---


# 0. 執行順序速查表（Gate A → H）

> 這一節只提供執行導航，不取代後文完整 requirement。任何 Gate 判定衝突時，以對應完整章節為準。

| Gate | 要做什麼 | 必備輸出 | 不可繼續的條件 |
|---|---|---|---|
| **A — Pre-implementation** | 使用者接受 v1.4；fresh-read X；freeze execution base；建立真正 GitHub owning Issues | `T0_HEAD`、bridge blob/LOC、issue URLs | spec 未接受、baseline 未 freeze、Issue 未反讀 |
| **B — Census** | 全 347+ symbols、facade、dynamic/string refs、prior decisions 全量分類 | machine-readable census；`UNKNOWN=0`；`FACADE_ACCOUNTED=T0_FACADE_COUNT` | 任何 UNKNOWN、未盤點 dynamic refs |
| **C — Stage A** | 刪 dead/duplicate glue；移除 existing-owner violation；alias/facade ratchet | Stage A LOC、owner violation=0、focused GREEN | owner violation 未清零、facade 增長 |
| **D — Mandatory Stage B** | 執行 MRG；若減幅不足，依 Deletion-Test 逐一重審 B1～B6 | 每個 boundary 的 decision artifact + supersession map | MRG RED 卻停工；decision 無 deletion-test evidence |
| **E — Structural** | 檢查 reverse import、composition root、full-app leak、duplicate domain path | architecture guards GREEN | reverse import>0、second root>0、full-app owner |
| **F — Quantitative Budget** | 計算 final meaningful reduction | `TOTAL_BRIDGE_REDUCTION >= MIN_REDUCTION` 且 `FINAL_BRIDGE_LOC <= EFFECTIVE_FINAL_CEILING` | `FUNCTIONAL_GREEN_BUDGET_RED` |
| **G — Combined Acceptance** | fixed T0 baseline A/B；Headless/Xvfb；affected GUI；必要時板件/DXF | exact tested head、candidate-only fail/error=0 | 只 focused GREEN、run 未 terminal、DXF 未 reopen |
| **H — Closing** | durable writeback、drift audit、non-force integration、production readback | closing head、ancestry/readback、final smoke | tested→closing drift、未真正整合、continuity 未 finalizable |

## 0.1 單一執行者的最短合法路徑

```text
A freeze
→ B census
→ C Stage A cleanup
→ evaluate MRG
→ (MRG RED ? D/B1~B6 : continue)
→ E structural
→ F budget
→ G combined
→ H durable close
```

## 0.2 Fail-closed 停止點

只有以下情況可以在整鏈中暫停：

- 真正外部 blocker；
- 使用者明確要求停止；
- remote QA 正在 active monitoring（但不得把 in-progress 當 terminal）；
- `ARCHITECTURE_BUDGET_BLOCKED` 已證明所有允許 boundary 都經 Deletion-Test，且需要使用者修改 spec/budget。

「child ticket 完成」、「focused GREEN」、「Stage A ownership 已正確」都不是 whole-chain 停止點。

---

# 1. Problem Statement

`fold_designer_bridge.py` 已經經過多輪 ownership refactor：

- #441 ownership-refactor chain；
- Phase 4 / #486；
- Phase 5 / #506；
- Assembly presentation / Settings / FinalScene / Registry / workspace 等多輪深模組化。

目前 production target `cleanup/2d-3d-sync` 的 grounded publication state：

- HEAD：`adbfa95092a35183b3b64d0d38ea8cb68be64b65`
- `fold_designer_bridge.py` blob：`17c4254c6aac960980c8ecfadfcd7e0ca03fc0d6`
- `wc -l` 等價值：`7,806`
- top-level `def/class` census：約 `347`
- facade binding count：`69`

過去重構已建立大量正確 owner，但 bridge 仍然很大。

v1.0 的策略是：

> 只刪 owner violation / dead glue，對過去已接受的 KEEP / NO_EXTRACTION 一律不重新審議。

這個策略架構上安全，但有一個產品化／維護上的實際缺口：

> **它完全可能讓 bridge 從 7,806 只降到 7,300、7,000，甚至只少數百行，卻仍被宣告完成。**

目前已知、被舊 decision 明確保護的函式群，僅粗略 span 就約有 **1,194 行**；其中包含：

- Part Editor activation / save / installer；
- Workspace Shell builders；
- Settings exact-six projection/dataflow compatibility；
- Linked Endcap；
- `_fix11_init`。

此外：

- `_phase6_sync_authoritative_derived_parts` 約 246 行；
- `Phase6FoldDesignerApp` class 約 167 行；
- `_phase6_settings_application_project_ui_values` 約 141 行；
- 仍有多個 50～100+ 行 application/compatibility function。

這些行數本身不是「錯誤」，但它證明：

> 如果「過去 KEEP」永遠不能重新打開，Bridge 的縮減幅度存在明顯上限。

因此 Phase 6 v1.2 的真正問題是雙層的：

1. 先清掉**不用改 boundary**就能證明的 dead glue / duplicate ownership；
2. 如果減幅仍不足，**不得結案**，而是必須進入本規格已預先授權的 Protected Boundary Reconsideration。

本 Phase 不是「為了行數亂搬」。

本 Phase 也不是「只要 ownership 正確，7,000 多行也算完成」。

本 Phase 的目標是：

> 在不破壞 mechanical / manufacturing / UI / persistence authority 的前提下，把 Bridge 從歷史 compatibility monolith 收斂成真正可維護的 application composition / compatibility surface，並用 quantitative budget 防止再次只少幾百行就收工。

---

# 2. Confirmed Product Rules

## CPR-1 — Bridge 的長期角色

`fold_designer_bridge.py` 長期只應承擔：

- application bootstrap；
- composition root handoff；
- lifecycle；
- bounded compatibility adapters；
- narrow host callback / port binding；
- 少量 legacy public entrypoints；
- 無法合理下沉且經 deletion-test 證明仍 cohesive 的 glue。

Bridge 不應長期持有：

- domain calculation；
- mechanical geometry；
- manufacturing formula；
- project persistence policy；
- workspace physical identity mutation；
- deep Settings sequencing；
- FinalScene geometry implementation；
- Registry semantic implementation；
- large UI subsystem implementation；
- 跨多 owner 的大段 transaction algorithm。

## CPR-2 — 既有 CURRENT owner 仍是第一優先

本 v1.4 **不是把 ownership 全部推倒重來**。

以下 CURRENT owners 繼續有效：

- Settings presentation → `phase6_settings_panel.py`
- Settings application sequencing → `Phase6FoldDesignerSettingsCoordinator`
- Settings→Profile pure planning → `phase6_settings_profile_projection.py`
- live-sync pure planning → `phase6_sync_envelope.py`
- workspace/navigation mutation → `Phase6WorkspaceNavigationController` / `Phase6DesignerWorkspace`
- derived-part pure planning → `phase6_derived_part_projection.py`
- FinalScene composition → `Phase6FoldDesignerComposition`
- FinalScene view / renderer → existing FinalScene view modules
- diagnostics → `phase6_diagnostics.py`
- Registry presentation → `phase6_registry_diagnostics_panel.py`
- Registry controller/semantic → `phase6_registry_diagnostics_controller.py`
- EndCap / Fold semantic owners → existing domain modules
- manufacturing / Certified Registry → canonical ae_engine owners

Stage B 的目的優先是 **深化既有 owner**，不是任意新增新檔。

## CPR-3 — LOC 不可作 domain authority

`bridge LOC`、function span、AST symbol count 是：

- maintainability budget；
- phase progress signal；
- anti-stall gate；
- reconsideration trigger。

它不是：

- mechanical truth；
- ownership mapping；
-「這個函式一定應搬」的直接證據。

因此：

> LOC 可強制「不能停」，但不能強制「搬到某個指定 owner」。

## CPR-4 — Meaningful Reduction Hard Gate

本 Phase 不允許「只少幾百行」就 COMPLETE。

### Normative budget symbols

本章**不自行定義數字門檻**。本 Phase 唯一的 quantitative budget authority 是 **Appendix A**，其在 T0 fresh execution baseline 上計算：

```text
MIN_REDUCTION
EFFECTIVE_FINAL_CEILING
```

主文、MRG、Gate F、DoD 只能引用這兩個符號；不得另外抄一份固定數字形成第二 authority。

Appendix A 中的係數與 publication example 都屬 **maintainability governance policy**，不是 mechanical/domain truth，也不是理論最小 Bridge 的數學證明。

### Stage A completion check

只完成 uncontroversial dead-glue / owner-violation cleanup 後，計算：

```text
STAGE_A_REDUCTION = T0_BRIDGE_LOC - STAGE_A_BRIDGE_LOC
```

任一成立：

```text
STAGE_A_REDUCTION < MIN_REDUCTION
OR
STAGE_A_BRIDGE_LOC > EFFECTIVE_FINAL_CEILING
```

則：

```text
STAGE_B_REQUIRED = TRUE
```

**不得關 Master、不得把 Phase 標 COMPLETE、不得以「ownership 已正確」停止。**

### Whole Phase final budget

本 Phase 最終要同時滿足：

```text
TOTAL_BRIDGE_REDUCTION >= MIN_REDUCTION
FINAL_BRIDGE_LOC <= EFFECTIVE_FINAL_CEILING
```

publication baseline 下的實際數值範例與 T0 漂移重算方式，**只讀 Appendix A**；主文不複製數值。

### 重要

此 budget 不允許靠以下方式作弊：

- blank line / comment mass deletion；
- 把同一 implementation 原封不動移到 `*_helpers.py`；
- 建 shallow wrapper；
- 把 full `self/app` 傳去新 module；
- 把 test / evidence / logging 刪掉只為達行數；
- 合併多行語句壓 LOC；
- 把 bridge code copy 到另一個 monolith。

真正要量的是：

- ownership removed；
- interface knowledge concentrated；
- bridge implementation responsibility reduced。

## CPR-5 — Stage B 是本 v1.4 預先授權的 boundary reconsideration

使用者接受 v1.4 後，不需要再為下列每一塊另寫一份新總規格才可開始 characterization：

- Workspace Shell；
- Part Editor；
- Linked Endcap；
- Settings exact-six；
- Derived Parts input/planning assembly；
- Facade compatibility surface。

Stage B 可在本規格限定的 decision set 中選擇新 boundary。

但每一個 boundary 要改之前，仍必須：

1. fresh census；
2. requirement RED；
3. deletion-test / owner-cohesion evidence；
4. machine-readable decision；
5. same-change old owner downgrade / guard update；
6. Combined Acceptance。

## CPR-6 — 舊 KEEP 決策是 prior accepted baseline，不是永久不可變 product truth

#447 / #448 / #481 / #482 的決策在當時 codebase 是有效、已接受的。

v1.1 不把它們說成「當時做錯」。

本規格只確認：

> 當 ownership graph、typed ports、coordinator、planner、workspace owners 已經比當時更成熟時，舊 deletion-test 結論可以重新驗證。

因此 Stage B 的 decision evidence必須寫：

```text
PRIOR_DECISION
CURRENT_CHANGED_PRECONDITIONS
DELETION_TEST_RESULT
NEW_DECISION
SUPERSEDED_TESTS
NEW_GUARDS
```

## CPR-7 — 舊 regression oracle 必須能被新 approved requirement supersede

使用者接受本 v1.4 後，像：

- `test_issue447_workspace_shell_owner.py`
- `test_issue448_part_editor_owner_decision.py`
- `test_issue481_derived_apply_linked_endcap_owner.py`
- `test_issue483_t5_bridge_dead_glue_cleanup.py`
- `test_issue502_editor_settings_commit_seam.py`

裡面若有直接鎖死舊 decision 的 assertion：

```text
DECISION=NO_EXTRACTION
DECISION=C_KEEP_BRIDGE_COMPATIBILITY
decision == KEEP_COMPATIBILITY
PROTECTED_KEEP contains exact function
prospective module must not exist
```

這些只代表 **current pre-v1.1 test oracle**。

若 v1.4 已接受，且 Stage B 對該 boundary 的 requirement RED / new decision 已通過：

- 舊 test 必須標 `SUPERSEDED`、改寫或替換；
- 不得以「舊 test 原本 GREEN」阻止新 requirement；
- 但行為 invariant 仍要保留，例如 single shared-content surface、activation ordering、single owner、no reverse import。

## CPR-8 — Workspace Shell 的產品行為 invariant 不等於檔案位置 invariant

無論 Workspace Shell 最後 KEEP 或 extraction：

必須保持：

- single shared content surface；
- 一般板件 / 組合體 / 截角資料互斥使用同一 physical slot；
- no second Assembly region；
- no second Corner Data region；
- no duplicate event binding；
- no callback multiplication；
- F11 / Save / Open keyboard semantics parity；
- fullscreen single state owner；
- operator UI layout不漂移。

舊 `NO_EXTRACTION` 可被重新審議。

上述 UI invariants 不可被重新審議掉。

## CPR-9 — Part Editor 的 transaction invariant 不等於 bridge ownership invariant

無論 Part Editor 最後 KEEP 或移出：

必須保持：

```text
plan activation
→ save outgoing editor state
→ begin identity switch
→ load/stage target state
→ render settings/shared content
→ finish activation
→ exactly one update intent
```

並維持：

- workspace backing state不被第二 owner直接寫；
- Settings commit走 canonical coordinator；
- update scheduler走 command router；
- project persistence走 project owner；
- physical child identity走 workspace/manufacturing owner；
- no second render authority。

舊 `C_KEEP_BRIDGE_COMPATIBILITY` 可被 supersede。

上述 transaction semantics不可被 supersede。

## CPR-10 — Linked Endcap derivation authority不變

`build_linked_endcap_xy_profiles` 等 domain derivation仍由 `phase6_fold_profiles` 擁有。

Stage B 可重新決定的是：

- application orchestration放哪裡；
- stash/apply如何接 workspace；
- 是否可納入 existing derived sync plan；
- bridge是否仍需 78 行 compatibility body。

不得把 Fold formula搬進 application coordinator或 UI。

## CPR-11 — Settings exact-six 可重新分配 presentation/projection orchestration，但不可建立第二 Settings domain

Stage B 可考慮：

- deepen `Phase6SettingsPanel`；
- deepen `Phase6FoldDesignerSettingsCoordinator`；
- deepen `phase6_settings_profile_projection.py`；
- 保留極薄 bridge compatibility delegate。

禁止：

- 第二個 Settings state owner；
- panel直接擁有 canonical mutation；
- coordinator擁有 mechanical formula；
- duplicate profile calculation；
- bridge重新取得 deep Settings sequencing。

## CPR-12 — Derived Parts 246-line bridge body 必須重新 characterization

目前 `_phase6_sync_authoritative_derived_parts` 已：

- 先建立 immutable request/plan；
- 將 apply mutation delegate 給 `Phase6WorkspaceNavigationController.apply_derived_sync_plan()`。

這是正確進步。

但 v1.1 要進一步問：

> Bridge 是否仍知道太多「如何從 snapshot 組成 derived projection request」的 application/domain knowledge？

Stage B 必須 characterization：

- Door projections；
- Base Plate projections；
- BoxBody physical piece profiles；
- Divider projections；
- Inner Door frame/panel projections；
- namespace replacement；
- active/selected repair。

允許決策：

```text
KEEP_REQUEST_ASSEMBLY_IN_BRIDGE
DEEPEN_EXISTING_DERIVED_PROJECTION_OWNER
DEEPEN_EXISTING_APPLICATION_COMPOSITION
ADD_TYPED_DERIVED_APPLICATION_COORDINATOR
```

最後一項只有在 deletion-test 證明它是一個深 application module時才允許，不可只是 246 行搬家。

## CPR-13 — Facade 69 是 compatibility debt inventory

目前 facade binding count = `69`。

它不是 domain truth。

Stage A / Stage B 都必須判定每個 binding：

```text
PUBLIC_REQUIRED
LEGACY_REQUIRED
INTERNAL_ONLY
NO_CALLER
SUPERSEDED
PROPERTY_COMPAT
```

要求：

- facade不得增加；
- `NO_CALLER / SUPERSEDED` 必須刪；
- internal-only若可改直接 owner call，應退出 facade；
- property compatibility若已有 single backing owner可保留極薄 descriptor。

v1.1 不硬寫 arbitrary `<=50`，避免為數字破壞 compatibility；但 final report必須逐個解釋 retained facade。

## CPR-14 — Manufacturing / geometry / DXF authority完全不因本 Phase改寫

本 Phase 不得改寫：

- CornerType；
- AssemblyJoint；
- Certified Relief Registry；
- Fold Profile mechanical meaning；
- W/H/D/T/FW dimension semantics；
- CUTTING formula；
- BEND formula；
- MARKING mechanical placement；
- physical collision；
- 2D/3D geometry authority；
- DXF manufacturing source。

如果某個 Bridge function內混有上述 responsibility：

- 應移回 current owner；
- 不是趁本 Phase重新發明算法。

Registry HIT：

- canonical Registry answer仍是 runtime manufacturing answer；
- 3D shadow只驗證；
- validation expected不得回灌 production。

## CPR-15 — FinalScene / actual DXF sink仍必須同源

任何 Stage B 改動若碰到：

- part activation；
- derived part；
- geometry request；
- FinalScene；
- physical inventory；
- export；

最終驗收必須保證：

```text
authoritative state
→ canonical manufacturing
→ resolved FinalScene/material
→ 2D
→ single-part 3D
→ Assembly 3D
→ actual DXF export
```

不出現第二 geometry path。

---

# 3. Current State / RED Evidence

## 3.1 Publication snapshot

本規格 grounding 時：

```text
TARGET_X=cleanup/2d-3d-sync
HEAD=adbfa95092a35183b3b64d0d38ea8cb68be64b65
BRIDGE_BLOB=17c4254c6aac960980c8ecfadfcd7e0ca03fc0d6
BRIDGE_LOC=7806
TOP_LEVEL_SYMBOLS≈347
FACADE_BINDINGS=69
```

施工 T0 必須 fresh-freeze，不能假設 publication snapshot仍是 execution base。

## 3.2 Diagnostic large-function inventory

目前具代表性的 spans：

```text
_phase6_sync_authoritative_derived_parts          ~246
_fix11_activate_part                              ~221
Phase6FoldDesignerApp                             ~167
_phase6_settings_application_project_ui_values    ~141
_fix11_save_current_part                          ~130
_phase6_build_persistent_top_area                  ~129
_phase6_install_part_editor_compatibility          ~119
_phase6_settings_box_structure_projection          ~110
_phase6_settings_corner_projection                  ~91
_phase6_registry_validate_candidate_3d              ~86
_phase6_commit_box_body_physical_piece_profile      ~84
_phase6_queue_update                                ~81
_phase6_rebuild_linked_endcaps                      ~78
_fix11_export                                       ~71
```

這只是 PROBE / census。

它不能直接決定 owner。

## 3.3 Prior protected footprint

目前可明確對應舊 protected decisions 的函式 span粗略合計約：

```text
~1194 lines
```

包含：

- Settings exact-six；
- Workspace Shell builder group；
- `_fix11_init`；
- `_fix11_save_current_part`；
- `_fix11_activate_part`；
- Part Editor installer；
- Linked Endcap。

該數字只能證明：

> 舊 protected boundary 規模已足以讓「只做 dead glue cleanup」很可能無法達 meaningful reduction。

它不是「1194 行全部都必須搬」的產品要求。

## 3.4 Current owner maturity compared with older decisions

自舊 KEEP decision後，專案已建立／深化：

- `Phase6FoldDesignerSettingsCoordinator`
- typed Settings application ports
- Settings Profile pure projection
- derived-part immutable plan
- `Phase6WorkspaceNavigationController.apply_derived_sync_plan`
- FinalScene composition owner
- Assembly panel/presentation owners
- Registry diagnostics panel/controller
- command router update ownership
- diagnostics module
- FinalScene view ownership

因此重新跑 deletion-test有合理工程基礎。

## 3.5 Current test oracle conflict

現行 tests仍有：

```text
assert "DECISION=NO_EXTRACTION"
assert "DECISION=C_KEEP_BRIDGE_COMPATIBILITY"
assert linked_endcap decision == "KEEP_COMPATIBILITY"
assert prospective shell/session does not exist
assert PROTECTED_KEEP functions continue to exist
```

在 v1.1 尚未接受前，這些是有效 CURRENT regression。

在 v1.4 接受後，這些 assertion若對應 boundary進入 Stage B，必須先轉成新的 requirement RED / invariant test。

不得：

- 直接刪舊 test來讓 extraction變綠；
- 也不得拿舊 test永久否決已接受的新 spec。

---

# 4. Solution

本 Phase 採 **Two-Stage Mandatory Reduction Architecture**。

---

## Stage A — Residual Ownership Ratchet

目標：

先做所有不需要推翻舊 boundary decision 的收斂。

### A1. Full symbol ownership census

全部 top-level symbols分類：

```text
BRIDGE_ROOT_BOOTSTRAP
PROTECTED_COMPATIBILITY_PRIOR
NARROW_DELEGATE_OR_ALIAS
OWNER_VIOLATION
DEAD_OR_DUPLICATE_GLUE
BOUNDARY_RECONSIDERATION_CANDIDATE
UNKNOWN
```

T0 完成：

```text
UNKNOWN=0
```

### A2. Dead glue deletion

刪：

- zero-caller；
- duplicate delegates；
- stale alias；
- fully superseded implementation；
- obsolete facade entry；
- duplicate state mirror；
- duplicate serialization adapter。

### A3. Existing-owner violation remediation

已有 owner的 responsibility必須回 owner：

- bridge direct workspace mutation；
- duplicate Settings sequencing；
- duplicate FinalScene geometry；
- duplicate Registry presentation；
- duplicate diagnostics serialization；
- duplicate domain semantic helper。

### A4. Alias / facade ratchet

能 direct alias就 direct alias。

能 remove facade binding就 remove。

不能刪的每個 retained compatibility entry都要有 caller evidence。

### Stage A checkpoint

記錄：

```text
T0_BRIDGE_LOC
STAGE_A_BRIDGE_LOC
STAGE_A_REDUCTION
STAGE_A_FACADE_COUNT
OWNER_VIOLATION_COUNT
DEAD_GLUE_REMOVED_COUNT
```

然後跑 Mandatory Reduction Gate。

---

## Mandatory Reduction Gate — MRG

```text
IF STAGE_A_REDUCTION >= MIN_REDUCTION
AND STAGE_A_BRIDGE_LOC <= EFFECTIVE_FINAL_CEILING
THEN
    Stage B may still run if evidence justifies,
    but not mandatory for budget.
ELSE
    STAGE_B_REQUIRED = TRUE
```

對 publication baseline 的具體門檻值請讀 Appendix A；MRG 不得自行抄寫或重算另一套字面值。

這是本 v1.4 專門用來防止：

> 拆一堆工單，最後又只少幾百行。

---


# Definition — Deletion-Test

`Deletion-Test` 是本規格重新審議舊 `KEEP / NO_EXTRACTION` 的正式證據機制。它不是「把檔案刪掉看測試會不會過」，也不是以 LOC 猜 ownership；它回答的是：

> **若拿掉 proposed owner / boundary，真正的責任知識會回流到哪裡？反過來，若拿掉舊 bridge implementation 並改走 proposed owner，是否能在不建立第二 authority 的情況下維持所有 invariant？**

每一個 B1～B6 boundary change 都必須完成以下六步。

## DT-0 — Freeze Characterization Baseline

固定：

- exact T0 HEAD；
- exact candidate boundary；
- direct callers；
- dynamic/string/facade callers；
- imports；
- state read/write inventory；
- current focused tests；
- exact operator path（若有 UI）；
- prior accepted decision。

輸出：

```text
baseline_head
boundary_id
prior_decision
candidate_symbols
direct_callers
dynamic_callers
state_reads
state_writes
current_owner_dependencies
```

## DT-1 — Responsibility Decomposition

把 candidate cluster逐項標成責任，不得只寫「UI code」「glue」。

至少使用：

```text
BOOTSTRAP
TRANSACTION_ORDERING
STATE_READ
STATE_MUTATION
PRESENTATION_BUILD
PRESENTATION_EFFECT
NAVIGATION
PERSISTENCE
DOMAIN_DERIVATION
MANUFACTURING_QUERY
COMPATIBILITY
LEGACY_PUBLIC_API
```

若同一 cluster混有不同 CURRENT owners，先拆責任再判 owner。

## DT-2 — Build Two Disposable Variants

在隔離 branch/worktree 建兩個 characterization variant；它們不是直接 merge candidate。

### Variant K — KEEP / Inline Variant

假設「不建立/不深化 proposed owner」。

若 proposed owner已存在，暫時把其 responsibility inline 回直接 caller；若尚未存在，保留 current boundary，但把所有 hidden forwarding展開到 caller view。

目的：

> 看 proposed owner消失後，caller 是否重新取得跨 owner sequencing、state mutation、domain branching 或重複 knowledge。

### Variant E — EXTRACT / Delete-Old-Boundary Variant

移除 old bridge implementation body，改成 proposed existing owner / bounded application owner，Bridge 只留：

- typed request/ports；
- narrow callback；
- direct alias；
- bootstrap handoff。

目的：

> 證明 old boundary 可以被刪除，而不是新舊兩條 path 同時存在。

兩個 variant 都不得修改產品 requirement來讓測試變綠。

## DT-3 — Structural Signals

Deletion-Test 不用單一 LOC 指標決定「cohesive」。必須記錄以下訊號。

### 支持 EXTRACT / DEEPEN 的 structural signal

任一成立都可作正向證據，但仍需 DT-4 behavior GREEN：

- Variant K 讓**兩個以上 caller**重複相同 transaction / branch knowledge；
- Variant K 讓單一 caller重新直接知道**兩個以上 CURRENT owner**的 ordering / failure semantics；
- Variant K 讓 caller重新同時擁有 `STATE_MUTATION + PRESENTATION/NAVIGATION EFFECT`；
- Variant K 迫使 caller取得原本可由 bounded typed contract隱藏的 domain/application branch；
- old bridge body存在 duplicate state owner / duplicate calculation / second implementation path；
- Variant E 能刪除 old body 且不產生 reverse import / full-app dependency。

### 支持 KEEP 的 structural signal

- proposed owner刪除後只剩一個單一 caller，inline 後仍是短且 cohesive 的 local composition；
- proposed module只做 1:1 forward、沒有封裝 transaction/order/state knowledge；
- proposed module必須吃 full `app/self` 才能工作；
- extraction只把相同程式搬檔，caller/owner knowledge沒有下降；
- extraction會製造 second composition root、reverse import 或 competing domain owner。

## DT-4 — Behavior / Invariant Test

Variant E 至少跑：

1. architecture/source focused tests；
2. 該 boundary unit/contract tests；
3. 既有 operator invariant tests；
4. 若是 Tk/UI：exact Xvfb user path；
5. 若觸碰 physical part / FinalScene / export：依 Skill 進板件/DXF final acceptance。

必驗：

```text
single state owner
single production path
no reverse import
no second composition root
no full-app owner interface
accepted transaction ordering
operator-visible parity
```

舊 test若只鎖「檔案必須不存在 / 函式必須留在 bridge」且已被 v1.2 requirement supersede，先改成新的 requirement RED，再驗真正 invariant。

## DT-5 — Decision Rule

輸出只能是：

```text
KEEP_CURRENT_BOUNDARY
DEEPEN_EXISTING_OWNER
EXTRACT_TO_DEEP_OWNER
ADD_BOUNDED_APPLICATION_COORDINATOR
SPEC_BLOCKED
```

`EXTRACT_TO_DEEP_OWNER` / `ADD_BOUNDED_APPLICATION_COORDINATOR` 只有在：

- DT-3 有至少一個明確 structural reason；
- DT-4 全部 GREEN；
- old implementation被實際刪除；
- duplicate production path = 0；

才成立。

若 proposed module只是 middle man：

```text
KEEP_CURRENT_BOUNDARY
```

若 evidence顯示需要改本規格未授權的 product/domain boundary：

```text
SPEC_BLOCKED
```

## DT-6 — Machine-Readable Evidence

每個 boundary 必須寫一份 decision artifact：

```json
{
  "boundary_id": "B1_PART_EDITOR",
  "baseline_head": "<sha>",
  "prior_decision": "C_KEEP_BRIDGE_COMPATIBILITY",
  "variant_keep": {
    "callers": [],
    "owner_dependencies": [],
    "state_writes": [],
    "observed_structural_regressions": []
  },
  "variant_extract": {
    "candidate_owner": "...",
    "bridge_symbols_removed": [],
    "reverse_import_count": 0,
    "duplicate_path_count": 0,
    "full_app_dependency": false
  },
  "tests": {
    "focused": "...",
    "xvfb": "...",
    "combined_required": true
  },
  "decision": "DEEPEN_EXISTING_OWNER",
  "supersedes": ["#448"],
  "rationale": "..."
}
```

缺任何 Variant K / Variant E evidence，不能寫「Deletion-Test 已證明」。

---

# 5. Stage B — Protected Boundary Reconsideration

Stage B 只在 v1.4 已被使用者接受後合法。

Stage B 對下列 boundary逐項重新跑 deletion-test。

---

## B1. Part Editor Reconsideration

### Prior decision

```text
C_KEEP_BRIDGE_COMPATIBILITY
```

### Current large surface

至少：

```text
_fix11_activate_part
_fix11_save_current_part
_phase6_install_part_editor_compatibility
_fix11_export  (相關但需分開 characterization)
```

### Required characterization

逐步拆解 responsibility：

- activation plan
- outgoing editor save
- workspace identity transition
- profile/features stash
- Settings projection
- shared-content switch
- Bending UI refresh
- hole editor/load
- structure controls
- content-switch refresh
- update intent
- render timing
- dirty/switching lifecycle
- project snapshot handoff

### Allowed decision set

```text
B1_KEEP_COMPATIBILITY
B1_DEEPEN_EXISTING_OWNERS
B1_ADD_DEEP_APPLICATION_COORDINATOR
```

### Preferred order

1. 先 deepen existing workspace/navigation/settings/router owners；
2. 若 remaining ordering仍跨多 owner且有明確 cohesive transaction，才允許 application coordinator。

### New coordinator hard rule

若建立：

```text
gui_modules/application/fold_designer_part_editor_coordinator.py
```

或同義 module，它必須：

- 擁有完整 activation/save ordering knowledge；
- 使用 typed ports；
- 不 import Tk；
- 不 import manufacturing；
- 不 import bridge；
- 不持有 full app；
- deletion-test：移除 coordinator後，複雜度會回到 caller，證明它不是 middle man。

### Desired outcome

Bridge中的 Part Editor應收斂成：

```text
build bounded request/ports
→ coordinator.execute(...)
→ apply narrow presentation handoff
```

而不是 200+ 行 transaction body。

---

## B2. Workspace Shell Reconsideration

### Prior decision

```text
NO_EXTRACTION
```

### Protected product invariants

永遠保留：

- single shared-content slot；
- same left physical surface；
- mutually exclusive single/assembly/corner-data mode；
- no extra wrapper；
- no duplicate bindings；
- exact keyboard behavior；
- fullscreen single owner。

### Current candidate surface

- project toolbar
- transaction buttons
- global controls
- output controls
- visual controls
- persistent top area
- shortcut install
- fullscreen UI orchestration
- shared-content host wiring

### Allowed decision set

```text
B2_KEEP_NO_EXTRACTION
B2_DEEPEN_EXISTING_COMPOSITION
B2_EXTRACT_DEEP_SHELL_OWNER
```

### 若選 Extract

`phase6_workspace_shell.py` 不再被舊 #447 永久禁止，但必須是 deep module：

至少真正擁有：

- shell widget construction；
- shell-local layout；
- shell-local fullscreen state/effect；
- top control event wiring；
- shared-content mode mounting policy（不含 domain selection semantics）；
- keyboard presentation routing。

不得只是：

```python
def build_x(app):
    return old_bridge_function(app)
```

### Hard parity

`ACTIVE_MODE_SURFACE_COUNT = 1`

仍是不可破壞 invariant。

---

## B3. Settings Exact-Six Reconsideration

### Prior decision

```text
KEEP_BRIDGE_COMPATIBILITY
```

### Current exact-six

1. `_phase6_settings_box_structure_projection`
2. `_phase6_settings_endcap_fw_projection`
3. `_phase6_settings_bottom_wrap_projection`
4. `_phase6_settings_corner_projection`
5. `_phase6_settings_context_extension_projection`
6. `_phase6_sync_settings_panel_extension`

### New context

Phase 5 已有：

- application coordinator；
- typed ports；
- pure profile projection；
- panel owner；
- Settings transaction/service owners。

### Allowed decisions per function/group

```text
B3_KEEP_THIN_COMPAT
B3_DEEPEN_SETTINGS_PANEL
B3_DEEPEN_SETTINGS_COORDINATOR
B3_EXTRACT_PURE_PROJECTION_INTO_EXISTING_SETTINGS_PROJECTION
```

禁止新增第二 Settings domain。

### Hard rule

Stage B 不可把 UI projection與 canonical mutation混回同一 owner。

---

## B4. Linked Endcap Reconsideration

### Prior decision

```text
KEEP_COMPATIBILITY
```

### Domain authority fixed

仍由：

```text
phase6_fold_profiles.build_linked_endcap_xy_profiles
```

### Reconsideration只處理

- request assembly；
- workspace stash；
- linked Head/Tail refresh ordering；
- update/live effect。

### Allowed decisions

沿用既有 decision vocabulary並擴充 evidence：

```text
KEEP_COMPATIBILITY
DEEPEN_FOLD_PROFILES
JOIN_DERIVED_PART_PLAN
DEEPEN_APPLICATION_COORDINATOR
```

`DEEPEN_FOLD_PROFILES` 只允許 pure derivation responsibility。

Workspace mutation仍不得進 Fold Profile owner。

---

## B5. Derived Parts Request Assembly Reconsideration

### Current fact

Apply mutation已下沉 navigation owner。

### Remaining question

Bridge仍負責大量：

- family-derived rows；
- profiles；
- namespaces；
- add/remove；
- repair；
- request materialization。

### Required split

把 `_phase6_sync_authoritative_derived_parts` 逐 statement分類：

```text
DOMAIN_DERIVATION
APPLICATION_PROJECTION
WORKSPACE_READ
PLAN_BUILD
MUTATION
COMPATIBILITY
```

`MUTATION` 必須維持 0 in bridge。

若大量 `APPLICATION_PROJECTION` 可由 existing pure owner吸收，則深化。

### Allowed decision

```text
KEEP_REQUEST_ASSEMBLY
DEEPEN_DERIVED_PROJECTION_OWNER
DEEPEN_APPLICATION_COMPOSITION
ADD_TYPED_DERIVED_APPLICATION_COORDINATOR
```

### Anti-middle-man rule

新 coordinator 必須能讓 Bridge不再知道：

- 各 namespace replacement details；
- active repair assembly；
- physical derived category orchestration；

但不得吸收 manufacturing formula。

---

## B6. Facade Compatibility Reconsideration

Facade audit 視為一條**獨立 mini-chain**，不得把 69 項當成一張「順手掃過」的小票。

### B6.0 Inventory-first hard gate

在任何 facade removal 前，先建立完整 inventory。

對目前 69 entries逐項列：

```text
name
consumer
consumer_type
dynamic/string reference
legacy/public requirement
direct-owner alternative
delete-safe?
```

完成條件：

```text
FACADE_ACCOUNTED == T0_FACADE_COUNT
UNCLASSIFIED_FACADE == 0
```

### B6.1 Bounded audit batches

- 每批 **最多 12 項**；
- 目前 69 項至少形成 **6 個 audit batches**；
- dynamic/string callback、property descriptor、public compatibility API 不得與普通 direct-call alias 混成「看名字就刪」；
- 每批先完成 caller search + classification，再做 production mutation；
- 每批都有 focused source/contract test；
- batch GREEN 只表示該批完成，不代表 B6 terminal。

這個 batch 上限是**執行負載控制**，不是 architecture truth；若某批因 coupling 需要更小，可再拆。

### B6.2 Completion

B6 只有在：

```text
FACADE_ACCOUNTED == T0_FACADE_COUNT
NO_CALLER_UNREVIEWED == 0
DYNAMIC_REF_UNREVIEWED == 0
```

才可 terminal。

### Final required classifications

```text
PUBLIC_REQUIRED
LEGACY_REQUIRED
PROPERTY_COMPAT
CAN_DIRECT_OWNER
NO_CALLER
SUPERSEDED
```

### Actions

- `NO_CALLER` → delete
- `SUPERSEDED` → delete
- `CAN_DIRECT_OWNER` → caller migration + delete facade
- `PROPERTY_COMPAT` → thin property only
- `PUBLIC_REQUIRED/LEGACY_REQUIRED` → retain with evidence

不得新增 facade entry補洞。

---

# 6. Stage C — Final Compression / Bridge Surface Normalization

Stage B完成後，進最後 bridge normalization。

這不是 domain extraction。

允許：

- imports cleanup；
- direct alias consolidation；
- adjacent tiny compatibility helpers合併；
- stale comment / superseded compatibility section移除；
- facade map按 responsibility整理；
- dead constants / unused dataclass清除。

禁止：

- minify；
- one-line compression；
- code golf；
- semantics rewrite。

Stage C後計算 FINAL budget。

---

# 7. User Stories

## US-1 — 使用者

我要看到這次重構真的讓 `fold_designer_bridge.py` 明顯縮小，而不是拆十幾張票最後只少 200～500 行。

## US-2 — 維護者

我要能知道每一段剩在 Bridge 的責任是：

- 真正 bridge responsibility；
- 還是暫時 compatibility debt。

不能再只因「舊 issue 說 KEEP」就永遠不能碰。

## US-3 — 未來 Agent

我要有清楚 machine-readable decision record，知道哪個舊 KEEP 已被 v1.1 supersede、哪個仍保留。

## US-4 — 操作員

無論 code搬到哪裡：

- UI不能變兩層；
- Part 切換不能跳錯；
- Settings不能不同步；
- 3D不能 stale；
- DXF不能漏件；
- Save/Reload不能變。

## US-5 — Manufacturing

Bridge瘦身不能讓 renderer / view / test 變成第二 manufacturing owner。

---

# 8. Implementation Decisions

## ID-1 — v1.1 acceptance 即授權 Stage B decision space

不需要 Stage A跑完後再另寫「總規格」。

但每個 Stage B child issue仍需 machine-readable decision artifact。

## ID-2 — Stage B 不是 optional fallback

只要 MRG fail：

```text
STAGE_B_REQUIRED=TRUE
```

Master chain下一票必須是 B-series ticket。

Child terminal不得被誤認 whole-chain terminal。

## ID-3 — Stage B 必須 supersede old tests atomically

同一個 boundary change PR/issue內：

1. requirement RED；
2. new implementation；
3. old decision artifact標 superseded；
4. old test oracle更新；
5. new invariant guard加入。

禁止先刪 old test，隔票再補 guard。

## ID-4 — Existing owner first

任何新 module前，先做 existing owner deletion-test。

新 module只有當：

- cohesive responsibility；
- bounded interface；
- complexity真正被集中；
- owner不需 full app；
- no reverse import；

才成立。

## ID-5 — Full app / self leakage fail closed

若新 owner interface出現：

```text
app
self
bridge
designer
service_bag
callbacks: dict[str, Any]
```

必須 characterization。

若它實際允許 owner任意 access runtime surface，視為 extraction failure。

## ID-6 — Final facade不可增加

```text
FINAL_FACADE_COUNT <= T0_FACADE_COUNT
T0_FACADE_COUNT <= 69
```

且 Stage B必須給 facade classification report。

## ID-7 — Reverse import維持 0

```text
PHASE6_REVERSE_IMPORT_BRIDGE_COUNT=0
```

## ID-8 — Second composition root維持 0

允許新增 application coordinator。

不允許新增第二 `Phase6FoldDesignerComposition` 等級的 service bag/composition root。

## ID-9 — LOC delta報告必須區分真正 ownership reduction

每票：

```text
bridge_before
bridge_after
bridge_delta
moved_to_existing_owner
new_owner_loc
deleted_loc
alias_loc
test_loc
net_project_loc
ownership_removed[]
protected_invariants[]
```

避免只看 bridge少多少卻專案總體複製更多垃圾。

## ID-10 — Budget failure不得寫 COMPLETE

若 Combined全綠但：

```text
FINAL_BRIDGE_LOC > EFFECTIVE_FINAL_CEILING
OR
TOTAL_BRIDGE_REDUCTION < MIN_REDUCTION
```

狀態只能是：

```text
FUNCTIONAL_GREEN_BUDGET_RED
```

不能：

```text
ACCEPTED
COMPLETE
CLOSED
```

下一步必須：

- 繼續 Stage B/C；
- 或由使用者明確修改 budget/spec。

## ID-11 — 若合理 owner全部審完仍過不了 budget

不得做危險 extraction湊數。

輸出：

```text
ARCHITECTURE_BUDGET_BLOCKED
```

並列出：

- retained cluster；
- line count；
- why extraction would violate cohesion；
- next candidate boundary；
- required user/spec change。

但這仍不是本 Phase COMPLETE。

---

# 9. Proposed Work-Order Chain

> 只有使用者接受 v1.4 後才真正建立 GitHub owning Issues。

## Master — Phase 6 Residual Reduction + Boundary Reconsideration

### A0 — Fresh Baseline / Full Symbol Census

- freeze X
- LOC
- facade
- symbol classification
- caller graph
- dynamic/string refs
- state read/write
- prior decision mapping

### A1 — Dead / Duplicate Glue

### A2 — Existing-Owner Violation Removal

### A3 — Alias / Facade Ratchet

### A4 — Stage A Combined / MRG

輸出：

```text
STAGE_A_LOC
STAGE_A_REDUCTION
STAGE_B_REQUIRED
```

若 `FALSE`，仍可進 C0。

若 `TRUE`，立即接 B1，不得停。

---

## B1 — Part Editor Boundary Reconsideration

## B2 — Workspace Shell Boundary Reconsideration

## B3 — Settings Exact-Six Reconsideration

## B4 — Linked Endcap Reconsideration

## B5 — Derived Projection / Request Assembly Reconsideration

## B6 — Facade Compatibility Reduction

Stage B順序可依 T0 coupling調整，但 Master必須記錄依賴圖。

---

## C0 — Bridge Final Compression / Surface Normalization

## C1 — Anti-Regrowth Architecture Guards

## C2 — Combined Acceptance

## C3 — Durable Writeback / Cleanup / Integration / Readback

---

# 10. Requirement RED Strategy

每一個 boundary改動都必須先有「新 requirement RED」。

---

## R-B1 Part Editor RED

不是：

```text
assert _fix11_activate_part does not exist
```

而是：

- bridge不再自己知道完整 activation sequence details；
- accepted coordinator/owners可獨立用 bounded DTO測；
- activation ordering不變；
- no full-app dependency。

## R-B2 Workspace Shell RED

- shell presentation owner能建立 single-slot layout；
- bridge不再持有 large builder implementation；
- `ACTIVE_MODE_SURFACE_COUNT=1`；
- exact widget master/visibility parity。

## R-B3 Settings RED

- exact-six responsibility由正式 owner消費；
- bridge只 thin compatibility；
- panel不取得 canonical mutation；
- coordinator不取得 mechanical formula。

## R-B4 Linked Endcap RED

- derivation identity仍是 Fold Profiles owner；
- Bridge orchestration responsibility依新 decision縮減；
- workspace mutation仍走 owner。

## R-B5 Derived RED

- Bridge不直接 assemble deep multi-family derived plan knowledge，若新 decision要求下沉；
- planner/coordinator不擁有 manufacturing；
- deterministic immutable plan；
- workspace apply only once。

## R-B6 Facade RED

- caller migrated before binding removed；
- dynamic/string reference inventory清空；
- no new facade binding。

---

# 11. Testing Decisions

## TD-1 — Stage A/B 每票 focused GREEN 不等於 final

每票可有 focused tests。

只有 C2 Combined是 whole-chain acceptance。

## TD-2 — Fixed T0 baseline

Headless：

```text
T0 baseline vs candidate
```

Xvfb：

```text
T0 baseline vs candidate
```

candidate-only failure/error = 0。

## TD-3 — Old decision test handling

如果 v1.4 新 decision supersede舊 KEEP：

舊 test必須：

- 保留真正 behavior invariant；
- 移除 file-location / old decision lock；
- 在 commit history / checkpoint記錄 supersession。

不得整顆刪掉而沒有 replacement。

## TD-4 — Exact GUI flows

至少覆蓋：

- fresh-open；
- designer already open；
- family live-switch；
- Part switch；
- Assembly switch；
- Corner Data switch；
- Settings lock/unlock；
- shared-content切換；
- 3D preview；
- Save / Load；
- export。

受影響才跑，不要求每一票都重跑全部；C2統一完整驗。

## TD-5 — Physical part / DXF trigger

只要 Stage B實際碰到：

- physical identity；
- 2D / 3D；
- manufacturing resolve；
- FinalScene；
- export inventory；
- Save/Reload geometry；

必須啟動「驗證板件與DXF」final acceptance：

- actual DXF export；
- reopen；
- independent compare；
- multipart physical piece逐件；
- CUTTING/BEND/hole/MARKING；
- file set exact。

## TD-6 — Geometry change禁止由 architecture票偷做

若 architecture refactor造成 geometry expected不同：

先 A/B 判：

- baseline debt；
- candidate regression；
- stale oracle；
- actual requirement change。

不得在 bridge refactor票順手改 mechanical formula讓 test綠。

## TD-7 — Config invariant

會啟動 GUI / Settings regression的 Combined：

`config.ini` pre/post Git-object / hash invariant必須綠。

## TD-8 — Tested-head drift

C2 GREEN後到 C3 integration前：

production/test blob drift = 0。

若不為 0：

rerun affected acceptance。

---

# 12. Anti-Regrowth Guards

Phase完成後新增永久 guards。

## ARG-1 — Bridge size budget

不是 mechanical oracle。

但 CI architecture guard可以：

- report bridge LOC；
- 若新增 PR使 bridge超過 accepted final baseline + allowed small budget，fail review gate。

建議：

```text
BRIDGE_LOC <= ACCEPTED_PHASE6_FINAL_LOC + 25
```

25 行只供小型 compatibility fix buffer。

若超過要：

- 明確 allowlist；
- owner rationale；
- follow-up removal plan。

## ARG-2 — Large new top-level bridge body

新增或擴張 top-level function：

```text
> 40 lines net new
```

觸發 architecture review。

不是自動判錯，但必須 owner classification。

## ARG-3 — No extracted owner reverse import

## ARG-4 — No second composition root

## ARG-5 — Facade non-growth

## ARG-6 — Domain extracted functions不得重新 def回 bridge

## ARG-7 — New full-self owner interface禁止

---

# 13. Out of Scope

本 Phase即使 boundary-changing，仍不做：

- redesign operator workflow；
- 改板金機械規則；
- 改 Certified Relief公式；
- 改 FW / T / W/H/D semantic；
- 改 MARKING產品定義；
- 改 DXF layer semantic；
- 改 Cabinet Family product rules；
- 新增 unrelated feature；
- 重寫整個 Fold Designer；
- 以 web framework / different GUI toolkit替換 Tk；
- 全面移除 legacy compatibility API（除非 B6逐項證明）。

---

# 14. Open Items

## OPEN-1 — Stage B 最終會選哪些 boundary

本規格預先授權 decision set，但不預先假裝知道 evidence結果。

每個 B ticket都必須 machine-decision。

## OPEN-2 — 最終可降到多少

本規格硬要求（符號值一律由 Appendix A 對 T0 baseline 計算）：

```text
FINAL_BRIDGE_LOC <= EFFECTIVE_FINAL_CEILING
AND
TOTAL_BRIDGE_REDUCTION >= MIN_REDUCTION
```

目前希望的工程方向是進一步往 6k以下靠近，但 **6000 只是方向性目標，不是本 v1.4 hard gate；真正 hard gate 只讀 Appendix A 的正式符號值。**

避免為了 6000做壞 extraction。

如果 B1～B6自然收斂後能到 5500～6000，屬良好結果。

## OPEN-3 — `Phase6FoldDesignerApp` class residual

167 行 class本身需 T0分類：

- real host adapter；
- duplicate state；
- compatibility properties；
- initializer residue。

不得因 class大直接拆。

---

# 15. Acceptance Gates

## Gate A — Pre-implementation

- [ ] v1.4 user accepted
- [ ] T0 current X fresh-read
- [ ] execution base frozen
- [ ] all GitHub owning issues created/readback before production writes

## Gate B — Census

- [ ] all top-level symbols classified
- [ ] UNKNOWN=0
- [ ] prior decision map complete
- [ ] facade 69 entries classified
- [ ] dynamic/string references inventoried

## Gate C — Stage A

- [ ] dead glue removed
- [ ] current owner violations = 0
- [ ] facade did not grow
- [ ] Stage A focused acceptance GREEN
- [ ] MRG evaluated

## Gate D — Mandatory Stage B

若 MRG RED：

- [ ] B1 Part Editor decision complete
- [ ] B2 Workspace Shell decision complete
- [ ] B3 Settings decision complete
- [ ] B4 Linked Endcap decision complete
- [ ] B5 Derived decision complete
- [ ] B6 Facade decision complete
- [ ] old decision tests updated atomically where superseded

若某 B ticket保留 prior decision：

- [ ] deletion-test證明 KEEP仍是最深/cohesive choice
- [ ] retained LOC attribution recorded

## Gate E — Structural

- [ ] reverse import bridge = 0
- [ ] second composition root = 0
- [ ] facade <= T0
- [ ] no full-app new owner
- [ ] no duplicate domain owner
- [ ] no second manufacturing path

## Gate F — Quantitative Final Budget

- [ ] `TOTAL_BRIDGE_REDUCTION >= MIN_REDUCTION`
- [ ] `FINAL_BRIDGE_LOC <= EFFECTIVE_FINAL_CEILING`
- [ ] `MIN_REDUCTION` / `EFFECTIVE_FINAL_CEILING` 來自 Appendix A 對 T0 baseline 的單一計算 authority

缺任一：

```text
FUNCTIONAL_GREEN_BUDGET_RED
```

不得 COMPLETE。

## Gate G — Combined

- [ ] fixed baseline Headless A/B
- [ ] fixed baseline Xvfb A/B
- [ ] candidate-only fail/error = 0
- [ ] exact GUI affected flows GREEN
- [ ] project/persistence GREEN
- [ ] Settings GREEN
- [ ] navigation GREEN
- [ ] Assembly/shared-content GREEN
- [ ] FinalScene GREEN
- [ ] Registry/diagnostics GREEN
- [ ] geometry/DXF final acceptance GREEN if touched
- [ ] config invariant GREEN

## Gate H — Closing

- [ ] durable owner decisions writeback
- [ ] old CURRENT docs superseded/updated as needed
- [ ] Canonical Authority Map updated only if owner changes
- [ ] tested→closing drift clean
- [ ] non-force current X integration
- [ ] production ancestry/readback proves integration
- [ ] final smoke
- [ ] Master chain truly complete

---

# 16. Durable Writeback Rules

若 Stage B改變 prior decision，必須同步：

## Ownership AI Library

`個人AI檔案庫/第二層_專案與SOP/12_WHD_FoldDesignerBridgeOwnership規則.md`

把：

```text
NO_EXTRACTION
KEEP_COMPATIBILITY
C_KEEP_BRIDGE_COMPATIBILITY
```

對應舊段落標：

```text
SUPERSEDED_BY_PHASE6_V1_4
```

並寫新 CURRENT owner。

## Canonical Authority Map

只有真正 stable owner path改變才更新。

## Pitfall

若本次證實一個 durable lesson，例如：

> 「過去 KEEP decision 不可被當永久禁止 reconsideration」

則寫回全域踩坑庫，但不能把 ticket narrative塞成 CURRENT authority。

---

# 17. Evidence / Traceability

## Per-invocation Skill grounding

本 v1.4 fresh-read：

- `.agents/skills/engineering/寫成規格書/SKILL.md`
  - sha `6ded882d905b971a3590d6c3627d3eeb5368dd7f`
- `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`
  - sha `43b073f4346423361460f93d488544032b674ed5`

## Required references

- `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
  - sha `9426c1f5df565dbfaa9e4ada75ffb6424deb30c3`
- `基準檔/截角資料庫/README_母規則說明.md`
  - canonical required reference read
- `基準檔/截角資料庫/certified_relief_rules.json`
  - canonical required reference read
- `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`
  - sha `0139ab2bbecbc3085e7c5aa491568afac934cb72`

## CURRENT ownership authority

- `個人AI檔案庫/第二層_專案與SOP/12_WHD_FoldDesignerBridgeOwnership規則.md`
  - sha `d78bb7159643e5facc0c31def96b7da92e310be4`
- `個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md`
  - sha `93825936f3bdc4ce8824dd26f81b388efc1cb469`

## v1.2 / v1.3 review-driven clarifications

本輪使用者指出並由 v1.2 納入：

- Deletion-Test 必須有正式操作定義；
- budget 數字必須有可重算來源；
- 文件需要 Gate A→H 一頁速查；
- 69 項 facade audit 必須被視為獨立工量，不可低估。

這四項屬 process/architecture requirement，不改變 mechanical/manufacturing authority。

v1.3 再納入：

- DT-4 韓文字元修正；
- 主文所有 quantitative gates改讀 Appendix A symbols；
- `12.5% / 10%` 明確降級為 governance policy coefficients，而非理論推導真值。

v1.4 再納入：

- OPEN-2 最後兩個字面門檻改為 `MIN_REDUCTION` / `EFFECTIVE_FINAL_CEILING`，完成主文 quantitative authority 單一化。

## Current code / tests reread

- `fold_designer_bridge.py`
  - blob `17c4254c6aac960980c8ecfadfcd7e0ca03fc0d6`
- `tests/test_issue447_workspace_shell_owner.py`
  - sha `bcf795b4a7bb99270b3f75ddcee4abc14a6b3076`
- `tests/test_issue448_part_editor_owner_decision.py`
  - sha `3faa7e81b004a6cf2d487c0f1ff4dee97a735888`
- `tests/test_issue481_derived_apply_linked_endcap_owner.py`
  - sha `641e83c4448dea20e7c482a2434355d210582425`
- `tests/test_issue483_t5_bridge_dead_glue_cleanup.py`
  - sha `cdaed5846c5c3decfc3601fe89ad1319834c48f3`
- `tests/test_issue498_settings_application_coordinator.py`
  - sha `65fb865066d0487fc8b1823e537f509766cded58`
- `tests/test_issue502_editor_settings_commit_seam.py`
  - sha `25b49cff02f4abc3ae9f7558e622a882a2e1892e`

## Accepted lineage being reconsidered

- #447 Workspace Shell
- #448 Part Editor
- #481 Linked Endcap
- #482 Settings exact-six
- #483 dead-glue cleanup
- #497～#506 Phase 5 Settings/dataflow chain

v1.4 接受後，這些不是被「抹掉」，而是作為 prior accepted provenance保存；被新 decision supersede的部分必須明確標示 lineage。

---


# Appendix A — Quantitative Budget Rationale

本附錄是本 Phase **唯一 quantitative budget authority**。

主文只可引用：

```text
MIN_REDUCTION
EFFECTIVE_FINAL_CEILING
```

不得在 CPR、MRG、Gate 或 DoD 再建立第二套字面門檻。

## A.0 Governance coefficient status

以下係數是**可審查、可版本化的 maintainability governance policy**：

```text
MIN_REDUCTION_RATIO = 0.125
PROTECTED_REVIEW_RESERVE_RATIO = 0.10
ABSOLUTE_MIN_REDUCTION_FLOOR = 1000
ABSOLUTE_FINAL_CEILING_CAP = 6500
```

它們不是：

- domain truth；
- mechanical rule；
- 理論最小 Bridge 的數學解；
- 由 production behavior 唯一反推出的常數。

它們的價值在於：

> 把原本模糊的「要明顯縮小」轉成可重算、可審查、可在未來 spec 中明確挑戰的 policy parameters。

未來若要修改 `12.5%` 或 `10% reserve`，必須修改本 Appendix / successor spec 並說明 rationale；執行者不得在 T0 或 child ticket 臨時調係數。

## A.1 Publication baseline

```text
T0-like publication LOC = 7806
```

目前被舊 KEEP / NO_EXTRACTION decisions明確保護、且可由 exact function span盤出的 footprint：

```text
PRIOR_PROTECTED_LOC = 1194
```

其中包含：

- Settings exact-six；
- Workspace Shell builder group；
- Part Editor activate/save/installer；
- Linked Endcap；
- `_fix11_init`。

這 1194 行**不是「全部都該刪」**；它只量化「如果完全不重新審議 protected boundary，Bridge 有多大一塊天然不會動」。

## A.2 Minimum Meaningful Reduction

定義：

```text
MIN_REDUCTION =
    max(
        ABSOLUTE_MIN_REDUCTION_FLOOR,
        ceil_to_100(MIN_REDUCTION_RATIO × T0_BRIDGE_LOC)
    )
```

publication baseline：

```text
0.125 × 7806 = 975.75
ceil_to_100(...) = 1000
```

所以 publication example 為：

```text
MIN_REDUCTION = 1000
```

這只是依上述 policy coefficients 對 publication baseline 的計算結果，不是另一個固定 authority。

意義：

> 至少約八分之一（12.5%）的 bridge 必須真正退出 Bridge ownership/surface，才算「有意義的 Phase 級縮減」。

目前 1000 / 7806 = **12.81%**。

它是 maintainability floor，不是 domain ownership oracle。

## A.3 Final Ceiling

先對 prior-protected footprint 加一個 10% review reserve：

```text
PROTECTED_REVIEW_BUDGET
    = PRIOR_PROTECTED_LOC × (1 + PROTECTED_REVIEW_RESERVE_RATIO)
    = 1194 × 1.10
    = 1313.4
```

用 publication baseline反推：

```text
7806 - 1313.4 = 6492.6
```

取易追蹤的整百 architecture budget：

```text
FINAL_CEILING ≈ 6500
```

因此 publication example 的 `6500` 不是「理論最小 Bridge = 6500」，也不是獨立於公式存在的第二門檻。

它的意義是：

> Phase 6 必須至少有能力處理掉與「舊 protected footprint + 10% review reserve」同量級的歷史 ownership/compatibility 負擔；否則代表 protected-boundary reconsideration沒有實質發生。

## A.4 T0 baseline 漂移時的重算規則

施工真正開始時，若 T0 bridge LOC / protected footprint和 publication snapshot不同，必須只在本 Appendix 重新計算，然後把結果寫入 T0 evidence；MRG / Gate F / DoD 讀該 evidence 的符號值，不自行改字面數字：

```text
MIN_REDUCTION = max(
    ABSOLUTE_MIN_REDUCTION_FLOOR,
    ceil_to_100(MIN_REDUCTION_RATIO × T0_BRIDGE_LOC)
)

PROTECTED_REVIEW_BUDGET = ceil(
    PRIOR_PROTECTED_LOC × (1 + PROTECTED_REVIEW_RESERVE_RATIO)
)

CALCULATED_FINAL_CEILING
    = round_to_100(T0_BRIDGE_LOC - PROTECTED_REVIEW_BUDGET)
```

但執行者不得自行把 gate放寬。

使用：

```text
EFFECTIVE_FINAL_CEILING
    = min(ABSOLUTE_FINAL_CEILING_CAP, CALCULATED_FINAL_CEILING)
```

也就是 baseline後來若變肥，不能因此把允許的 final ceiling往上抬。

若 baseline已因其他已整合工作自然降很多，計算會變得更嚴格；若嚴格到不合理，必須回報使用者修改 spec，不能自行改公式。

## A.5 這不是「Bridge 理論最小值」

理論最小值只能在 T0/B-series line attribution後估。

本 Phase最後必須額外交付：

```text
FINAL_RESIDUAL_ATTRIBUTION
```

按以下類別列出剩餘 LOC：

```text
BOOTSTRAP
COMPOSITION
LIFECYCLE
PUBLIC_COMPAT
LEGACY_COMPAT
PRESENTATION_GLUE
SPEC_BLOCKED
```

下一 Phase若要再往 5k/4k收斂，應以這份 residual attribution反推，不再拿整數先猜。

---

# Appendix B — Facade Audit Workload Contract

Facade 69 項的審核不是「69 次 grep」。

每一項可能包含：

- direct Python caller；
- monkey-patched facade method；
- Tk callback；
- string/event binding；
- property descriptor；
- legacy external/public caller；
- tests-only reference；
- dynamic `getattr`；
- persistence/plugin compatibility。

因此 B6 的完成工量至少是：

```text
inventory 69/69
→ <=12 entries per batch
→ caller/dynamic classification
→ mutation
→ focused verification
→ retained rationale
```

在 publication count 69 下，**至少 6 批**。

Master/checkpoint 必須顯示：

```text
facade_total
facade_accounted
facade_deleted
facade_migrated
facade_retained
facade_dynamic_pending
current_batch
```

若只寫「Facade audit completed」但沒有 `69/69 accounted`，視為未完成。

---

# 18. Definition of Done

本 Phase 的完成定義同時包含 **architecture correctness** 與 **meaningful reduction**。

## Architecture DoD

- Bridge不持有已由 CURRENT owner接管的 domain implementation；
- owner不 reverse-import Bridge；
- single composition root；
- no second geometry/manufacturing path；
- bounded typed seams；
- protected product behavior parity；
- old KEEP decision若被 supersede，有完整 machine-readable provenance。

## Reduction DoD

以 T0 execution baseline計：

```text
TOTAL_BRIDGE_REDUCTION >= MIN_REDUCTION
FINAL_BRIDGE_LOC <= EFFECTIVE_FINAL_CEILING
```

因此：

> **這一版明確不接受「最後只少幾百行」作為完成。**

若 Stage A只少幾百行：

> 自動進 Stage B。

若 Stage B某個舊 KEEP經重新驗證仍應保留：

> 可以保留，但其他候選必須繼續審，直到 Final Budget GREEN；或由使用者明確修改本規格。

若所有合理 boundary都完成 evidence、Combined全綠，但仍無法達 budget：

> 標 `ARCHITECTURE_BUDGET_BLOCKED`，不得假裝 COMPLETE，也不得危險搬碼湊數。

本 Phase 真正希望達到的狀態是：

> `fold_designer_bridge.py` 不再是一個「因為歷史 KEEP 太多所以永遠拆不下去」的相容巨石，而是一個經重新驗證後只保留必要 composition / lifecycle / compatibility surface 的薄 bridge。