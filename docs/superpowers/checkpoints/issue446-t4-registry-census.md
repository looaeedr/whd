# Issue #446 / T4 — Registry diagnostics presentation census

- Parent / Master: #441
- Issue: #446
- Role: T4 實作者
- Accepted predecessor / base: `cc2af5a40769d8897ecd81679bfcb81fa36e5599` (#445 cleaned accepted HEAD)
- Work branch: `refactor/issue446-t4-registry-diagnostics-owner-20260921`
- Preflight evidence: `docs/superpowers/checkpoints/issue446-t4-preflight-evidence.txt`
- Local checkout: blocked by runtime DNS; census performed against exact GitHub Git objects.

## Existing semantic/controller owner

`phase6_registry_diagnostics_controller.py::Phase6RegistryDiagnosticsController` already owns:
- candidate lifecycle and current-candidate checks;
- formula-matrix orchestration and regression evidence;
- promotion candidate routing;
- rule-record loading/lookup;
- Joint add/delete routing;
- diagnostic-id selection / selected diagnostic;
- presentation-ready diagnostic status text.

The controller must remain free of Tk and must not import `fold_designer_bridge.py`.

## True presentation seam in bridge

### Registry editor surface
Selected live Tk construction currently in `fold_designer_bridge.py`:
- `_phase6_form_choice`
- `_phase6_open_relief_registry_form`

Presentation refresh/population that belongs with the same surface:
- `_phase6_registry_refresh_rule_tree`
- `_phase6_registry_rule_selected`
- `_phase6_joint_form_refresh`
- `_phase6_registry_preview_2d` drawing only

The semantic callbacks invoked by the surface remain outside the panel:
- `_phase6_registry_validate_formula_form`
- `_phase6_registry_save_candidate_form`
- `_phase6_registry_run_formula_matrix`
- `_phase6_registry_preview_assembly_3d`
- `_phase6_registry_promote_form`
- `_phase6_joint_form_add`
- `_phase6_joint_form_delete`

### Assembly diagnostics surface
Selected live Tk construction currently in bridge:
- `_phase6_build_assembly_diagnostics`
- menu presentation portion of `_phase6_refresh_joint_diagnostic_menu`

Status semantics remain in controller / bridge callbacks:
- `Phase6RegistryDiagnosticsController.diagnostic_ids`
- `Phase6RegistryDiagnosticsController.diagnostic_status`
- `_phase6_on_assembly_diagnostic_changed`
- `_phase6_create_relief_promotion_candidates`

## Explicit exclusions / ownership boundary

The new/existing presentation owner MUST NOT own or reimplement:
- `ae_engine.certified_relief_registry` formula validation/evaluation;
- candidate save/promote semantics or trust-level rules;
- Certified Registry rule semantics;
- candidate-specific 3D manufacturing validation;
- canonical AssemblyJoint add/delete mutation;
- manufacturing geometry / collision / relief solving;
- compatibility mirrors as canonical state.

The panel may only own Tk variables/widgets, view formatting, row/menu rendering, 2D preview canvas drawing, and callback dispatch.

## Decision

`DECISION=EXTRACT`

Reason: both selected surfaces are live, user-visible Tk construction already routed through a non-Tk controller seam. Leaving them in the bridge preserves a clear ownership violation; this is not a zero-caller/dead-code case.

## RED acceptance direction

RED contracts must fail while:
1. selected Registry/diagnostics Tk constructors remain top-level in `fold_designer_bridge.py`;
2. no canonical `phase6_registry_diagnostics_panel.py` presentation owner exists;
3. controller/panel reverse-import invariants are not yet locked.

GREEN must prove:
- selected Registry Tk construction in bridge = 0;
- selected diagnostics Tk construction in bridge = 0;
- panel reverse import bridge = 0;
- controller reverse import bridge = 0;
- Certified Registry/promote/preview/Joint semantic owners stay outside panel;
- existing compatibility surface remains functional through explicit callbacks.

Next action: add focused RED ownership contracts before production extraction.
