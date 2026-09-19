---
whd_doc_role: REFERENCE
whd_contract: issue364-phase3-preflight
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #364 / Phase 3 T0 — Bridge ownership / dependency / timing preflight

## Identity

- Master: #363
- Task: #364 / T0
- Fixed Phase 3 root baseline: \`0dd6561f3253d0a17714af316d5e9da90e24058f\`
- Branch: \`refactor/issue364-phase3-preflight-20260919\`
- Accepted validated candidate: \`ca4c4ebfe63354d4f5c90b15b0f675b4bfa346ae\`
- Final QA RUN: \`35426467279\`
- Final QA job: \`105853188030\`
- Evidence artifact: \`issue364-phase3-preflight\` / artifact \`10578368911\`
- Nature: read-only characterization / inventory
- Production integration: not required for T0
- Status: **ACCEPTED**

No production behavior source changed in T0.

## Baseline failure evidence

Frozen from accepted Phase 2 final candidate at the exact same baseline SHA:

~~~text
SOURCE_RUN = 35423014088
HEADLESS_FAILED_NODE_SET = 6
HEADLESS_ERROR_NODE_SET = 0
XVFB_FAILED_NODE_SET = 47
XVFB_ERROR_NODE_SET = 0
~~~

The exact node IDs are embedded in the machine artifact.

## Bridge census

~~~text
BRIDGE_LINES = 9148
TOP_LEVEL_FUNCTIONS = 304
~~~

Responsibility groups:

~~~text
2d = 21
3d = 14
compatibility = 86
lifecycle = 22
manufacturing = 7
project = 21
registry = 32
settings = 76
workspace = 25
~~~

Structural classifications:

~~~text
COMPATIBILITY_FACADE = 28
COMPOSITION = 36
CONTROLLER_OWNER = 89
DOMAIN_DELEGATE = 29
VIEW_ADAPTER_OWNER = 122
UNKNOWN = 0
~~~

## State / callback / wiring inventory

~~~text
direct self-read attributes across top-level functions = 915
direct self-write attributes across top-level functions = 351
callback/event/provider references = 162
Phase6FoldDesignerApp class/property wiring rows = 70

UNKNOWN_CALLBACKS = 0
UNKNOWN_STATE_WRITES = 0
UNKNOWN_CLASS_WIRING = 0
~~~

The class-wiring gate explicitly handles both direct function assignment and property-factory wiring, including:

- \`_phase6_view_property(...)\`
- \`property(_legacy_*_get, _legacy_*_set)\`

so property wiring is classified instead of silently ignored.

## Transitive dependency / Tk reentrancy inventory

Machine closure from all 304 bridge roots reaches:

~~~text
REACHABLE_TRANSITIVE_FUNCTIONS = 680
~~~

After separating mapping \`.update()\` calls from actual Tk pumping:

~~~text
TRUE_TK_EVENT_LOOP_PUMPS = 3
SCHEDULED_AFTER_CALLBACKS = 8
BIND_TRACE_EVENT_DISPATCH = 41
DATA_MAPPING_UPDATE_NOT_TK = 66
UNMAPPED_EVENT_LOOP_PATHS = 0
~~~

The three confirmed Tk pumps are:

1. \`fold_designer_bridge:_fix11_activate_part\` line 8658
   - \`self.root.update_idletasks()\`
2. \`fold_designer_bridge:_fix11_activate_part\` line 8674
   - \`self.root.update_idletasks()\`
3. \`fold_designer_bridge:_phase6_update_left_workspace_width\` line 4250
   - \`canvas.update_idletasks()\`

Important Phase 3 implication:

> Unlike the Phase 2 manufacturing solve path, the full bridge does contain real Tk reentrancy/timing points. T1–T7 extraction must preserve the characterized ordering for the owning slice.

## Protected-source manifest

The machine gate froze SHA-256 for 16 protected/critical entries, including:

- \`config.ini\`
- Phase 2 manufacturing adapter/contracts/cache/service/geometry
- canonical DXF baseline files

~~~text
PROTECTED_MANIFEST_ENTRIES = 16
IMPLEMENTATION_SOURCE_DRIFT = 0
~~~

Only these T0 evidence paths differ from the root baseline:

~~~text
.github/workflows/qa-issue364-t0-phase3-preflight.yml
docs/superpowers/checkpoints/issue364-t0-phase3-preflight.md
tools/issue364_phase3_preflight.py
~~~

## Final machine gate

RUN \`35426467279\`:

~~~text
PASS BASELINE_ANCESTRY=1
PASS BRIDGE_LINES=9148
PASS TOP_LEVEL_FUNCTIONS=304
PASS UNKNOWN_FUNCTIONS=0
PASS UNKNOWN_CALLBACKS=0
PASS UNKNOWN_STATE_WRITES=0
PASS UNKNOWN_CLASS_WIRING=0
PASS UNMAPPED_EVENT_LOOP_PATHS=0
PASS IMPLEMENTATION_SOURCE_DRIFT=0
PASS BASELINE_HEADLESS_FAILED_NODE_SET=6
PASS BASELINE_HEADLESS_ERROR_NODE_SET=0
PASS BASELINE_XVFB_FAILED_NODE_SET=47
PASS BASELINE_XVFB_ERROR_NODE_SET=0
~~~

## Acceptance

#364 / T0 is **ACCEPTED**.

Next allowed task:

> #365 / T1 — Workspace / Navigation state-owner extraction

T1 fixed task baseline remains the Phase 3 root production SHA:

\`0dd6561f3253d0a17714af316d5e9da90e24058f\`
