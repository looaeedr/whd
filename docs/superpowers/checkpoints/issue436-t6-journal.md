# Issue #436 / #429 T6 — Cumulative A/B, visual acceptance, integration & closure

## Authority
- Parent: #429
- Predecessor: #435 CLOSED/completed
- Fixed T0 production baseline: `50e14c7054916cb0b9597c61194725939c5de323`
- Accepted T5 production candidate: `e3438fab1a77eee7bbcf8d03b0c2d765a1bcceea`
- T6 branch: `qa/issue436-t6-cumulative-acceptance-20260920`

## Knowledge Preflight
- RUN `35500313918` — SUCCESS

## Cumulative full A/B
Source full-suite RUN: `35504038682`.

Headless:
- baseline: **2630 PASS / 11 FAIL / 460 SKIP / 0 ERROR**
- candidate: **2633 PASS / 8 FAIL / 485 SKIP / 0 ERROR**

Xvfb:
- baseline: **3052 PASS / 48 FAIL / 1 SKIP / 0 ERROR**
- candidate: **3079 PASS / 46 FAIL / 1 SKIP / 0 ERROR**

All four lanes preserved:
- `config.ini`
- repository DXF digest
- tracked diff invariant

The raw candidate-only set contained two stale presentation-source contracts:
1. `tests/process/test_issue426_phase5_t5_bridge_compression.py::test_t5_mount_unmount_transition_sources_match_t0_behavior`
2. `tests/test_phase6_latest_layout_contract.py::test_assembly_left_panel_lists_all_sheet_parts_with_view_only_checkboxes`

Both contracts asserted pre-#429 ownership:
- direct Assembly `pack/pack_forget` in bridge entrypoints;
- `assembly_parts_panel.master is app.left`.

They were migrated test-only to the accepted #429/#431 single shared-host contract:
- `_phase6_mount_shared_content(...)` owns mode mounting;
- `assembly_parts_panel.master is app.shared_content_host`.

Production runtime was not changed by T6 remediation.

Normalized classifier:
```text
NEW_HEADLESS=[]
NEW_XVFB=[]
NEW_HEADLESS_ERRORS=[]
NEW_XVFB_ERRORS=[]
CONFIG_INVARIANT=1
DXF_REPO_INVARIANT=1
```

## Structural / protected lanes
Non-visual remediation/finalizer evidence established:
```text
SHARED_CONTENT_HOST_COUNT=1
ACTIVE_SHARED_CONTENT_MODE_COUNT=1
SEPARATE_ASSEMBLY_REGION=0
SEPARATE_CORNER_DATA_REGION=0
PERMANENT_HIDDEN_SECOND_HOST=0
DUPLICATE_WIDGET_TREE=0
DUPLICATE_EVENT_BINDING=0
CALLBACK_MULTIPLICATION=0
STALE_WIDGET_REFERENCE=0
MOUSEWHEEL_EXCEPTION=0
GEOMETRY_DRIFT=0
DATAFLOW_DRIFT=0
PERSISTENCE_DRIFT=0
CALLBACK_SEMANTIC_DRIFT=0
VISIBILITY_SEMANTIC_DRIFT=0
CORNER_DATA_BEHAVIOR_DRIFT=0
PROTECTED_DRIFT=0
```

## Final visual acceptance
Canonical visual-final RUN: `35505738075` — SUCCESS.

Jobs:
- prior-gates: SUCCESS
- visual: SUCCESS
- target-drift: SUCCESS
- accepted: SUCCESS

Visual artifact:
- ID `10603786010`
- SHA256 `c6a470600465617de736413eee35de7ece8eb2a45ec98009cea91a3ba940e093`

Final acceptance artifact:
- ID `10603781041`
- SHA256 `ae9f83cd48bade30983d70a1746b0180509816afbafe1b5bbed097c11f0c7021`

Three screenshots were reviewed:
- normal part
- Assembly
- Corner Data

All three modes use the same left-side anchor and width:
- x = 10
- y = 123
- width = 318
- mapped content tree count = 1

Content heights legitimately differ by mode. The screenshot harness has no final-scene provider connected, so the central 3D pane can show its provider-not-connected fallback; that does not affect the shared-content visual acceptance.

Machine visual gates:
```text
VISUAL_SCREENSHOT_COUNT=3
SHARED_HOST_ANCHOR_WIDTH_PARITY=1
ACTIVE_SHARED_CONTENT_MODE_COUNT=1
```

Final acceptance artifact declares:
```text
DECISION=GREEN
FORCE_PUSH=0
```

## Accepted-head drift audit
The canonical visual-final accepted HEAD is:
`3fd041736d81194182ea568f2173da3cc6484aa1`

Subsequent branch changes before closing touched only the temporary T6 remediation workflow. No production runtime or accepted test-contract drift occurred.

## Closing policy
The closing commit must:
- remove the four temporary T6 QA workflows;
- retain the two migrated permanent tests;
- retain preflight / acceptance evidence;
- add this journal and checkpoint.

Then:
1. non-force fast-forward `cleanup/2d-3d-sync`;
2. read back exact production SHA;
3. run focused post-merge smoke from that exact production SHA;
4. close #436 and parent #429 only after post-merge smoke is GREEN.
