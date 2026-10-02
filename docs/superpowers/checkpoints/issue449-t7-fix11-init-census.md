# Issue #449 / T7 — `_fix11_init` bootstrap-only lifecycle census

- Parent / Master: #441
- Issue: #449
- Role: T7 實作者
- Accepted predecessor / base: `41bf313b9389a7e98f9978c36b96380c237e57ec`
- Work branch: `refactor/issue449-t7-fix11-init-bootstrap-20260921`
- Current X observation only: `acdfcfc66a46940798bff77df4b8e32bfc10b7ca`
- Preflight evidence: `docs/superpowers/checkpoints/issue449-t7-preflight-evidence.txt`

## Accepted owner inputs

T7 runs only after the prior ownership decisions are accepted:

- T2 / #444: `phase6_bending_ui.py::Phase6BendingUI` is the Bending UI implementation owner.
- T3 / #445: `phase6_settings_panel.py::Phase6SettingsPanel` is the Settings presentation owner.
- T4 / #446: `phase6_registry_diagnostics_panel.py` + controller own Registry diagnostics presentation/semantics split.
- T5 / #447: Workspace Shell decision is `NO_EXTRACTION`; persistent top area remains bridge composition, but no second shell owner may be invented.
- T6 / #448: Part Editor decision is `C_KEEP_BRIDGE_COMPATIBILITY`; bridge keeps application-level compatibility/composition, but state/navigation/update/persistence owners remain external.

## Current `_fix11_init` responsibility census

Current span: **307 lines**. Line count is evidence only; it is not the DoD.

### A. Correct lifecycle/bootstrap responsibilities that may remain in `_fix11_init`

1. Set lifecycle to INITIALIZING before predecessor construction can emit callbacks.
2. Establish authoritative mutable mapping identities before callbacks can resolve them.
3. Invoke narrow bootstrap/install helpers in a deterministic order.
4. Invoke predecessor `_FIX10_INIT`.
5. Preserve legacy host compatibility requirements.
6. Select the initial user-visible mode.
7. Transition INITIALIZING → READY only after all owners are installed and state is seeded.

### B. Responsibilities currently inlined but not lifecycle-root implementation

These must leave the body of `_fix11_init`, while their existing authority remains unchanged:

1. **Snapshot/workspace data preparation**
   - part presence/active normalization;
   - copied features / face-features / assembly-placement payload;
   - `Phase6DesignerWorkspace.from_snapshot(...)`;
   - initial dimensions/settings/corner/endcap/baseline compatibility fields.

2. **Callback / compatibility port installation**
   - settings/live-sync/transaction/baseline/scene/part-spec/project/output callbacks;
   - compatibility state flags and guards;
   - text-scale controller bootstrap.

3. **Legacy inherited-host compatibility**
   - inherited preview suppression/restore;
   - original mode/global/visual control hiding;
   - old notebook/HolesUI compatibility hiding;
   - window title and compatibility fields.

4. **Workspace profile bootstrap**
   - saved profile reload;
   - EndCap order normalization;
   - default profile materialization;
   - linked EndCap rebuild;
   - authoritative derived-part sync.

5. **Part Editor compatibility presentation**
   - selector/menu/action row;
   - hidden Structure Tree compatibility projection;
   - hidden multipart Notebook compatibility projection;
   - direct shared-content host creation;
   - `Phase6BendingUI` owner construction;
   - `Phase6AssemblyPanel` owner construction and alias installation.

6. **Owner-view installation**
   - persistent top area;
   - content switch;
   - settings center;
   - final-scene renderer/view installation.

7. **Initial mode / ready-state seeding**
   - initial `box_body` activation;
   - initial assembly display;
   - workspace mark-clean;
   - live fingerprint seed;
   - lifecycle READY transition.

## Required implementation shape

`_fix11_init` remains the **single composition/lifecycle root**. T7 must not introduce a second root class or a new `phase6_workspace_shell.py` / `phase6_part_editor_session.py`.

The root may call narrow bridge-local bootstrap/install helpers. Those helpers are implementation-detail adapters, not new semantic owners. They must preserve the accepted external owners above.

Target lifecycle sequence:

1. enter INITIALIZING;
2. bootstrap authoritative mapping identities/state;
3. install callback/compatibility ports;
4. install predecessor-call adapters needed during legacy construction;
5. call `_FIX10_INIT`;
6. finish legacy-host compatibility setup;
7. bootstrap authoritative workspace/profile data;
8. install accepted presentation owners in one deterministic order;
9. select initial single/assembly mode through existing routes;
10. seed live-state fingerprint;
11. mark workspace clean;
12. transition to READY.

## Prohibited deep-owner construction in `_fix11_init` body

The root body must not directly construct or implement:

- `Phase6BendingUI`;
- `Phase6AssemblyPanel`;
- `Phase6DesignerWorkspace.from_snapshot`;
- Settings deep widgets / `Phase6SettingsPanel`;
- FinalScene deep view/renderer objects;
- Registry diagnostics deep presentation;
- raw selector / Treeview / shared-content Tk widget trees.

Those belong behind the accepted owner/bootstrap adapters.

## No second composition root

Machine evidence must prove:

- exactly one call site of `_FIX10_INIT`, inside `_fix11_init`;
- no new bootstrap class/session/shell becomes an alternate lifecycle root;
- helper installers are only invoked from `_fix11_init` for initial owner installation;
- runtime feature callbacks continue to use existing owners rather than the bootstrap helper layer.

## Accepted T4/T5/T6 state must remain unchanged

- Registry decision: extracted presentation owner, no bridge re-absorption.
- Shell decision: `NO_EXTRACTION`; no `phase6_workspace_shell.py`.
- Part Editor decision: `C_KEEP_BRIDGE_COMPATIBILITY`; no `phase6_part_editor_session.py`.
- shared-content physical-slot contract stays direct-sibling / exactly-one-active.
- no product geometry, dataflow, project persistence, Registry rule, physical-part identity, or update-intent semantics move.

## RED acceptance direction

Focused RED contract must fail on the current base because `_fix11_init` still directly contains:

- `Phase6DesignerWorkspace.from_snapshot`;
- `Phase6BendingUI(...)`;
- `Phase6AssemblyPanel(...)`;
- direct `ttk.Frame/StringVar/Treeview/Notebook` construction for Part Editor compatibility surfaces;
- profile reload/materialization loops and live-fingerprint details.

GREEN is semantic, not a line threshold:

- `FIX11_INIT_IS_BOOTSTRAP_ONLY=1`;
- only lifecycle/bootstrap/install-order operations remain in `_fix11_init`;
- deep owner construction tokens above absent from the root body;
- no second composition root;
- accepted T2–T6 owners unchanged;
- geometry/dataflow/persistence semantic drift = 0.

Next action: add `tests/test_issue449_fix11_init_bootstrap_owner.py`, confirm expected RED, then refactor vertical slices.
