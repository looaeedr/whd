# Issue #625 / A8 — P7-G Settings presentation Deletion-Test

Decision parent HEAD: `590448a911099d2bdb61aef09112dd6b6d3afc3c`

## Decision

**`KEEP_CURRENT_BOUNDARY`**

No production Settings implementation is changed by A8. The existing single `Phase6SettingsPanel` remains the presentation owner, `Phase6FoldDesignerComposition` remains the single construction/wiring root, and Settings transaction/state authority remains in the existing transaction/application owners.

## DT-0 — Current boundary

- `Phase6SettingsPanel` owns Tk/UI presentation and presentation-local state.
- Structure, Corner, EndCap FW and Bottom Wrap mutations enter through bounded callback ports.
- `fold_designer_bridge.py` retains the compatibility projection/dataflow seam.
- `phase6_settings_profile_projection.py` remains a pure owner and may not gain bridge/Tk/workspace/manufacturing dependencies.
- No second Settings panel/state machine or second composition root is permitted.

## DT-1 — Remove / inline

**KEEP_REQUIRED.** The scoped projection bodies are live. Deleting them removes current presentation dataflow; inlining the domain-heavy box/corner projections into the panel would transfer domain dependencies into a presentation-only owner.

## DT-2 — Existing-owner candidate

The current architecture was rechecked after the Phase 7/A7 composition changes:

- Panel: legal presentation owner, illegal domain-projection service bag.
- Composition root: legal wiring owner, illegal deep domain-projection implementation owner.
- Pure profile projection: legal pure planner, illegal bridge/domain callback bag.

There is therefore **no legal deep destination for the group**.

## DT-3 — Bounded ports

The current boundary is already bounded through:

- `context_extension_projection` / `sync_context_extension`;
- EndCap FW selection;
- Box structure numeric/back-panel/advanced controls;
- Bottom Wrap commit;
- Corner pair/type/mode/target callbacks.

Canonical Settings mutation/state authority is unchanged.

## DT-4 — Variant K

Variant K = **KEEP_CURRENT_BOUNDARY / GREEN**.

The accepted #528 formal Deletion-Test remains directly relevant:

- RUN `35783860498`;
- exact-six total span: **277 LOC**;
- distinct bridge/domain helper dependencies: **16**;
- Settings owner suite: **26 passed / 6 skipped**;
- Xvfb panel suite: **11 passed**.

Fresh Phase 7 readback found all six scoped compatibility bodies and all structure/corner/endcap mutation delegates source-identical to that accepted lineage. `phase6_settings_panel.py` and `phase6_settings_profile_projection.py` owner constraints are unchanged.

## DT-5 — Variant E

Variant E = **DEEPEN_EXISTING_OWNER / REJECTED**.

The prior disposable extraction removed only **1 / 6** bodies and left **5 duplicate paths**. The remaining bodies still depend on **16** bridge/domain helpers. Moving them into the panel breaks presentation purity; moving them into the pure projection owner creates a service bag; moving them into composition mixes wiring with domain projection implementation.

## DT-6 — Terminal decision

`KEEP_CURRENT_BOUNDARY`.

Focused P7-R-G expected-RED run `36273585335` completed successfully as a RED harness with exactly **3 passed / 1 failed**. The sole failure was `test_p7_r_g_requires_terminal_deletion_test_decision`, because DT-6 was still `PENDING`. No other P7-G invariant failed.

The next gate is fresh GREEN + Xvfb/settings behavior verification against this terminal DT artifact.
