from pathlib import Path


def _open_block():
    source = Path('gui.py').read_text(encoding='utf-8')
    start = source.index('    def open_original_fold_designer(self):')
    end = source.index('\n    def on_fw_selected', start)
    return source[start:end]


def test_window_x_flushes_live_state_without_cancel_or_confirm_transaction():
    block = _open_block()
    assert 'window.protocol("WM_DELETE_WINDOW", close_designer)' in block
    assert 'on_live_sync=lambda payload:' in block
    assert 'on_transaction_confirm=' not in block
    assert 'on_transaction_cancel=' not in block
    assert 'begin_designer' not in block
    assert 'cancel_designer' not in block
    assert 'confirm_designer(payload)' not in block
    assert 'designer._phase6_publish_live_state(force=True)' in block
    assert 'export_phase6_snapshot()' not in block


def test_main_snapshot_supplies_baseline_choices_to_3d():
    source = Path('gui.py').read_text(encoding='utf-8')
    start = source.index('    def _make_original_fold_designer_snapshot(self):')
    end = source.index('\n    @staticmethod\n    def _fold_designer_number_text', start)
    block = source[start:end]
    assert 'snapshot["baseline_models"]' in block
    assert 'snapshot["baseline_unknown_value"]' in block


def test_open_3d_uses_live_canonical_callback_and_never_creates_project_draft():
    block = _open_block()
    assert 'on_settings_change=None' in block
    assert 'self.project_controller.capture_committed(designer_snapshot)' in block
    assert 'on_live_sync=lambda payload: self._apply_fold_designer_live_snapshot' in block
    assert 'begin_designer' not in block
    close_start = block.index('        def close_designer():')
    load_start = block.index('        def load_project_from_designer', close_start)
    close = block[close_start:load_start]
    assert 'designer.flush_pending_settings()' in close
    assert 'designer._save_current_part(notify=False)' in close
    assert 'designer._phase6_publish_live_state(force=True)' in close
    assert 'destroy_designer_window()' in close
    assert 'rollback' not in close.lower()


def test_live_snapshot_applies_settings_workspace_and_commits_one_canonical_state():
    source = Path('gui.py').read_text(encoding='utf-8')
    start = source.index('    def _apply_fold_designer_live_snapshot(self, payload):')
    end = source.index('\n    def _apply_fold_designer_corner_transaction', start)
    block = source[start:end]
    assert 'payload.get("settings")' in block
    assert '_apply_fold_designer_live_settings(settings, recalculate=False)' in block
    assert 'payload.get("workspace")' in block
    assert '_store_fold_designer_workspace(workspace)' in block
    assert 'self.assembly_relief_state = deepcopy(payload.get("assembly_relief") or {})' in block
    assert '_phase6_update_scheduler' in block
    assert '.mark_dirty(' in block
    assert 'self.update_calculations()' not in block
    assert 'self.project_controller.capture_committed(' in block
