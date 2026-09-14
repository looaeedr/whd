# #210 / T6 TDD State

Role: `[當前角色：T6 實作者]`
Accepted parent: `e5c5d6cea1aae155b7110060e794fa865f7ac2ea`
Preflight/inventory GREEN: run `34833248521 @ 6645577465e114b00c4dbba6682c96573cee0c99`

## First Move-Only slice
Move only these `Phase6ApplicationHost` project-action wrappers to `gui_modules/project_actions.py`:
- `save_phase6_project_as`
- `save_phase6_project`
- `open_phase6_project`
- `load_phase6_project`

HOLD in `gui.py`:
- `_compose_phase6_project_snapshot_from_main_gui`
- `_phase6_loaded_project_path`
- `_apply_phase6_project_snapshot`
- `_make_original_fold_designer_snapshot`

Do not modify `Phase6ProjectController`, `ProjectSession`, `.p6fold` schema, or persistence ordering.

## RED provenance
- run `34835064768 @ 6f79e0cb2cde68ab2ac153ef96912dc9e54893fd` is **INVALID / HARNESS FAILURE**: Preflight GREEN, but pytest was not installed, so the structural test never collected.
- QA runner base commit `86eaee21cd2861bf7aea11189e450faa8760b0f2` adds only the missing pytest runner dependency.

Next expected evidence: a real structural TDD RED because `gui_modules/project_actions.py` does not yet exist and the four method bodies still live in `Phase6ApplicationHost`.