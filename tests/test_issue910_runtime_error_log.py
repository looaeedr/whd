from __future__ import annotations

import inspect

import gui
import gui_modules.application.lifecycle as lifecycle
from gui_modules.runtime_error_log import (
    SCHEMA,
    install_tk_exception_logging,
    write_runtime_exception,
)


def _raised_runtime_error():
    try:
        raise RuntimeError("3D startup exploded")
    except RuntimeError as exc:
        return exc, exc.__traceback__


def test_runtime_error_log_persists_context_message_and_traceback(tmp_path):
    path = tmp_path / "runtime_error.log"
    exc, tb = _raised_runtime_error()

    written = write_runtime_exception(
        "3d_designer_construction",
        exc,
        tb=tb,
        log_path=path,
        metadata={"build_id": "TEST_BUILD", "model": "受電箱"},
    )

    assert written == path
    text = path.read_text(encoding="utf-8")
    assert SCHEMA in text
    assert "context=3d_designer_construction" in text
    assert "exception_type=RuntimeError" in text
    assert "exception_message=3D startup exploded" in text
    assert "build_id=TEST_BUILD" in text
    assert "model=受電箱" in text
    assert "traceback:" in text
    assert "_raised_runtime_error" in text


def test_runtime_error_log_deduplicates_the_same_exception(tmp_path):
    path = tmp_path / "runtime_error.log"
    exc, tb = _raised_runtime_error()

    write_runtime_exception("first", exc, tb=tb, log_path=path)
    write_runtime_exception("second", exc, tb=tb, log_path=path)

    text = path.read_text(encoding="utf-8")
    assert text.count(SCHEMA) == 2  # one opening marker plus one END marker
    assert "context=first" in text
    assert "context=second" not in text


def test_tk_callback_hook_logs_and_preserves_previous_handler(tmp_path):
    path = tmp_path / "runtime_error.log"
    prior_calls = []

    class FakeRoot:
        def report_callback_exception(self, exc_type, exc, tb):
            prior_calls.append((exc_type, str(exc)))

    root = FakeRoot()
    install_tk_exception_logging(root, log_path=path, metadata={"build_id": "TEST"})
    exc, tb = _raised_runtime_error()

    root.report_callback_exception(type(exc), exc, tb)

    text = path.read_text(encoding="utf-8")
    assert "context=tk_callback" in text
    assert "3D startup exploded" in text
    assert prior_calls == [(RuntimeError, "3D startup exploded")]


def test_primary_startup_installs_tk_runtime_error_hook_before_app_creation():
    source = inspect.getsource(gui.main)
    assert "install_tk_exception_logging(" in source
    assert source.index("install_tk_exception_logging(") < source.index("Phase6PrimaryApplication(")
    assert "write_runtime_exception(" in source
    assert '"application_startup"' in source


def test_3d_designer_constructor_boundary_logs_before_reraising():
    source = inspect.getsource(lifecycle.open_original_fold_designer)
    assert "write_runtime_exception(" in source
    assert '"3d_designer_construction"' in source
    assert "designer_factory(" in source
