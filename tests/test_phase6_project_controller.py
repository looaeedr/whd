from pathlib import Path

import pytest

from phase6_project_controller import Phase6ProjectController


def make_controller(tmp_path=None):
    writes = []

    def read_project(path):
        return {"schema": "phase6-project/v1", "snapshot": {"w": 321.0, "existing_parts": ["box_body"]}}

    def write_project(path, payload):
        writes.append((str(path), payload))
        return Path(path)

    controller = Phase6ProjectController(
        read_project=read_project,
        write_project=write_project,
        schema="phase6-project/v1",
        clock=lambda: "2026-08-23T12:40:00+08:00",
    )
    return controller, writes


def provider_must_not_run():
    raise AssertionError("snapshot provider must not run while draft is active")


def test_active_draft_build_payload_uses_committed_without_calling_snapshot_provider():
    controller, _ = make_controller()
    controller.begin_designer(lambda: {
        "w": 400.0,
        "existing_parts": ["box_body", "head"],
        "workspace": {"existing_parts": ["box_body", "head"], "active_part": "box_body"},
    })

    payload = controller.build_payload(provider_must_not_run, active_part_hint="head")

    assert payload["snapshot"]["w"] == pytest.approx(400.0)
    assert payload["snapshot"]["active_part"] == "head"
    assert payload["snapshot"]["workspace"]["active_part"] == "head"
    assert payload["saved_at"] == "2026-08-23T12:40:00+08:00"
    assert payload["final_geometry"] == {}


def test_invalid_active_part_hint_cannot_change_committed_navigation():
    controller, _ = make_controller()
    payload = controller.build_payload(
        lambda: {
            "w": 400.0,
            "existing_parts": ["box_body", "head"],
            "active_part": "box_body",
            "workspace": {
                "existing_parts": ["box_body", "head"],
                "active_part": "box_body",
            },
        },
        active_part_hint="door",
    )

    assert payload["snapshot"]["active_part"] == "box_body"
    assert payload["snapshot"]["workspace"]["active_part"] == "box_body"


def test_load_replaces_old_draft_and_returns_payload_and_committed(tmp_path):
    controller, _ = make_controller(tmp_path)
    controller.begin_designer(lambda: {"w": 400.0, "existing_parts": ["box_body"]})
    assert controller.has_draft is True

    payload, committed = controller.load(tmp_path / "loaded.p6fold")

    assert payload["snapshot"]["w"] == pytest.approx(321.0)
    assert committed["w"] == pytest.approx(321.0)
    assert controller.has_draft is False
    assert controller.project_path == str(tmp_path / "loaded.p6fold")


def test_confirm_designer_commits_canonical_snapshot_once():
    controller, _ = make_controller()
    controller.begin_designer(lambda: {"w": 400.0, "existing_parts": ["box_body"]})

    committed = controller.confirm_designer({"w": 500.0, "existing_parts": ["box_body"]})

    assert committed["w"] == pytest.approx(500.0)
    assert controller.has_draft is False
    assert controller.committed_snapshot()["w"] == pytest.approx(500.0)


def test_gui_does_not_directly_call_project_file_read_write_or_session_ordering():
    source = Path("gui.py").read_text(encoding="utf-8")
    assert "read_phase6_project(" not in source
    assert "write_phase6_project(" not in source
    for call in (
        "project_session.capture_committed(",
        "project_session.begin_draft(",
        "project_session.commit_draft(",
        "project_session.cancel_draft(",
        "project_session.load_project(",
        "project_session.snapshot_for_save(",
    ):
        assert call not in source


def test_save_writes_payload_and_updates_project_path_only_after_success(tmp_path):
    controller, writes = make_controller(tmp_path)
    target = tmp_path / "ok.p6fold"

    saved = controller.save(
        target,
        lambda: {"w": 400.0, "existing_parts": ["box_body"]},
    )

    assert saved == str(target)
    assert controller.project_path == str(target)
    assert writes[0][0] == str(target)
    assert writes[0][1]["snapshot"]["w"] == pytest.approx(400.0)


def test_failed_save_does_not_change_project_path(tmp_path):
    def failing_write(path, payload):
        raise OSError("disk full")

    controller = Phase6ProjectController(
        read_project=lambda path: None,
        write_project=failing_write,
        schema="phase6-project/v1",
    )
    controller.set_project_path(tmp_path / "before.p6fold")

    with pytest.raises(OSError, match="disk full"):
        controller.save(
            tmp_path / "after.p6fold",
            lambda: {"w": 400.0, "existing_parts": ["box_body"]},
        )

    assert controller.project_path == str(tmp_path / "before.p6fold")
