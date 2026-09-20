# Phase 5 / Issue #427 T6 Journal

## Authority

- MASTER_ID: `#413`
- TASK_ID: `#427 / T6`
- TARGET_X: `cleanup/2d-3d-sync`
- PHASE5_ACCEPTED_ROOT / A-B BASELINE: `396bfd96524a44a178c29bbefaf1b7c0437c119f`
- T5_ACCEPTED_SHA / A-B CANDIDATE: `06f23d44ad29d5e2fe9a0a82d71ec48ce1416980`
- WORK_ORDER_BRANCH: `refactor/issue413-phase5-assembly-presentation-20260920`
- Requirement Authority: Phase 5 v1.7 accepted master #413

## Fresh production target readback

Before T6 harness write:
```text
cleanup/2d-3d-sync == 396bfd96524a44a178c29bbefaf1b7c0437c119f
ahead_by=0
behind_by=0
status=identical
```

No target drift exists at T6 start.

## Knowledge Preflight

Exact T6 changed-file route:
```text
tools/phase5_t6_classifier.py
.github/workflows/qa-issue427-phase5-t6.yml
docs/superpowers/checkpoints/issue427-phase5-t6-journal.md
```

Router result:
```text
REQUIRED_SKILLS=9
REQUIRED_REFERENCES=8
KNOWLEDGE_PREFLIGHT_RC=0
```

READ_SKILL: 派工
READ_SKILL: issue-closure-gate
READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: phase6-release-packaging
READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_SKILL: executable-continuity-controller
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: release_required_artifacts.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md

SUPPORTING_REFERENCE_READ_BEFORE_CLOSURE:
- 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md

## Accepted Phase 5 lineage

| Task | Accepted closing SHA | Final RUN |
|---|---|---:|
| T0 / #421 | `b31409e7c1736df31bd554afe4ac779d49b30aaa` | 35486472231 |
| T1 / #422 | `cb7ae0d906e52d286e740e5c8fb984c40728be83` | 35487073574 |
| T2 / #423 | `b3d798c1a1d8ec3ad690948bee833d7c174df122` | 35487882048 |
| T3 / #424 | `35641caa9abe5927766135ee5e5621bfce1cf775` | 35488530162 |
| T4 / #425 | `5581b091cd891bd725577dfc60376cf35bc13e63` | 35489448163 |
| T5 / #426 | `06f23d44ad29d5e2fe9a0a82d71ec48ce1416980` | 35490168585 |

## Candidate changed-file inventory before T6

PR #428 at T5 accepted candidate contains production changes only in:
- `fold_designer_bridge.py`
- `phase6_assembly_panel.py`
- `phase6_assembly_presentation.py`

All other Phase 5 branch changes are tests/workflows/evidence/tooling.

T6 protected-drift gate therefore fails closed if any other production path differs between baseline and candidate.

## T6 execution design

### Cumulative focused/static lane
- rerun T0 baseline census against the exact accepted root;
- run T1–T5 permanent focused contracts against exact candidate under Xvfb;
- run protected-owner/hash/static classifier;
- preserve right-side diagnostics exact-source parity;
- enforce config.ini / 基準檔 / project/manufacturing/final-scene protected drift.

### Full A/B lanes
Four independent exact-SHA jobs:
1. baseline Headless
2. candidate Headless
3. baseline Xvfb
4. candidate Xvfb

Each lane:
- installs the same runtime/test dependencies;
- runs full pytest;
- always emits JUnit XML even when inherited failures exist;
- does not classify its own non-zero pytest exit as Phase 5 failure.

Final classifier compares testcase identities:
- candidate failures minus baseline failures;
- candidate errors minus baseline errors;
- no baseline substitution;
- extra candidate tests are permitted only when they pass/skip.

Required:
```text
NEW_HEADLESS=[]
NEW_XVFB=[]
NEW_HEADLESS_ERRORS=[]
NEW_XVFB_ERRORS=[]
CANDIDATE_ONLY_FAILURES=0
CANDIDATE_ONLY_ERRORS=0
PHASE5_DECISION=GREEN
```

## Integration boundary

No integration is permitted by harness creation or by any non-terminal T6 result.

Only after T6 GREEN:
1. fresh-read production;
2. target drift audit;
3. exact tested candidate ancestry;
4. remove temporary QA workflows/probes;
5. prove production-code blobs remain the tested candidate blobs;
6. non-force integration;
7. no untested conflict resolution;
8. exact production readback;
9. post-merge focused Assembly/Xvfb smoke;
10. protected-owner scan;
11. exact closing proof.

## State

```text
STATE=PREPARING_T6
BASELINE=396bfd96524a44a178c29bbefaf1b7c0437c119f
CANDIDATE=06f23d44ad29d5e2fe9a0a82d71ec48ce1416980
RUN_ID=RUN_NOT_CREATED
NEXT_ACTION=Create cumulative static/JUnit classifier and four-lane fixed-root A/B workflow.
```


