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
- run `34835064768 @ 6f79e0cb2cde68ab2ac153ef96912dc9e54893fd` is **INVALID / HARNESS FAILURE**: pytest was not installed, so the structural test never collected.
- run `34835211280 @ b83cd019a0ed91ed5bab7d5091a2ad5b5ebc175b` is the **VALID TDD RED**: Preflight GREEN, test collected, exactly 3 structural assertions failed for the intended missing extraction.

## GREEN candidate
- one-shot AST Move-Only applicator run `34835482565` completed SUCCESS.
- code commit: `d820890a9ff6c22b5af31fc5b495ce87a2826c03` (`refactor(issue210): move global project action wrappers`).
- immediate checks on that bot-pushed commit are **not acceptance evidence** because GitHub reported `action_required`; this evidence-only commit exists solely to retrigger normal exact-head validation through a connector-authored push.

Next action: validate the same code blobs on the new exact head. The only intended difference after `d820890a...` is this durable TDD state update.