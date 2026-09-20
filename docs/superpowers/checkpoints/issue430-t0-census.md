# #430 / T0 — Single shared-content host baseline census

Baseline: `cleanup/2d-3d-sync @ 50e14c7054916cb0b9597c61194725939c5de323`

Accepted characterization head: `a3a3a8ec67b1ece5cc27b8392298737ed2c53772`

Accepted remote QA: RUN `35495541940`, artifact `10599994493`.

## Result

The current UI is mutually exclusive at presentation time, but it is **not** a single physical shared-content host.

Current direct mode surfaces under `self.left`:

| Mode | Surface | Creation / owner | Direct left-content host today |
| --- | --- | --- | --- |
| normal part | `fold_editor_host` | Bridge creates `ttk.Frame(self.left)` | `fold_editor_host` |
| assembly | `assembly_parts_panel` | `Phase6AssemblyPanel(self.left)`; owner creates `ttk.Frame(parent)` | `assembly_parts_panel` |
| corner data | `corner_data_panel` | lazy `ttk.Frame(self.left, padding=6)` | `corner_data_panel` |

Remote Tk evidence resolved them to three distinct direct-left identities:
```text
('.!frame.!frame6', '.!frame.!frame5', '.!frame.!frame7')
DIRECT_HOST_COUNT=3
TARGET_SHARED_HOST_COUNT=1
```

`self.left` is the whole left workspace, not a dedicated shared-content host: it also owns selector/actions and compatibility widgets. Treating `self.left` itself as the target host would hide the defect.

## Mode authority census

Existing authority remains intentionally unchanged in T0:

- `_phase6_3d_display_mode`: presentation mode authority, with `single / assembly / corner_data`.
- `designer_workspace.active_part`: real active manufacturing/navigation part.
- assembly/corner-data mode switches do not create a second active-part authority.
- Corner Data selected row is view-only adapter state (`Phase6CornerDataViewAdapter.selected_part_key`) and does not replace workspace active-part authority.
- legacy `content_switch_frame` is compatibility-only; old buttons are `None`.
- retired Structure Tree compatibility objects remain unmapped.

## Mount / unmount census

### Normal part
- show: `_fix11_activate_part()` packs `fold_editor_host`.
- hide for assembly: `_phase6_show_assembly()` calls `fold_editor_host.pack_forget()`.
- hide for Corner Data: `_phase6_show_corner_data()` calls `fold_editor_host.pack_forget()`.

### Assembly
- show: `_phase6_show_assembly()` packs `assembly_parts_panel`.
- hide for normal part: `_fix11_activate_part()` calls `assembly_parts_panel.pack_forget()`.
- hide for Corner Data: `_phase6_show_corner_data()` calls `assembly_parts_panel.pack_forget()`.

### Corner Data
- lazy create: `_phase6_show_corner_data()` creates `corner_data_panel = ttk.Frame(self.left, padding=6)` once.
- show: same function packs `corner_data_panel`.
- hide for normal part: `_fix11_activate_part()` calls `corner_data_panel.pack_forget()`.
- hide for assembly: `_phase6_show_assembly()` calls `corner_data_panel.pack_forget()`.

## Lifecycle characterization

Repeated switching reuses the same three mode-surface objects.

`_fix11_refresh_part_buttons()` and assembly refresh do not replace them.

`_fix11_add_part()` / `_fix11_remove_part()` mutate workspace topology and do not accumulate new mode surfaces.

A fresh designer workspace creates a fresh Tk tree and does not reuse stale widget objects from a prior instance.

At any instant only one of the three current mode surfaces is managed. This proves mutual exclusivity exists today, but does **not** satisfy the single-host requirement.

## Intended RED seam

The test walks each visible mode surface upward to the first widget whose master is `self.left`.

- current architecture: three identities → intended RED;
- target architecture: all three presentations pass through one dedicated shared-content host → GREEN.

Accepted result:
```text
4 PASS
1 intended FAIL
0 SKIP
```

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