## T6 Static Classifier Harness Recovery

First T6 RUN `35491085695` @ harness HEAD `f1ea8904f0a0a5149da3c472f7fc8a764b05a217` reached:
- fixed production target readback GREEN;
- Knowledge Preflight GREEN;
- exact T0 census GREEN;
- all static Phase 5 gates GREEN except `PROTECTED_DRIFT=1`.

Artifact `issue427-phase5-t6-cumulative` proved the sole static failure was a harness-only Unicode path bug:
- `git ls-tree` quoted `基準檔/**` paths as octal escapes;
- classifier then passed those quoted literal strings back to `git show`;
- every reference-tree file was therefore falsely reported as drift.

Independent markers from the same static report already showed:
```text
PROTECTED_OWNER_BLOB_PARITY=1
CONFIG_BLOB_PARITY=1
DXF_DRIFT=0
GEOMETRY_DRIFT=0
PROJECT_SCHEMA_DRIFT=0
RIGHT_DIAGNOSTICS_PARITY=GREEN
```

Correction:
- classifier now uses `git -c core.quotePath=false ls-tree ...` for Unicode reference-tree paths;
- fix commit: `e228abeb453e662c40f0822db812c4f2788a9ec2`;
- BASELINE remains `396bfd96524a44a178c29bbefaf1b7c0437c119f`;
- CANDIDATE remains `06f23d44ad29d5e2fe9a0a82d71ec48ce1416980`;
- no candidate production file changed.

RUN `35491085695` is therefore classified as **STATIC_CLASSIFIER_HARNESS_FALSE_POSITIVE**, not Phase 5 product drift.


## Final T6 GREEN / Cleanup Evidence

Final normalized common-test A/B:
- harness HEAD: `08ee15e13642f861a58e78e8bff60c9721a103c1`
- RUN: `35491897110` — **SUCCESS**
- BASELINE: `396bfd96524a44a178c29bbefaf1b7c0437c119f`
- CANDIDATE: `06f23d44ad29d5e2fe9a0a82d71ec48ce1416980`

Headless:
```text
baseline: 5 failed / 2615 passed / 427 skipped
candidate: 5 failed / 2615 passed / 427 skipped
NEW_HEADLESS=[]
NEW_HEADLESS_ERRORS=[]
```

Xvfb:
```text
baseline: 42 failed / 3004 passed / 1 skipped
candidate: 42 failed / 3004 passed / 1 skipped
NEW_XVFB=[]
NEW_XVFB_ERRORS=[]
```

Final classifier:
```text
CANDIDATE_ONLY_FAILURES=0
CANDIDATE_ONLY_ERRORS=0
PHASE5_DECISION=GREEN
```

Cumulative static/focused:
- `BOUNDARY_CENSUS_REPRODUCIBLE=1`
- `MOUNT_UNMOUNT_CENSUS_COMPLETE=1`
- `LEGACY_ATTRIBUTE_READER_CENSUS_COMPLETE=1`
- `PROTECTED_OWNER_MANIFEST_COMPLETE=1`
- `NEW_NON_TK_VISIBILITY_STORE=0`
- `VISIBILITY_STATE_DUPLICATION=0`
- `BOX_PIECE_ROW_SOURCE_RENDER_DATA_PIECES=True`
- `BOX_PIECE_KEY_SET_FORCED_EQUALIZATION=0`
- `VISIBILITY_CHANGE_RENDER_ONLY_IN_ASSEMBLY_MODE=True`
- `PANEL_READS_DISPLAY_MODE=0`
- `VISIBILITY_RENDER_MODE_GATE_OWNED_BY_ACTION_TARGET=True`
- `FINAL_SCENE_ASSEMBLY_QUERY_ORDER_PARITY=GREEN`
- `VISIBLE_BOX_BODY_PIECE_TRISTATE_PARITY=GREEN`
- Structure Tree empty/repopulated parity GREEN
- refresh/mount/unmount parity GREEN
- legacy alias parity GREEN; stale reference count 0
- `GEOMETRY_DRIFT=0`
- `DXF_DRIFT=0`
- `PROJECT_SCHEMA_DRIFT=0`
- `PROTECTED_DRIFT=0`
- `RIGHT_DIAGNOSTICS_PARITY=GREEN`
- focused cumulative contracts: `65 passed / 1 deselected`

Evidence artifacts:
- final classifier artifact `10599367255`, digest `sha256:9aee8aaf78e6b5e4cccd4ae424ac3f2cb3e72e9cf9af12f0d37dc540e57d5be9`
- Headless baseline `10599073759`, digest `sha256:c36a346d57fc28d6070244d12fdb64deca9883a7d5774d648c7fbd3f044373b2`
- Headless candidate `10599282219`, digest `sha256:e7c5c1716850e59ca122ba1c1128eeff81db82f4d11cf50b9f375bbe0f925548`
- Xvfb baseline `10599866267`, digest `sha256:59ce48542b7ded30e66f9dac3b315c83dde77f27cbc1f300585936fcc328e216`
- Xvfb candidate `10599119775`, digest `sha256:d716c519242b404309b069784e8a7d3dd2ab0f7af8b42a47db42dc63bc030db0`

