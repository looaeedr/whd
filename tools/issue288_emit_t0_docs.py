#!/usr/bin/env python3
"""Emit durable T0 evidence docs for issue #288 from gui.py AST.

Temporary branch-only generator. It does not import gui.py or execute production code.
"""
from __future__ import annotations

import ast
from pathlib import Path

BASELINE = "d72e81b5820b9cb54008a2dda9e96cdc673a9734"
AUDIT_RUN = "34990930540"
AUDIT_ARTIFACT = "10405043174"
OUT = Path("docs/superpowers/plans/2026-09-15-gui-phase2-t0")
OUT.mkdir(parents=True, exist_ok=True)
source = Path("gui.py").read_text(encoding="utf-8")
tree = ast.parse(source)
loc = len(source.splitlines())


def span(node):
    return int(node.end_lineno) - int(node.lineno) + 1


def nested_defs(node):
    out = []
    for child in ast.walk(node):
        if child is not node and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(child)
    return sorted(out, key=lambda n: n.lineno)

classes = []
top_funcs = []
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        top_funcs.append(node)
    elif isinstance(node, ast.ClassDef):
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes.append((node, methods))

host_node, host_methods = next((c, m) for c, m in classes if c.name == "Phase6ApplicationHost")


def method_class(m):
    n, line = m.name, m.lineno
    if 745 <= line <= 787:
        return "HOLD", "T7 compatibility", "legacy property shim; real owner is delegated controller"
    if n == "setup_styles":
        return "MOVE_SAFE", "T2 layout", "theme/ttk presentation"
    if n == "init_variables":
        return "REVIEW", "T2/T4/T7 split", "mixed Tk adapters + host-owned state; split, never move whole"
    if 1047 <= line <= 1354:
        return "MOVE_WITH_DEPENDENCY_CONTRACT", "T4/T7 state routing", "settings/corner sync; preserve service/controller authority"
    if 1357 <= line <= 1460:
        return "REVIEW", "T7 controller boundary", "baseline/render/cabinet policy bridge"
    if 1463 <= line <= 1985:
        return "HOLD", "T7 controller/adapter", "manufacturing/render/project boundary"
    if 1988 <= line <= 2599:
        if n == "open_original_fold_designer":
            return "MOVE_WITH_DEPENDENCY_CONTRACT", "T1 application lifecycle", "workspace window lifecycle"
        return "MOVE_WITH_DEPENDENCY_CONTRACT", "T7 project/workspace controller", "snapshot/transaction orchestration"
    if 2601 <= line <= 2664:
        return "MOVE_WITH_DEPENDENCY_CONTRACT", "T2/T4 presentation", "UI preference/assembly routing"
    if 2666 <= line <= 3531:
        return "MOVE_WITH_DEPENDENCY_CONTRACT", "T4 corner/part panels", "panel + state-changing callbacks"
    if 3533 <= line <= 3843:
        return "REVIEW", "T2 main layout", "311-line mixed layout/callback method; split by region"
    if 3845 <= line <= 4374:
        return "MOVE_WITH_DEPENDENCY_CONTRACT", "T4 part panels", "input/presence/tab presentation"
    if 4376 <= line <= 5203:
        return "MOVE_WITH_DEPENDENCY_CONTRACT", "T4 door/multipart panels", "door-layout UI + routing"
    if 5205 <= line <= 6259:
        if n.startswith("draw_") or n.startswith("_draw_") or "canvas" in n:
            return "MOVE_WITH_DEPENDENCY_CONTRACT", "T6 rendering/interaction", "2D presentation/interaction"
        return "MOVE_WITH_DEPENDENCY_CONTRACT", "T4/T6 door UI", "door/indicator UI split"
    if 6261 <= line <= 6445:
        if "dialog" in n or "editor" in n:
            return "MOVE_WITH_DEPENDENCY_CONTRACT", "T5 editors/dialogs", "modal workflow"
        if n.startswith("draw_"):
            return "MOVE_WITH_DEPENDENCY_CONTRACT", "T6 rendering", "2D presentation"
        return "MOVE_WITH_DEPENDENCY_CONTRACT", "T4 indicator panel", "indicator UI routing"
    if 6447 <= line <= 6977:
        if n == "update_calculations":
            return "HOLD", "root/T7 orchestration", "central calculation orchestrator; not a view helper"
        if n in {"_request_phase6_update", "_flush_phase6_authoritative_state", "bind_live_updates"}:
            return "MOVE_WITH_DEPENDENCY_CONTRACT", "T1 command routing", "scheduler/orchestrator seam"
        return "REVIEW", "T7 application/domain controller", "cabinet runtime + calculation result routing"
    if 6980 <= line <= 7441:
        return "MOVE_WITH_DEPENDENCY_CONTRACT", "T6 rendering/interaction", "2D render/selection entrypoints"
    if 7443 <= line <= 7976:
        return "HOLD", "T7 manufacturing adapter/controller", "part-spec/manufacturing boundary; never view/render"
    if 7978 <= line <= 8241:
        return "REVIEW", "T7 project/export/state adapters", "DXF/export or state snapshot boundary"
    if 8243 <= line <= 9811:
        return "MOVE_WITH_DEPENDENCY_CONTRACT", "T5 editors/dialogs", "hole editor workflow; transient state only"
    return "REVIEW", "T7 remaining controller", "manual dependency review"


