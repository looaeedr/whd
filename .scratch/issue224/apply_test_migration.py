from pathlib import Path

path = Path('tests/test_phase6_linked_fold_chain_and_parts.py')
text = path.read_text(encoding='utf-8')

old = '''def test_confirm_existing_parts_updates_main_2d_export_presence_flags():
    class Var:
        def __init__(self, value=True): self.value = value
        def set(self, value): self.value = bool(value)
        def get(self): return self.value

    from phase6_workspace_controller import Phase6WorkspaceController
    import gui
    dummy = SimpleNamespace(
        workspace_controller=Phase6WorkspaceController(),
        export_z_var=Var(True), export_head_var=Var(True), export_tail_var=Var(True),
        export_door_var=Var(True), export_base_plate_var=Var(True),
        is_indicator_box_var=Var(True), is_door_indicator_var=Var(False),
        _phase6_logical_part_present=gui.BoxCalculatorGUI._phase6_logical_part_present,
    )
    # This helper is intentionally GUI-light so commit/project-load share it.
    gui.BoxCalculatorGUI._apply_existing_parts_from_fold_workspace(
        dummy, ['box_body', 'head', 'door']
    )
    assert dummy.export_z_var.get() is True
    assert dummy.export_head_var.get() is True
    assert dummy.export_tail_var.get() is False
    assert dummy.export_door_var.get() is True
    assert dummy.export_base_plate_var.get() is False
    assert dummy.is_indicator_box_var.get() is False
'''

new = '''def test_confirm_existing_parts_preserves_main_2d_export_selection_intent():
    class Var:
        def __init__(self, value=True): self.value = value
        def set(self, value): self.value = bool(value)
        def get(self): return self.value

    from phase6_workspace_controller import Phase6WorkspaceController
    import gui
    dummy = SimpleNamespace(
        workspace_controller=Phase6WorkspaceController(),
        export_z_var=Var(True), export_head_var=Var(False), export_tail_var=Var(True),
        export_door_var=Var(False), export_base_plate_var=Var(True),
        is_indicator_box_var=Var(True), is_door_indicator_var=Var(False),
        _phase6_logical_part_present=gui.BoxCalculatorGUI._phase6_logical_part_present,
    )
    before = (
        dummy.export_z_var.get(), dummy.export_head_var.get(), dummy.export_tail_var.get(),
        dummy.export_door_var.get(), dummy.export_base_plate_var.get(),
    )
    gui.BoxCalculatorGUI._apply_existing_parts_from_fold_workspace(
        dummy, ['box_body', 'head', 'door']
    )
    after = (
        dummy.export_z_var.get(), dummy.export_head_var.get(), dummy.export_tail_var.get(),
        dummy.export_door_var.get(), dummy.export_base_plate_var.get(),
    )
    assert after == before
    assert dummy.is_indicator_box_var.get() is False
'''

if old not in text:
    if new in text:
        print('already_applied=1')
        raise SystemExit(0)
    raise SystemExit('stale test contract block not found exactly')

path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('applied=1')
