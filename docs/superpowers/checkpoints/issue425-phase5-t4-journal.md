# Phase 5 / Issue #425 T4 Journal

## Authority

- MASTER_ID: `#413`
- TASK_ID: `#425 / T4`
- TARGET_X: `cleanup/2d-3d-sync`
- FROZEN_X_BASE_SHA: `396bfd96524a44a178c29bbefaf1b7c0437c119f`
- ACCEPTED_PREDECESSOR: `#424 @ 35641caa9abe5927766135ee5e5621bfce1cf775`
- WORK_ORDER_BRANCH: `refactor/issue413-phase5-assembly-presentation-20260920`
- Requirement Authority: Phase 5 v1.7 accepted master #413
- T4 scope: Final Scene Assembly presentation sinks/visibility + Structure Tree compatibility only.

## Knowledge Preflight

Exact router input:

```text
TASK=派工執行 Phase 5 accepted specification T4 #425: rewire FinalScene assembly presentation ports, visibility tri-state and fallback writeback, DM7 Structure Tree compatibility to panel-owned Tk vars; preserve render order, lossy formed/blank text sink, corner separate sink, registry-empty no-op behavior, UI parity, remote QA and durable closure

CHANGED_FILES=
phase6_assembly_panel.py
fold_designer_bridge.py
tests/process/test_issue425_phase5_t4_final_scene_visibility.py
.github/workflows/qa-issue425-phase5-t4.yml
docs/superpowers/checkpoints/issue425-phase5-t4-journal.md

REQUIRED_SKILLS=10
REQUIRED_REFERENCES=10
KNOWLEDGE_PREFLIGHT_RC=0
```

READ_SKILL: Python測試實務
READ_SKILL: 截角資料入口收斂
READ_SKILL: UI設計與去AI味
READ_SKILL: 派工
READ_SKILL: issue-closure-gate
READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: executable-continuity-controller
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_SKILL: 驗證板件與DXF

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/dm7_part_navigation_pitfalls.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md

## Accepted Fixed-Root Characterization

### Final Scene protected order

At accepted predecessor `35641caa...`, `Phase6FinalSceneViewAdapter.query_assembly_render_data()` is:

```text
resolve_geometry()
→ publish_live_state(force=True)
→ build AssemblyScenePart tuple
→ assembly_corner_text_sink(corner_texts)
→ per part assembly_part_text_sink("formed", ...)
→ per part assembly_part_text_sink("blank", ...)
→ if part_key == "box_body": refresh_box_body_piece_info(render_data)
→ assembly_visibility(parts)
→ make_assembly_scene_render_data(...)
```

`publish_live_state(force=True)` remains outside panel ownership.

Producer text kinds are exactly `formed` and `blank`. Corner remains a separate sink.

### Existing Bridge sink semantics

`_phase6_final_scene_corner_text_sink`:
- normalizes keys/values to strings;
- writes compatibility snapshot `_phase6_last_assembly_corner_dimension_texts`;
- writes existing corner StringVar when present;
- missing target silently drops.

`_phase6_final_scene_part_text_sink`:
- `kind == "formed"` targets formed map;
- all other kinds target blank map (legacy sink behavior);
- missing target silently drops.

The compatibility corner snapshot has no reader elsewhere in Bridge. It may remain in the thin wrapper while Tk mutation moves into panel.

### Visibility semantics

Top-level:
- missing var defaults visible;
- all-hidden + non-empty parts falls back to logical `box_body` if present, otherwise first part;
- if fallback var exists, writes it `True`.

BoxBody physical pieces:
- source keys come from resolved `box_body.render_data.pieces`;
- no piece keys => `None`;
- piece keys + logical box_body hidden => `()`;
- logical box_body visible => tuple of visible pieces;
- missing piece var defaults visible;
- if result empty and visible top-level set is exactly `{"box_body"}`, first piece is written `True` and returned as one-element tuple.

Therefore `None != () != non-empty tuple` is protected.

### Render trigger ownership

Panel visibility controls call `AssemblyPanelActions.on_visibility_changed`.
Bridge target `_phase6_on_assembly_part_visibility_changed` owns:
```text
display_mode == "assembly"
→ do_update()
```
Panel must not read display mode.

### Structure Tree compatibility

`_phase6_structure_tree_visibility_var(key)` currently returns the same Assembly top-level or BoxBody piece BooleanVar.

Registry-empty physical piece states:
1. before first render-time BoxBody piece refresh;
2. after panel rebuild and before next render-time piece refresh.

When piece var is absent:
- tree refresh displays `顯示`;
- visibility-column click returns `break`;
- no visibility mutation;
- no render request.

After piece registry repopulates:
- Structure Tree toggle mutates the exact shared piece BooleanVar;
- visibility-changed action is invoked;
- Structure Tree refresh follows.

## T4 Target Ownership

Add panel presentation methods:
- `set_corner_texts(values)`
- `set_part_text(kind, part_key, value)`
- `resolve_visibility(parts)`
- `visibility_var(key)`
- `notify_visibility_changed()`

Bridge retains thin compatibility wrappers only:
- corner snapshot + panel delegate;
- part-text panel delegate;
- visibility panel delegate;
- Structure Tree shared-var panel delegate;
- display-mode-aware action target.