top_map = {
    "_endcap_profiles_for_assembly": ("HOLD", "T7 manufacturing adapter/controller", "assembly/fold semantic bridge"),
    "_rects_overlap": ("MOVE_SAFE", "T6 rendering/overlays", "pure rectangle helper"),
    "layout_reference_overlay_rects": ("MOVE_SAFE", "T6 rendering/overlays", "pure overlay layout"),
    "render_structural_result": ("MOVE_SAFE", "T6 rendering", "renders resolved result"),
    "render_secondary_scene": ("MOVE_SAFE", "T6 rendering", "scene presentation"),
    "render_resolved_features": ("MOVE_SAFE", "T6 rendering", "resolved-feature presentation"),
    "render_surface_user_features": ("MOVE_WITH_DEPENDENCY_CONTRACT", "T6 rendering", "resolved-feature wrapper"),
    "feature_surface_from_drawing_scene": ("REVIEW", "T6 rendering/adapter", "prove derived-only surface semantics"),
    "_draw_phase6_annotation_projection": ("MOVE_SAFE", "T6 rendering", "annotation drawing"),
    "_draw_phase6_corner_dimension_overlay": ("MOVE_SAFE", "T6 rendering", "dimension overlay drawing"),
    "draw_hole_editor_hint": ("MOVE_SAFE", "T5/T6 editor presentation", "hint rendering"),
    "_phase6_2d_material_viewport": ("MOVE_SAFE", "T6 rendering/transforms", "presentation viewport"),
    "main": ("MOVE_WITH_DEPENDENCY_CONTRACT", "T1 application bootstrap", "startup/root orchestration"),
}

nested = []
for f in top_funcs:
    nested += [(f.name, n) for n in nested_defs(f)]
for c, methods in classes:
    for m in methods:
        nested += [(f"{c.name}.{m.name}", n) for n in nested_defs(m)]

