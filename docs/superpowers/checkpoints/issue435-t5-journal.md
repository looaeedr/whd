# Issue #435 / T5 — Switch lifecycle, state preservation & duplicate-tree guards

## Authority
- Parent: #429
- Predecessor: #434 CLOSED/completed
- Exact T5 base: `07a5fe36880d1548c9f42f2f6d071f46a9ac062f`
- Branch: `refactor/issue435-t5-switch-lifecycle-guards-20260920`
- Accepted TESTED_SHA: `94fe9251c99b41386c304c8cc97d89bcc3690dd5`

## Knowledge Preflight
- RUN `35498891860`
- JOB `106046943836`
- result: SUCCESS / `KNOWLEDGE_PREFLIGHT_RC=0`

## Characterization / intended RED

The first lifecycle run exposed two independent classes:
- four known stale #378 mousewheel tests that still modeled the retired `assembly_parts_canvas` seam;
- one T5 test-harness overreach around reopen active-part semantics.

The reopen test was corrected to use the canonical project snapshot. A second correction respected the accepted Fold Designer startup behavior: project payload preserves `active_part`, while entering 3D still starts in assembly/box_body and can restore the persisted part through the existing navigation owner.

Accepted intended RED RUN `35499647553`:
```text
30 PASS
4 intended FAIL
1 allowed SKIP
T5_INTENDED_RED=1
T5_RED_STALE_ISSUE378_COUNT=4
MOUSEWHEEL_RUNTIME_OWNER_PATH_GREEN=1
```

The four REDs were exactly the stale #378 owner-contract assertions. Runtime `Phase6AssemblyPanel.scroll()` was already GREEN.

## Test-contract migration

`tests/test_issue378_assembly_mousewheel.py` was migrated test-only to the accepted Phase 5 owner seam:
- `Phase6AssemblyPanel` is the sole scroll owner;
- bridge `_phase6_scroll_assembly_parts()` only delegates;
- Windows delta, Button-4, Button-5 and neutral-event directions remain covered;
- no second runtime scroll authority was added.

No production file changed.

## Focused GREEN

RUN `35499762496`, exact TESTED_SHA `94fe9251c99b41386c304c8cc97d89bcc3690dd5`:
```text
34 PASS
0 FAIL
1 allowed SKIP
PRODUCTION_RUNTIME_EDIT=0
PERMANENT_HIDDEN_SECOND_HOST=0
DUPLICATE_WIDGET_TREE=0
DUPLICATE_EVENT_BINDING=0
CALLBACK_MULTIPLICATION=0
STALE_WIDGET_REFERENCE=0
STATE_PRESERVATION_PARITY=GREEN
MOUSEWHEEL_EXCEPTION=0
```

The only allowed skip remains the current-family absence of resolved BoxBody physical child rows in #376.

Artifact:
- ID `10600739417`
- SHA256 `fc105b9204aac712a2397a2944f474e084636556b66dacc0e8949a55781647b2`

## Final A/B

The first A/B orchestration failed harness-only because common candidate tests copied onto the baseline worktree blocked the second checkout. The runner was corrected to reset/clean before each ref checkout; no product or test contract changed.

Accepted final A/B RUN `35499954029`:
```text
PRODUCTION_EXACT_PREDECESSOR=1
PRODUCTION_RUNTIME_EDIT=0
BASELINE_COUNTS {'passed': 34, 'skipped': 1}
CANDIDATE_COUNTS {'passed': 34, 'skipped': 1}
LIFECYCLE_AB_EXACT_OUTCOME_PARITY=1
LIFECYCLE_CANDIDATE_ONLY_FAILURES=0
CONFIG_INVARIANT=1
PERSIST_BASELINE_COUNTS {'passed': 4}
PERSIST_CANDIDATE_COUNTS {'passed': 4}
PROJECT_LOAD_SAVE_RELOAD_AB_EXACT_OUTCOME_PARITY=1
T5_AB_QUALIFICATION_GREEN=1
```

Artifacts:
- lifecycle A/B: ID `10601966140`, SHA256 `193104d45012d8cb04b8dd0b89ed2202ec4af589b29ad424e628220fa02e628a`
- persistence A/B: ID `10601064286`, SHA256 `8e32457905406919d1e34075d9db4d9c70a957b7ce605e6edf2d6cc3429e3898`

## Accepted conclusion

T5 is accepted with **zero production runtime edit**. The accepted implementation from #431–#434 already satisfies the switch-lifecycle contract; T5 added durable lifecycle guards and migrated the stale #378 test to the real panel-owner seam.

The closing commit may only:
- update this checkpoint / journal;
- remove temporary #435 QA workflows.

The two formal tests remain:
- `tests/test_issue435_switch_lifecycle_guards.py`
- `tests/test_issue378_assembly_mousewheel.py`

## State
```text
STATE=ACCEPTED
TESTED_SHA=94fe9251c99b41386c304c8cc97d89bcc3690dd5
FINAL_AB_RUN=35499954029
PRODUCTION_RUNTIME_EDIT=0
NEXT_ACTION=#436 / T6
```