Forbidden:
- second bool visibility store;
- panel import/read of display mode;
- DM7 topology ownership in panel;
- manufacturing/project mutation;
- tri-state collapse;
- registry-empty click enhancement;
- Final Scene order change.

## State

```text
STATE=RED
HEAD=35641caa9abe5927766135ee5e5621bfce1cf775
RUN_ID=RUN_NOT_CREATED
NEXT_ACTION=Add focused T4 requirement RED for panel-owned sinks/visibility/shared Structure Tree vars and exact Final Scene order.
```


## RED Harness Classification

- RUN `35489209046` @ `ba34e051677256fb0df77fe55439be3f22f725ec`
- Preflight: GREEN
- Scope: GREEN
- Focused pytest did not reach requirement assertions.
- Collection failed because workflow installed only pytest before importing `fold_designer_bridge.py`; repository dependency `ezdxf` was missing.
- Marker: `T4_RED_INVALID=harness_or_collection_error`
- This run is **NOT** requirement RED evidence.
- Fix is workflow-only dependency installation; no production file changed.


## RED / GREEN Evidence

### Harness-only first RED attempt

- RUN `35489209046` @ `ba34e051677256fb0df77fe55439be3f22f725ec`
- Preflight: GREEN
- Scope: GREEN
- collection failed before requirement assertions because workflow had not installed repository dependency `ezdxf`.
- `T4_RED_INVALID=harness_or_collection_error`
- NOT accepted as requirement RED.
- workflow-only fix installed `requirements.txt + matplotlib`; production unchanged.

### Valid requirement RED

- RUN `35489241292` @ `d63de3f9bde1395123764ad8e053f1483bbe07c8`: SUCCESS.
- `KNOWLEDGE_PREFLIGHT_RC=0`
- `T4_SCOPE_EXTERNAL_DRIFT=0`
- focused Xvfb: `10 failed / 2 passed`
- `T4_RED_INTENDED=1`
- `T4_RED_PYTEST_RC=1`
- no collection/import/syntax error
- legacy lane remained `21 passed / 1 skipped`
- `CONFIG_INVARIANT=GREEN`

### Minimal GREEN implementation

- panel Final Scene/visibility ports commit: `180272934718a0b06de2b7af9a813b03455b8f47`
- Bridge thin-delegate commit: `5d3a69a19a29221863fbe494fca6c39cf265ab64`

Panel now owns:
- `set_corner_texts(values)`
- `set_part_text(kind, part_key, value)`
- fixed-root visibility resolution including top-level fallback/writeback and BoxBody piece tri-state/fallback
- exact panel visibility-var lookup for Structure Tree
- visibility-changed action emission with no display-mode read

Bridge retains:
- corner compatibility snapshot write
- thin sink/visibility wrappers
- DM7 physical-piece classification for Structure Tree identity
- display-mode-aware render action target

### Accepted GREEN

- RUN `35489373830` @ `5d3a69a19a29221863fbe494fca6c39cf265ab64`: SUCCESS.
- focused Xvfb: `12 passed`
- `T4_GREEN=1`
- `FINAL_SCENE_ASSEMBLY_QUERY_ORDER_PARITY=GREEN`
- `FINAL_SCENE_TEXT_SINK_PARITY=GREEN`
- `UNKNOWN_TEXT_KIND_PRODUCED=0`
- `TOP_LEVEL_VISIBILITY_PARITY=GREEN`
- `BOX_PIECE_VISIBILITY_PARITY=GREEN`
- `VISIBLE_BOX_BODY_PIECE_TRISTATE_PARITY=GREEN`
- `TOP_LEVEL_FALLBACK_WRITEBACK_PARITY=GREEN`
- `BOX_PIECE_FALLBACK_WRITEBACK_PARITY=GREEN`
- `VISIBILITY_CHANGE_RENDER_ONLY_IN_ASSEMBLY_MODE=true`
- `PANEL_READS_DISPLAY_MODE=0`
- `VISIBILITY_RENDER_MODE_GATE_OWNED_BY_ACTION_TARGET=true`
- `STRUCTURE_TREE_VISIBILITY_STATE_DUPLICATION=0`
- `STRUCTURE_TREE_VISIBILITY_PARITY=GREEN`
- `STRUCTURE_TREE_REGISTRY_EMPTY_PIECE_DISPLAY_PARITY=GREEN`
- `STRUCTURE_TREE_REGISTRY_EMPTY_PIECE_CLICK_NOOP_PARITY=GREEN`
- `STRUCTURE_TREE_REGISTRY_REPOPULATED_PIECE_TOGGLE_PARITY=GREEN`
- panel architecture: Bridge/DM7/Settings/display-mode/manufacturing/project/second-store all `0`
- legacy Assembly/BoxBody lane: `21 passed / 1 skipped`
- `LEGACY_T4_ASSEMBLY_REGRESSIONS=GREEN`
- `CONFIG_INVARIANT=GREEN`
- retained single pytest skip remains explicit SKIP and is not counted as PASS.

## Acceptance State

```text
STATE=GREEN
TESTED_IMPLEMENTATION_HEAD=5d3a69a19a29221863fbe494fca6c39cf265ab64
RUN_ID=35489373830
NEXT_ACTION=Run exact-head closing qualification/finalization proof with no further production changes.
```