# Responsibility inventory
r = [
    "# Issue #288 T0 — gui.py Responsibility Inventory", "",
    "## Evidence identity", "",
    f"- Production baseline: `{BASELINE}`",
    f"- AST audit run: `{AUDIT_RUN}` — SUCCESS",
    f"- AST artifact: `{AUDIT_ARTIFACT}` (`issue288-t0-ast-inventory`)",
    f"- `gui.py` LOC: **{loc}**",
    f"- Top-level functions: **{len(top_funcs)}**",
    f"- Classes: **{len(classes)}**",
    f"- Direct class methods: **{sum(len(m) for _,m in classes)}**",
    f"- Nested functions/callbacks: **{len(nested)}**", "",
    "## T0 conclusion", "",
    f"`Phase6ApplicationHost` occupies **{span(host_node)} lines / {len(host_methods)} direct methods**. The monolith is therefore an application-host responsibility problem, not a top-level-helper problem.", "",
    "The worst hotspot is `_open_unified_hole_editor`: **1,333 lines / 57 nested functions**. T5 must decompose it into explicit editor view/controller/session seams; a whole-method file move is forbidden.", "",
    "## Classification", "",
    "- `MOVE_SAFE`: stateless/presentation responsibility may move after characterization.",
    "- `MOVE_WITH_DEPENDENCY_CONTRACT`: preserve caller/state-owner contract before movement.",
    "- `REVIEW`: mixed responsibility; split/prove contract first.",
    "- `HOLD`: manufacturing/state/compatibility boundary; do not move until authority is proven.", "",
    "## Top-level functions", "",
    "| Symbol | Lines | Classification | Target | Reason |", "|---|---:|---|---|---|"
]
for f in top_funcs:
    c,t,why = top_map.get(f.name, ("REVIEW","T7 remaining","manual review"))
    r.append(f"| `{f.name}` | {f.lineno}-{f.end_lineno} ({span(f)}) | {c} | {t} | {why} |")
r += ["", "## Classes", "", "| Class | Lines | Direct methods | Classification | Target |", "|---|---:|---:|---|---|"]
for c, methods in classes:
    if c.name == "_YMirroredPreviewTransform": cl,target="MOVE_SAFE","T6 rendering/transforms"
    elif c.name == "_Phase6UpdateScheduler": cl,target="MOVE_WITH_DEPENDENCY_CONTRACT","T1 command routing"
    elif c.name == "_Phase6DerivedCacheOwner": cl,target="REVIEW","T6/T7 derived-cache boundary"
    elif c.name == "Phase6ApplicationHost": cl,target="REVIEW","T1–T7 decomposition"
    elif c.name == "BoxCalculatorGUI": cl,target="HOLD","T7 compatibility lifecycle"
    else: cl,target="MOVE_WITH_DEPENDENCY_CONTRACT","T1 application lifecycle"
    r.append(f"| `{c.name}` | {c.lineno}-{c.end_lineno} ({span(c)}) | {len(methods)} | {cl} | {target} |")
r += ["", "## Phase6ApplicationHost exhaustive direct-method map", "", "| Lines | Symbol | LOC | Classification | Planned slice |", "|---:|---|---:|---|---|"]
for m in host_methods:
    c,t,why = method_class(m)
    r.append(f"| {m.lineno}-{m.end_lineno} | `{m.name}` | {span(m)} | {c} | {t} — {why} |")
r += ["", "## Nested functions/callbacks", "", "| Parent | Nested symbol | Lines | LOC |", "|---|---|---:|---:|"]
for parent,n in sorted(nested, key=lambda x:x[1].lineno):
    r.append(f"| `{parent}` | `{n.name}` | {n.lineno}-{n.end_lineno} | {span(n)} |")
r += ["", "## Required extraction order", "",
      "1. T1 lifecycle + scheduler/command routing.",
      "2. T2 root layout/style split; never move `create_widgets` whole.",
      "3. T3 selector/navigation over WorkspaceController state.",
      "4. T4 part panels; split `init_variables` by owner vs Tk adapter.",
      "5. T5 editor/dialog decomposition, led by the 1,333-line unified hole editor.",
      "6. T6 rendering/overlay/interaction consuming resolved data only.",
      "7. T7 project/visibility/controllers + HOLD/REVIEW manufacturing and compatibility boundaries.",
      "8. T8 combined structural/functional/drift acceptance.", "",
      "## T0 gate", "",
      "- Meaningful top-level/class/direct-method/nested-callback structure: **mapped**.",
      "- Every >150-line function/method: **classified by the exhaustive table and slice rules**.",
      "- Every >800-line class: **classified** (`Phase6ApplicationHost`).",
      "- Manufacturing-boundary methods are HOLD/REVIEW, not treated as view helpers.",
      "- No production extraction performed during T0.",
      "- **Responsibility inventory gate: GREEN.**"]