### Temporary QA cleanup

After classifier GREEN, T6 removed only temporary Phase 5 QA harness/probes:
- `.github/workflows/qa-issue421-phase5-t0.yml`
- `.github/workflows/qa-issue422-phase5-t1.yml`
- `.github/workflows/qa-issue423-phase5-t2.yml`
- `.github/workflows/qa-issue424-phase5-t3.yml`
- `.github/workflows/qa-issue425-phase5-t4.yml`
- `.github/workflows/qa-issue426-phase5-t5.yml`
- `.github/workflows/qa-issue427-phase5-t6.yml`
- `tools/phase5_t0_assembly_presentation_census.py`
- `tools/phase5_t6_classifier.py`

Permanent regressions under `tests/**`, all T0–T6 journals/checkpoints, and production files are retained.

Cleanup changed-file Preflight route:
```text
REQUIRED_SKILLS=8
REQUIRED_REFERENCES=7
KNOWLEDGE_PREFLIGHT_RC=0
```

### Integration state

```text
STATE=CLEANUP_COMPLETE_PENDING_INTEGRATION
BASELINE=396bfd96524a44a178c29bbefaf1b7c0437c119f
CANDIDATE=06f23d44ad29d5e2fe9a0a82d71ec48ce1416980
T6_HARNESS_HEAD=08ee15e13642f861a58e78e8bff60c9721a103c1
RUN_ID=35491897110
PHASE5_DECISION=GREEN
NEXT_ACTION=Prove cleanup-head production blobs equal tested candidate, fresh-read production target, then non-force integrate.
```


## Production Integration / Post-Merge Smoke

### Non-force integration

Production target `cleanup/2d-3d-sync` was fresh-read immediately before integration and remained exactly:
`396bfd96524a44a178c29bbefaf1b7c0437c119f`.

Cleanup head before integration:
`246578f815f4edfe273d1d5b6b443254ccfd6fa3`.

Production-code blob parity against tested T5 candidate `06f23d44...`:
- `fold_designer_bridge.py`: `fdc0b6053575257d3ee60f86aed5ea2340205bd2` — unchanged
- `phase6_assembly_panel.py`: `3ffea0709dd0c692816c59c2232f06710f2be885` — unchanged
- `phase6_assembly_presentation.py`: `b460bbbb819d4d6639f438fe63e866e21f71789e` — unchanged

Integration:
```text
FORCE_PUSH=0
BASELINE_SUBSTITUTION=0
UNTESTED_CONFLICT_RESOLUTION=0
TARGET_X=cleanup/2d-3d-sync
INTEGRATION_SHA=246578f815f4edfe273d1d5b6b443254ccfd6fa3
NON_FORCE_FAST_FORWARD=1
```

Exact production readback after integration:
- target SHA == `246578f815f4edfe273d1d5b6b443254ccfd6fa3`
- ahead/behind vs integration SHA = `0/0`
- tested candidate `06f23d44...` is an ancestor of production.

PR #428 was consequently reported by GitHub as merged/closed at the exact fast-forward integration SHA.

### Post-merge focused Assembly/Xvfb smoke

A one-shot **non-merge** smoke carrier PR #437 was used only to obtain observable remote-QA execution. Its workflow explicitly checked out and tested exact production SHA:
`246578f815f4edfe273d1d5b6b443254ccfd6fa3`.

RUN `35493064085` / job `106031202384`: **SUCCESS**

```text
POST_MERGE_PRODUCTION_SHA_EXACT=1
POST_MERGE_PRODUCTION_SHA=246578f815f4edfe273d1d5b6b443254ccfd6fa3
POST_MERGE_ASSEMBLY_XVFB_SMOKE=GREEN
CONFIG_INVARIANT=GREEN
86 passed / 1 skipped / 1 deselected
```

Smoke artifact:
- artifact `10600330315`
- digest `sha256:ecec143168437235fe21ae25d6280e0495ae50f558a37f8e453a7febcdab8303`

The one-shot smoke workflow was then deleted from the work-order branch and PR #437 was closed **without merge**. Production never contained that smoke workflow.

### Closing state

```text
STATE=POSTMERGE_SMOKE_GREEN_PENDING_FINALIZATION
PHASE5_DECISION=GREEN
INTEGRATION_SHA=246578f815f4edfe273d1d5b6b443254ccfd6fa3
POST_MERGE_RUN_ID=35493064085
NEXT_ACTION=Fast-forward journal-only closing writeback, verify protected-owner drift zero, then produce exact-head finalization proof and close #427/#413.
```
