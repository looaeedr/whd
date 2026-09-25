# Issue #432 / T2 — General part input/display content on the shared host

## Authority
- Parent: #429
- Predecessor: #431 CLOSED/completed
- Exact T2 base: `7ac2c3a1f3743e74750ed148e132be4004e340e5`
- Branch: `refactor/issue432-t2-general-part-shared-host-20260920`
- Accepted TESTED_SHA: `94cedb227a1f6c1fd99529eb9a6d0d8ef22e35bb`

## Knowledge Preflight
Initial fail-closed preflight:
- RUN `35497154030`
- classification: missing `截角資料入口收斂` + DM7 entry-convergence durable evidence

Required Skill/references were then actually read and persisted:
- `截角資料入口收斂`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md`
- `個人AI檔案庫/踩坑庫/dm7_part_navigation_pitfalls.md`

Retry:
- RUN `35497204537`
- JOB `106042271050`
- result: SUCCESS / `KNOWLEDGE_PREFLIGHT_RC=0`

## Characterization
T2 intentionally did not manufacture a fake RED. The #431 implementation might already satisfy the T2 contract, so the workflow first proved `fold_designer_bridge.py` is byte-identical to the #431 closing SHA.

First characterization RUN `35497321811`:
- production bridge exact predecessor: PASS
- 3 tests PASS
- 1 test FAIL because the new test incorrectly required `_fix11_add_part("door")` to force `workspace.active_part == "door"`
- this stronger active-part rule is not part of #432
- production remained unchanged

The test was narrowed to the actual T2 contract only:
- topology add/remove parity
- active identity remains valid
- part mode stays on the shared host
- Assembly / Corner Data remain unmounted in part mode

Accepted characterization RUN `35497419539`, JOB `106042871380`:
```text
4 PASS
0 FAIL
0 SKIP
PRODUCTION_RUNTIME_EDIT=0
PART_CONTENT_HOST_IS_SHARED_HOST=true
ASSEMBLY_WIDGET_TREE_MOUNTED_IN_PART_MODE=0
CORNER_DATA_WIDGET_TREE_MOUNTED_IN_PART_MODE=0
PART_INPUT_CALLBACK_PARITY=GREEN
PART_DISPLAY_PARITY=GREEN
ADD_DELETE_PART_PARITY=GREEN
T2_ALREADY_GREEN_AFTER_T1=1
```

Artifact:
- ID `10600691899`
- SHA256 `7c89216761e1dbb27984e7f36c9cbd3f039410164d8d4d5b2b4464798a0553ab`

## Final A/B
RUN `35497507917` — SUCCESS.

Source guard:
```text
PRODUCTION_BRIDGE_EXACT_PREDECESSOR=1
PRODUCTION_RUNTIME_EDIT=0
```

Common UI A/B covered the accepted #430/#431/#384 shared-host contracts:
```text
COMMON_UI_AB_EXACT_OUTCOME_PARITY=1
COMMON_UI_BASELINE=11_PASS
COMMON_UI_CANDIDATE=11_PASS
```

Candidate T2:
```text
PART_CONTENT_HOST_IS_SHARED_HOST=true
ASSEMBLY_WIDGET_TREE_MOUNTED_IN_PART_MODE=0
CORNER_DATA_WIDGET_TREE_MOUNTED_IN_PART_MODE=0
PART_INPUT_CALLBACK_PARITY=GREEN
PART_DISPLAY_PARITY=GREEN
ADD_DELETE_PART_PARITY=GREEN
T2_ALREADY_GREEN_AFTER_T1=1
```

Accepted:
```text
T2_AB_QUALIFICATION_GREEN=1
BASE_SHA=7ac2c3a1f3743e74750ed148e132be4004e340e5
TESTED_SHA=94cedb227a1f6c1fd99529eb9a6d0d8ef22e35bb
```

A/B artifact:
- ID `10601446114`
- SHA256 `6fc1ca3317810256b89b9941d8563e75046e01368a007859d4d8545726f3cd2c`

## Accepted conclusion
T2 is **already GREEN after T1**. No production change is required or allowed for this task.

The closing commit may only:
- update this checkpoint / journal;
- remove temporary #432 QA workflows.

No production or T2 test-contract drift is allowed after TESTED_SHA.

## State
```text
STATE=ACCEPTED
TESTED_SHA=94cedb227a1f6c1fd99529eb9a6d0d8ef22e35bb
FINAL_AB_RUN=35497507917
PRODUCTION_RUNTIME_EDIT=0
NEXT_ACTION=#433 / T3
```