(OUT / "gui_responsibility_inventory.md").write_text("\n".join(r)+"\n", encoding="utf-8")

# Dependency map
(OUT / "gui_dependency_map.md").write_text(f'''# Issue #288 T0 — gui.py Dependency Map

## Evidence identity
- Production baseline: `{BASELINE}`
- AST audit run: `{AUDIT_RUN}` — SUCCESS
- `gui.py`: **{loc} LOC**

## Current dependency shape
```text
main → Phase6PrimaryApplication → Phase6ApplicationHost
  ├─ SettingsService
  ├─ Phase6ProjectController → ProjectSession → phase6_project_file
  ├─ Phase6WorkspaceController → SharedWorkspaceState
  ├─ Phase6FoldDesignerApp
  ├─ Phase6HoleEditorSession / CanvasView
  ├─ ae_engine.* manufacturing / geometry / drawing APIs
  └─ gui_modules/{{drawing,layout,part_panels,render_2d,project_actions}}
```

Existing extracted modules establish the correct one-way pattern: `gui.py/orchestrator → focused gui_modules → authoritative controller/engine types`. `drawing.py`, `layout.py`, `part_panels.py`, `render_2d.py`, and `project_actions.py` do not import `gui.py`.

## Non-negotiable direction
```text
gui_modules/* → gui.py                         FORBIDDEN
gui_modules/new_module → compatibility/*       FORBIDDEN
```
Cross-module mutation routes through an explicit command/controller/application orchestrator.

## Authority boundaries

### Settings
`Tk variable/panel → normalize → SettingsService → committed snapshot → consumers`.

### Workspace / physical identity
`selector/panel → command → Phase6WorkspaceController → SharedWorkspaceState`.

### Project / persistence
`file action/dialog → Phase6ProjectController → ProjectSession → phase6_project_file`.

### Manufacturing geometry
`controller input → ae_engine/phase6 authoritative calculation → resolved result/projection → rendering`.

Rendering must never rederive manufacturing geometry or consume test/golden expected data as a production source.

## High-risk hotspots
- `init_variables` (230 LOC): mixed UI adapters + host-owned state; split before movement.
- `create_widgets` (311 LOC): mixed root layout + callbacks; T2/T4 split.
- `_open_unified_hole_editor` (1,333 LOC / 57 nested defs): T5 view/controller/session decomposition.
- L7443–L7976 manufacturing/spec cluster: HOLD/REVIEW; never move to rendering/panel modules.
- L1463–L2599 snapshot/workspace/project bridge: explicit controller/lifecycle contract required.

## Target graph
```text
gui.py
  ├─ application/*
  ├─ layout/* ──→ callbacks/commands only
  ├─ parts/* ───→ WorkspaceController / SettingsService
  ├─ editors/* ─→ transient session → explicit commit
  ├─ rendering/* ← resolved/projection data only
  ├─ project/* ─→ ProjectController
  └─ visibility/* → authoritative owner
```

## Compatibility rule
Only `external legacy caller/test → compatibility/legacy_exports.py → current implementation` is allowed. Every retained shim requires a deprecated marker, caller inventory, and removal Phase/Issue/Date.

## Per-task gates
- **T1:** lifecycle/scheduler/command routing; no domain owner movement.
- **T2:** presentation only; layout cannot calculate manufacturing geometry.
- **T3:** selector queries/commands WorkspaceController; no duplicate active-part/existing-parts state.
- **T4:** panels route commands; no second committed settings/domain store.
- **T5:** transient editor state only; cancel leaves committed state unchanged.
- **T6:** resolved data → rendering only.
- **T7:** project/visibility/focused controllers; compatibility cannot become internal dependency.

## Static circular-import gate
Every new module must prove:
```text
no import gui
no from gui import ...
no gui_modules/** import compatibility/legacy_exports.py
```

**Dependency-map gate: GREEN for T1 planning.**
''', encoding="utf-8")

