# Issue #440 — Fold Designer no-wrapper direct-slot acceptance

## User-visible defect

The prior #439 correction still rendered a fixed outer content shell around smaller mode content. The user explicitly rejected this "大框包小框" presentation.

## Final presentation contract

There is no permanent outer content wrapper Frame.

```text
self.left
├─ part_selector
├─ input_content_host
├─ assembly_parts_panel
└─ corner_data_panel
```

Only one mode surface is mapped at a time. All three surfaces are direct siblings under `self.left`, so they occupy the same layout slot without a fixed-height wrapper.

Compatibility aliases create no widget:
- `fold_editor_host is input_content_host`
- `shared_content_host is self.left`

The active mode owns its natural height. There is deliberately no all-mode height parity gate.

## Viewport background

The scroll viewport remains for left-side scrolling, but its empty area uses `WHD_THEME["background"]` so it visually blends into the application instead of forming a large panel-colored rectangle.

The Assembly native canvas uses `WHD_THEME["panel"]` so it does not leak the Tk/OS default light background.

## RED

RUN `35511172826`:
- 3 intended FAIL / 1 PASS
- `EXTRA_CONTENT_WRAPPER_FRAME_COUNT=1`
- `FIXED_OUTER_CONTENT_EXTENT=1`
- `MODE_SURFACES_DIRECT_PARENT_IS_LEFT=0`
- `DEFAULT_TK_CANVAS_BG_LEAK=1`

## Focused GREEN

Canonical latest focused RUN `35511619252`:
- 37 PASS / 0 FAIL / 0 ERROR / 0 SKIP
- `MODE_SURFACES_DIRECT_PARENT_IS_LEFT=1`
- `ACTIVE_MODE_SURFACE_COUNT=1`
- `SAME_LAYOUT_SLOT=1`
- `DEFAULT_TK_CANVAS_BG_LEAK=0`

## Final acceptance

Canonical final RUN `35511690588` — all jobs SUCCESS.

Visual mode bboxes:
- part: `[10, 123, 318, 234]`
- assembly: `[10, 123, 318, 44]`
- corner_data: `[10, 123, 318, 114]`

The x/y/width anchor is identical; height remains content-natural.

Visual artifact:
- ID: `10605812154`
- SHA256: `4d268261d67c4b2abe3657c4100f6c5ec39bc6e9c3d70de1b86c5d5401262dc2`

Protected regression:
- 26 PASS / 1 accepted SKIP
- `GEOMETRY_DRIFT=0`
- `DATAFLOW_DRIFT=0`
- `PERSISTENCE_DRIFT=0`
- `CALLBACK_SEMANTIC_DRIFT=0`
- `CONFIG_INVARIANT=1`

Final gates:
```text
EXTRA_CONTENT_WRAPPER_FRAME_COUNT=0
FIXED_OUTER_CONTENT_EXTENT=0
PACK_PROPAGATE_FALSE_CONTENT_SHELL=0
MODE_SURFACES_DIRECT_PARENT_IS_LEFT=1
ACTIVE_MODE_SURFACE_COUNT=1
SAME_LAYOUT_SLOT=1
SAME_SLOT_ANCHOR_WIDTH_PARITY=1
NATURAL_MODE_HEIGHTS=1
DEFAULT_TK_CANVAS_BG_LEAK=0
GEOMETRY_DRIFT=0
PERSISTENCE_DRIFT=0
CALLBACK_SEMANTIC_DRIFT=0
DECISION=GREEN
FORCE_PUSH=0
```

## Integration policy

Production baseline:
`3be16a4d6e9bde6ad4ad74365f718f2b0385db36`

Integration must be non-force fast-forward only.
