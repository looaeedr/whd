# Issue #625 / A8 — P7-G Settings presentation DT-0 census

Characterization head: `10ec9a52eff1b8495042270445755e59b6a329c2`

## Existing owner boundary

`phase6_settings_panel.py` explicitly owns Tk/UI presentation only. Settings draft, mechanical semantics, and transaction authority remain outside the panel and enter through callback ports.

The A8 deletion-test scope is the existing structure/corner/endcap presentation cluster already exposed on `Phase6SettingsPanel`: endcap FW selection, box-structure numeric/back-panel/advanced callbacks, bottom-wrap commit, corner pair/type/mode/target callbacks, baseline/global settings presentation, and context-extension render/sync/projection ports.

## DT-0 census

- Direct owner: `Phase6SettingsPanel`.
- Schema/context owner: `phase6_settings_center`.
- Mutation boundary: `stage_setting_update`, `flush_settings`, `save_defaults`, and explicit structure/corner/endcap callback ports supplied by composition.
- Presentation-local state: Tk variables, page cache, current page/context, render/guard flags.
- Protected invariant: no second Settings state machine/panel owner; transaction/state authority stays outside presentation.
- Candidate existing owner for deepening: the existing Settings panel/composition boundary only. No new shallow coordinator is authorized.

## P7-R-G RED

The focused RED requires DT-6 to become terminal using exactly one canonical enum: `DEEPEN_EXISTING_OWNER` or `KEEP_CURRENT_BOUNDARY`. At DT-0 this is intentionally unresolved, so the RED must fail until DT-1..DT-5 provide evidence for one branch.

No production behavior is changed by this characterization commit.