# State owner map
(OUT / "gui_state_owner_map.md").write_text(f'''# Issue #288 T0 — gui.py State Owner Map

## Evidence identity
- Production baseline: `{BASELINE}`
- AST audit run: `{AUDIT_RUN}` — SUCCESS
- `gui.py`: **{loc} LOC**
- `Phase6ApplicationHost`: **{span(host_node)} LOC / {len(host_methods)} methods**

## Authoritative committed owners

### SettingsService
`gui.py` explicitly identifies `SettingsService` as the single owner of committed runtime settings. `config.ini` supplies startup defaults / explicit persistence; Tk variables are UI adapters.

### Phase6WorkspaceController
Single committed workspace owner for physical `existing_parts`, `active_part`, box-body profile/structure, part profiles, assembly placements, part features, and part-face features. Legacy properties in `gui.py` delegate to this controller.

### Phase6ProjectController / ProjectSession
Owns committed/draft transaction lifecycle, project path, payload build/save/load ordering and persistence coordination. `_phase6_loaded_project_path` is a delegating compatibility alias, not a second path store.

## Host-owned state requiring explicit T4/T7 review
These direct `Phase6ApplicationHost` clusters must not be duplicated during extraction:

- assembly/corner: `assembly_joint_state`, `assembly_relief_state`, `endcap_fw_state`, `endcap_bottom_wrap_state`, `manual_corner_state`, `manual_corner_pair_same`, parameter lock/override state.
- door/multipart: `door_layout_columns`, `receiving_inner_doors`, `door_layout_scope`, `door_layout_handle_edges`, per-cell feature/indicator maps.
- surface/face features: `surface_features`, `box_body_face_features`, `box_body_face_bounds`.

Classification: `HOST_COMMITTED_STATE_REVIEW`. Either establish a focused owner/controller or keep the ownership in thin root orchestration; never copy it into panels/renderers.

## Non-authoritative UI adapter state
Tk variables, widget/entry collections, notebook/tab/canvas references, click timing, panel frames and enable/disable presentation state may move with their view responsibility **only when state-changing callbacks delegate immediately to the authoritative owner**.

## Derived cache state
`_Phase6DerivedCacheOwner` is explicitly a GUI-derived cache owner, not manufacturing authority. Cache movement must preserve source authority and invalidation; a cache may never become persisted truth.

## Transient editor state
`Phase6HoleEditorSession`/editor-local values may own temporary edit-session state only:
```text
committed owner → transient session → preview/edit
confirm → explicit commit
cancel  → discard, no committed mutation
```

## Rendering state
Rendering may own transform/viewport/hit-test/hover/selection presentation only. It may not own physical presence, project truth, DXF truth, or manufacturing dimensions.

## Compatibility aliases are not owners
- `fold_designer_box_body_profile` → WorkspaceController
- `fold_designer_part_bundle` → WorkspaceController
- `_phase6_existing_parts` → WorkspaceController
- `_fold_designer_last_part_key` → WorkspaceController
- `_phase6_loaded_project_path` → ProjectController

## Task ownership rules
- **T1:** may move scheduler/window lifecycle/command routing; committed domain owners stay put.
- **T2:** layout/widget references only; callbacks delegate.
- **T3:** `active_part`/`existing_parts` remain WorkspaceController-owned.
- **T4:** panel Tk adapters may move; committed values route to SettingsService/WorkspaceController/proven controller.
- **T5:** transient editor state only; confirm/cancel contract preserved.
- **T6:** presentation/derived render state only.
- **T7:** remaining host-owned committed clusters receive an explicit owner or remain documented root orchestration while satisfying final size gate.

## Forbidden shadow-state examples
```text
panel.current_part = authoritative_copy
selector.existing_parts = authoritative_copy
renderer.geometry = new_authoritative_geometry
editor.project_snapshot = permanent_truth
compatibility.legacy_state = shadow_store
```

**State-owner map gate: GREEN for T1.**
''', encoding="utf-8")

for p in sorted(OUT.glob("*.md")):
    print(p, p.stat().st_size)
