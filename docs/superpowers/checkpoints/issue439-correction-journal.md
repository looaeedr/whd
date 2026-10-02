# Issue #439 — Single physical input region correction

## Why #429 was not enough

#429 made normal input / Assembly / Corner Data share one parent, but it still created a second physical `shared_content_host` Frame under `self.left`. Because the left workspace propagates child geometry, the physical region could resize by active mode.

The prior visual gate only compared x/y/width. That missed the height drift.

Observed pre-correction mode heights:
- normal input: 244
- Assembly: 52
- Corner Data: 122

## Corrected ownership

The original input region is now the only physical content region:

```text
self.left
├─ part_selector
└─ fold_editor_host
   ├─ input_content_host
   ├─ assembly_parts_panel
   └─ corner_data_panel
```

Compatibility:
```text
shared_content_host is fold_editor_host
```

No second shared-content Frame is created.

## Runtime behavior

- `fold_editor_host` is a permanent outer host directly under `self.left`.
- `input_content_host` owns the existing BendingUI.
- the existing Phase 5 Assembly panel is parented directly to `fold_editor_host`.
- Corner Data lazy panel is parented directly to the same `fold_editor_host`.
- `_phase6_mount_shared_content` only swaps the three inner trees.
- the permanent outer host keeps the normal-input physical extent across mode switches.

## Final acceptance

RUN `35508601402` — SUCCESS.

Visual gates:
```text
EXTRA_SHARED_CONTENT_FRAME_COUNT=0
SHARED_CONTENT_HOST_IS_FOLD_EDITOR_HOST=1
OUTER_CONTENT_BBOX_IDENTICAL_ALL_MODES=1
ACTIVE_INNER_CONTENT_TREE_COUNT=1
```

Exact outer bbox for all three modes:
```text
part        = [10, 123, 318, 424]
assembly    = [10, 123, 318, 424]
corner_data = [10, 123, 318, 424]
```

Visual artifact:
- ID `10603858764`
- SHA256 `7d8a7a1fe1aad4c8c4e23734621ddf6fe3f351f83ca19d606ace8d18ec58a5fe`

Protected A/B:
```text
GEOMETRY_DRIFT=0
PERSISTENCE_DRIFT=0
CALLBACK_SEMANTIC_DRIFT=0
```

Protected artifact:
- ID `10604473339`
- SHA256 `7026e4bf3be8604b960dcf8e1938b498adfa11d0a6ebf3e061aba984feb50e0e`

Final classifier:
```text
EXTRA_SHARED_CONTENT_FRAME_COUNT=0
SHARED_CONTENT_HOST_IS_FOLD_EDITOR_HOST=1
FOLD_EDITOR_HOST_DIRECT_PARENT_IS_LEFT=1
INPUT_CONTENT_HOST_PARENT_IS_FOLD_EDITOR_HOST=1
ASSEMBLY_PANEL_PARENT_IS_FOLD_EDITOR_HOST=1
CORNER_DATA_PANEL_PARENT_IS_FOLD_EDITOR_HOST=1
OUTER_CONTENT_BBOX_IDENTICAL_ALL_MODES=1
ACTIVE_INNER_CONTENT_TREE_COUNT=1
SEPARATE_ASSEMBLY_REGION=0
SEPARATE_CORNER_DATA_REGION=0
DUPLICATE_WIDGET_TREE=0
GEOMETRY_DRIFT=0
PERSISTENCE_DRIFT=0
CALLBACK_SEMANTIC_DRIFT=0
DECISION=GREEN
FORCE_PUSH=0
```

## Closing policy

Temporary #439 RED/acceptance workflows are removed before integration. Permanent correction tests and preflight evidence remain.

Integration is allowed only as non-force fast-forward from production baseline
`719f4509371376f9d01fca97553b5199963de4c6`.
