from pathlib import Path


def _open_block():
    source = Path('gui.py').read_text(encoding='utf-8')
    start = source.index('    def open_original_fold_designer(self):')
    end = source.index('\n    def on_fw_selected', start)
    return source[start:end]


def test_window_x_flushes_live_canonical_state_then_closes_without_rollback():
    block = _open_block()
    start = block.index('        def close_designer():')
    end = block.index('        def load_project_from_designer', start)
    close = block[start:end]
    assert 'designer.flush_pending_settings()' in close
    assert 'designer._save_current_part(notify=False)' in close
    assert 'designer._phase6_publish_live_state(force=True)' in close
    assert 'destroy_designer_window()' in close
    assert 'cancel_designer' not in close
    assert 'project_session.cancel' not in close
    assert 'window.protocol("WM_DELETE_WINDOW", close_designer)' in block


def test_open_designer_has_no_deferred_confirm_apply_path():
    block = _open_block()
    assert 'def confirm_designer(' not in block
    assert 'after_idle' not in block
    assert '_apply_fold_designer_corner_transaction' not in block
    assert 'on_live_sync=lambda payload:' in block
