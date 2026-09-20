# #430 / T0 — Single shared-content host baseline census

Baseline: `cleanup/2d-3d-sync @ 50e14c7054916cb0b9597c61194725939c5de323`

Work branch characterization head before RED tests: `f618a373f4fd8199991c04f1c817f78220df3a46`

## Result

The current UI is mutually exclusive at presentation time, but it is **not** a single physical shared-content host.

Current direct mode surfaces under `self.left`:

| Mode | Surface | Creation / owner | Direct left-content host today |
| --- | --- | --- | --- |
| normal part | `fold_editor_host` | Bridge creates `ttk.Frame(self.left)` | `fold_editor_host` |
| assembly | `assembly_parts_panel` | `Phase6AssemblyPanel(self.left)`; owner creates `ttk.Frame(parent)` | `assembly_parts_panel` |
| corner data | `corner_data_panel` | lazy `ttk.Frame(self.left, padding=6)` | `corner_data_panel` |

Therefore the current direct host identity count is **3**, while #429 requires **1**.

`self.left` is the whole left workspace, not a dedicated shared-content host: it also owns the part selector/actions and compatibility widgets. Treating `self.left` itself as the shared host would hide the duplicate-region problem rather than solve it.

## Mode authority census

Existing authority remains intentionally unchanged in T0:

- `_phase6_3d_display_mode`: presentation mode authority, with `single / assembly / corner_data`.
- `designer_workspace.active_part`: real active manufacturing/navigation part.
- assembly/corner-data mode switches do not create a second active-part authority.
- Corner Data selected row is view-only adapter state (`Phase6CornerDataViewAdapter.selected_part_key`) and does not replace workspace active-part authority.
- legacy `content_switch_frame` is compatibility-only; the three old content buttons are `None` and are not a visible second navigation strip.
- retired Structure Tree compatibility objects remain intentionally unmapped.

## Mount / unmount census

### Normal part
- show: `_fix11_activate_part()` packs `fold_editor_host` when returning from a non-single mode.
- hide for assembly: `_phase6_show_assembly()` calls `fold_editor_host.pack_forget()`.
- hide for Corner Data: `_phase6_show_corner_data()` calls `fold_editor_host.pack_forget()`.

### Assembly
- show: `_phase6_show_assembly()` packs `assembly_parts_panel`.
- hide for normal part: `_fix11_activate_part()` calls `assembly_parts_panel.pack_forget()`.
- hide for Corner Data: `_phase6_show_corner_data()` calls `assembly_parts_panel.pack_forget()`.

### Corner Data
- lazy create: `_phase6_show_corner_data()` creates `corner_data_panel = ttk.Frame(self.left, padding=6)` once.
- show: the same function packs `corner_data_panel`.
- hide for normal part: `_fix11_activate_part()` calls `corner_data_panel.pack_forget()`.
- hide for assembly: `_phase6_show_assembly()` calls `corner_data_panel.pack_forget()`.

## Lifecycle census

Repeated switching reuses the same three mode-surface objects; current code does not create a new host on every switch.

`_fix11_refresh_part_buttons()` refreshes selector/presentation data and assembly rows but does not replace these three host objects.

`_fix11_add_part()` / `_fix11_remove_part()` mutate workspace topology and refresh selectors; characterization verifies that those operations do not accumulate additional mode-surface objects.

Project load is delegated through `_phase6_load_project_file()` to the parent callback after validation. The designer-side lifecycle is therefore a fresh workspace instance rather than an in-place fourth content host; T0 separately checks that fresh reopen does not reuse stale widget objects across instances.

## Intended RED seam

The behavior test does not compare the three mode surface widgets themselves. It walks each surface's `master` chain upward and records the first widget whose master is `self.left`.

- current architecture: three different direct hosts → RED;
- target architecture: mode content may remain distinct child trees, but all three must ascend through one dedicated shared-content host → GREEN.

This avoids turning a test observation into a runtime design formula.

## Gates

```text
POST_PHASE5_ROOT_EXACT=1
KNOWLEDGE_PREFLIGHT_RC=0
SHARED_CONTENT_HOST_CENSUS_COMPLETE=1
MODE_AUTHORITY_CENSUS_COMPLETE=1
MOUNT_UNMOUNT_CENSUS_COMPLETE=1
DUPLICATE_REGION_RED_INTENDED=1
PRODUCTION_RUNTIME_EDIT=0
```

Expected focused outcome before T1:

```text
4 PASS
1 intended FAIL:
tests/test_issue430_single_host_red.py::test_t0_intended_red_all_three_modes_require_one_direct_shared_content_host
```
