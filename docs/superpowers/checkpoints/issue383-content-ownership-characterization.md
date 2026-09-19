---
whd_doc_role: REFERENCE
whd_contract: issue383-content-ownership-characterization
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #383 / T0 — 組合體 content-area ownership characterization

Baseline: `cleanup/2d-3d-sync @ 0947e546063c4c2118cb778d2798da5dbff682b3`

## Current owners

- `part_choice_menu`: main operator dropdown.
- `structure_tree_host / structure_tree`: current sticky, permanently visible **板件 / 功能** presentation.
- `fold_editor_host`: normal part input/edit content.
- `assembly_parts_panel`: assembly show/hide + read-only per-part data.
- `corner_data_panel`: Corner Data content.
- `_phase6_build_content_switch()`: compatibility handles only; no longer user-visible.

The current Structure Tree is not the shared input/display area. It reserves a separate sticky slot using
`structure_tree_spacer.pack(...)` plus `structure_tree_host.place(...)`.

## New accepted ownership

The permanent Structure Tree presentation is superseded by #382.

- Normal part mode: no visible 板件/功能 surface.
- Assembly mode: the same left content region used by normal part input becomes the assembly part/function + data list.
- The assembly list itself owns show/hide presentation; a second Structure Tree is not kept visible beside/above it.
- The hidden Structure Tree object may temporarily remain as compatibility state during migration, but it must not reserve or cover operator layout pixels.

## Current collapse behavior

`_phase6_refresh_assembly_parts_panel()` uses:

```python
details_open = old_open.get(key, True)
```

so fresh assembly rows default **expanded**. #382 requires fresh rows default collapsed.

## Current hierarchy behavior

`phase6_part_navigation.project_hierarchy()` is navigation/domain projection and currently nests only real BoxBody physical children below a present `box_body` aggregate.

Receiving multipart identities also include:
- `door_cN_rM`
- `base_plate_cN_rM`

Those are real authoritative physical identities but do not have a synthetic `door` / `base_plate` domain owner in `available_parts`.

For #382, grouping them visually under labels 門 / 底板 must therefore be **presentation-only**:
- do not add fake workspace parts;
- do not mutate navigation/manufacturing identity;
- each real child retains its existing visibility variable/data;
- a presentation group header does not become a manufacturing/domain identity.

Existing BoxBody child nesting remains based on authoritative `box_body:* ` identities.

## Superseded UI contracts

The following historical tests encode the previous sticky-tree product requirement and must be updated/replaced when T1 goes GREEN:

- `tests/test_issue186_sheetmetal_selector_visibility.py`
- Structure-Tree visibility portions of `tests/test_issue124_structure_tree.py`

Their state/identity/visibility delegation assertions remain useful; only the requirement that the Tree be permanently mapped is superseded.

`tests/test_issue376_assembly_collapsible_data.py` also encodes the old default-open presentation and must change to default-collapsed.

## T0 boundary

T0 changes tests/docs only. No production UI source changes.
