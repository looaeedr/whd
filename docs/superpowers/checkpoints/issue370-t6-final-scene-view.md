---
whd_doc_role: REFERENCE
whd_contract: issue370-t6-final-scene-view
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #370 / Phase 3 T6 — 3D / Final-Scene View Adapter Extraction

## Identity

- Master: #363
- Task: #370 / T6
- Original T6 baseline: `c79ff3e3e0f863a10869f8b1f40416e8686cc711`
- Current-production acceptance baseline: `e121ecfe4a524a80744e92c75c02d69cc9874624`
- Production-first integration branch: `integration/issue370-t6-on-current-production-20260919`
- Accepted production behavior SHA before QA-only cleanup: `e3d6383d5a9ef211408e9f6671aaf43ca11a51df`
- Status: **ACCEPTED**

## Scope / Ownership

Extracted 3D / Final-Scene orchestration into `Phase6FinalSceneViewAdapter` inside the existing deep 3D owner `phase6_final_scene_view.py`.

The bridge now delegates:

- final render-data selection
- assembly-scene bundle construction
- assembly render-data projection
- FinalScene request construction
- cutting-mesh request/render handoff
- 3D scroll forwarding
- renderer install
- committed-view render
- preview enable/disable
- preview refresh

The deep renderer remains `Phase6FinalSceneView`; no second 3D renderer was introduced.

Manufacturing hard boundaries remain:

- no relief/joint solver ownership in the adapter
- no direct manufacturing rebuild calls
- no `fold_designer_bridge` reverse import from the deep view
- provider-missing remains fail-closed
- manufacturing/cache/provider authority remains outside the view adapter

## Characterization RED

Final intended RED:

```text
RUN = 35441386596
result = SUCCESS
T6_BASELINE = c79ff3e3e0f863a10869f8b1f40416e8686cc711
```

The earlier RED RUN `35441356530` was a harness-only failure because `python3-tk` was not installed before pytest collection.

## Focused GREEN

```text
RUN = 35441899248
result = SUCCESS
```

Results:

- ownership contract: 3 PASS
- headless final-scene/provider regressions: 71 PASS / 2 SKIP
- real-Tk 3D/assembly regressions excluding exact inherited RED nodes: 25 PASS / 2 DESELECTED
- exact inherited Xvfb parity: 2 baseline FAIL == 2 candidate FAIL

A diagnostic RUN `35441828040` proved those two assembly-selector failures were inherited from the original T6 baseline and not introduced by T6.

## Original Task-Scoped A/B

```text
RUN = 35441989568
result = SUCCESS
baseline = c79ff3e3e0f863a10869f8b1f40416e8686cc711
tested = c2b9cb07e719ecc5942daf13aa527ddb1dadce5a
```

Classifier:

```text
Headless: 73 nodes / 0 -> 0 FAIL
Xvfb: 27 nodes / 2 -> 2 inherited FAIL
NEW_RELEVANT_HEADLESS = []
NEW_RELEVANT_XVFB = []
NEW_RELEVANT_ERRORS = []
PROTECTED_DRIFT = 0
UNEXPLAINED_3D_DELTA = 0
ISSUE370_T6_AB_DECISION = GREEN
```

## Production Race / Reconciliation

Before production integration, `cleanup/2d-3d-sync` advanced independently from the original T6 baseline to:

```text
e121ecfe4a524a80744e92c75c02d69cc9874624
```

Those production changes modified `fold_designer_bridge.py` for the accepted UI work around:

- main selector navigation
- assembly collapsible data
- wrapper-label removal
- assembly MouseWheel handling

A direct T6 merge was therefore rejected as non-fast-forward/conflicting.

T6 was rebuilt production-first on top of `e121ecfe...`, preserving the accepted UI changes while applying only the T6 3D orchestration ownership transfer.

## Authoritative Production-First A/B

```text
RUN = 35444412113
result = SUCCESS
baseline = e121ecfe4a524a80744e92c75c02d69cc9874624
tested = e3d6383d5a9ef211408e9f6671aaf43ca11a51df
```

This acceptance additionally carried forward the current production UI regression suites:

- `tests/test_issue375_main_selector_navigation.py`
- `tests/test_issue376_assembly_collapsible_data.py`
- `tests/test_issue377_remove_wrapper_labels.py`
- `tests/test_issue378_assembly_mousewheel.py`

Classifier:

```text
Headless: 73 nodes / 0 -> 0 FAIL
Xvfb: 39 nodes / 0 -> 0 FAIL
NEW_RELEVANT_HEADLESS = []
NEW_RELEVANT_XVFB = []
NEW_RELEVANT_ERRORS = []
PROTECTED_DRIFT = 0
UNEXPLAINED_3D_DELTA = 0
ISSUE370_T6_PRODUCTION_FIRST_AB_DECISION = GREEN
```

The temporary production-first A/B workflow and classifier were deleted after acceptance.

## Production Acceptance

The final integration branch is a descendant of current production `e121ecfe...` and is eligible for non-force fast-forward only.

After production readback is identical, the integrated SHA becomes the immutable `T7_BASELINE`.
