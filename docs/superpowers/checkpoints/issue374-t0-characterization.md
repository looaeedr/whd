# #374 / T0 — UI layout characterization

## Identity

- Parent: #373
- Task: #374
- Production baseline: `cleanup/2d-3d-sync @ 4137b62887c3dc20c6ee5bbd4d753f485dcaf23b`
- Work branch: `ui/issue374-layout-characterization-20260919`
- Scope: characterization + RED only. No production UI relocation.

## User-approved target contract

1. Main selector becomes one operator navigation entry point:
   - `組合體`
   - all existing physical/logical part entries in their existing authoritative order
   - `截角資料`
2. `組合體` has no child selector.
3. Assembly page combines current assembly content, complete visibility controls, and existing per-part read-only data in one continuous content region.
4. Per-part data is shown immediately below its part row and can collapse/expand.
5. Hidden parts remain in the list and retain their data; hide/show changes only view visibility.
6. Assembly part data is read-only. No new edit capability.
7. User-visible wrapper labels `輸入區` and `顯示區` are removed.
8. Corner Data moves only its navigation entry. Its data, state, drawing, callbacks, and behavior stay unchanged.
9. Geometry, manufacturing authority, persistence, sync direction, and callback semantics stay unchanged.

## Current navigation characterization

At the fixed baseline:

- `part_choice_button / part_choice_menu` is a visible compact sheet-metal selector.
- `_fix11_refresh_part_buttons()` populates that compact menu from only
  `_phase6_operator_part_selector_keys(self.available_parts)`.
- `組合體` and `截角資料` are not entries in that compact menu.
- `_phase6_refresh_structure_tree()` separately inserts:
  - `mode:assembly` / `組合體`
  - `mode:corner_data` / `截角資料`
  - then physical/logical part rows.
- `_phase6_build_content_switch()` additionally constructs three visible buttons:
  - `輸入區`
  - `組合體`
  - `截角資料`

Therefore the current UI has duplicated presentation entry surfaces for assembly/corner-data, while the requested target is one main selector projection. The authority itself remains `designer_workspace.active_part` / existing mode state; this task must not create a second state owner.

## Current assembly characterization

- `assembly_parts_panel` is a scrollable view.
- `_phase6_refresh_assembly_parts_panel()` creates one row per current operator part identity.
- Each row currently owns:
  - the existing visibility BooleanVar / Checkbutton;
  - formed-size display StringVar;
  - unfolded-blank display StringVar;
  - corner-size display StringVar.
- Those data strings are presentation-only. There are no per-row editing controls for them.
- Box Body physical child rows are created by `_phase6_refresh_box_body_piece_info_rows()` and use the same pattern: visibility Checkbutton + read-only dimension/corner labels.
- Visibility state is preserved across row rebuilds through existing visibility maps/stash.
- `_phase6_query_assembly_render_data()` filters rendered output using those existing visibility vars; layout changes must continue delegating to them.

Current missing target behavior: the per-part information is always expanded; there is no per-part collapse/expand presentation control.

## Current Corner Data characterization

- Structure Tree mode `mode:corner_data` and the separate content-switch button both route to the existing Corner Data view.
- Corner Data selection reads current stable identities from `designer_workspace.available_parts`.
- Its 2D/unfold projection is view-only and consumes existing authoritative render data.
- This chain is not to be rewritten by #373; only the entry location changes.

## Current MouseWheel regression

Current assembly scrolling contains:

```python
delta = int(getattr(event, "delta", 0) or 0)
number = int(getattr(event, "num", 0) or 0)
```

On Windows `<MouseWheel>`, Tk may provide `event.num == '??'`.
That makes the second conversion raise `ValueError` before scroll handling.

A safe event-normalization pattern already exists in the Corner Data mousewheel handler; T4 can reuse the behavior pattern without changing assembly scroll direction or step size.

## T0 intended RED signals

- `RED: #373 main selector does not yet contain assembly + existing parts + corner data`
- `RED: assembly MouseWheel still crashes on nonnumeric event.num`

These REDs prove target gaps only. They are not production calculation sources.

## Isolation

#363 Phase 3 explicitly forbids UI redesign / unrelated baseline-debt repair. #373 stays on its own branch chain and must not be merged through #369 or another #363 task branch.
