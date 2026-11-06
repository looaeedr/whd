"""#2517: Part Session commit failure cannot silently publish stale project bytes."""
from types import SimpleNamespace
import inspect

import pytest

from gui_modules.application import fold_designer_composition_state as composition
from phase6_project_controller import Phase6ProjectController


class ProjectSaveHost:
    def __init__(self, path, error):
        self.commits = []
        self.app = SimpleNamespace(
            _phase6_current_project_path=str(path),
            _phase6_pending_settings={},
            root=object(),
        )
        def save_part(*, notify=True):
            self.commits.append(notify)
            raise error
        self.app._save_current_part = save_part

    def _required(self, namespace, name):
        return namespace[name]

    def build_project_snapshot(self, namespace):
        return composition.build_project_snapshot(self, namespace)


@pytest.mark.parametrize("error", (
    ValueError("CURRENT_PART_FOLD_SOURCE_INVALID"),
    RuntimeError("CURRENT_PART_HOLE_SOURCE_INVALID"),
))
def test_project_snapshot_rejects_failed_live_part_before_reading_saved_workspace(tmp_path, error):
    host = ProjectSaveHost(tmp_path / "project.p6fold", error)
    with pytest.raises(type(error), match=str(error)):
        composition.build_project_snapshot(host, {})
    assert host.commits == [False]


@pytest.mark.parametrize("error", (
    ValueError("CURRENT_PART_FOLD_SOURCE_INVALID"),
    RuntimeError("CURRENT_PART_HOLE_SOURCE_INVALID"),
))
def test_existing_project_bytes_unchanged_on_failed_part_commit(tmp_path, monkeypatch, error):
    path = tmp_path / "existing.p6fold"
    original = b'{"schema":"phase6-fold-project-v1","source":"confirmed"}'
    path.write_bytes(original)
    host = ProjectSaveHost(path, error)
    errors = []
    monkeypatch.setattr(
        "tkinter.messagebox.showerror",
        lambda title, message, **kwargs: errors.append((title, message)),
    )
    monkeypatch.setattr(
        Phase6ProjectController, "write_designer_project",
        lambda *args, **kwargs: pytest.fail("stale physical source must not be written"),
    )
    project_file = SimpleNamespace(PROJECT_EXTENSION=".p6fold")
    result = composition.save_project_file(
        host, {"_phase6_project_file": project_file}, save_as=False,
    )
    assert result is None
    assert host.commits == [False]
    assert path.read_bytes() == original
    assert errors and errors[-1][0] == "存檔失敗"
    assert str(error) in errors[-1][1]


def test_gui_composition_does_not_suppress_current_part_commit_error():
    body = inspect.getsource(composition.build_project_snapshot)
    assert "app._save_current_part(notify=False)" in body
    assert "except Exception:\n        pass" not in body
