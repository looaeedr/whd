# -*- coding: utf-8 -*-
import pytest

from phase6_project_session import ProjectSession


def test_cancel_draft_keeps_committed_snapshot_isolated_from_external_mutation():
    session = ProjectSession()
    source = {"w": 400.0, "workspace": {"existing_parts": ["box_body", "head"]}}

    committed = session.capture_committed(source)
    source["w"] = 999.0
    committed["workspace"]["existing_parts"].append("tail")

    draft = session.begin_draft()
    draft["w"] = 500.0
    draft["workspace"]["existing_parts"].append("door")
    cancelled = session.cancel_draft()

    assert cancelled["w"] == pytest.approx(400.0)
    assert cancelled["workspace"]["existing_parts"] == ["box_body", "head"]
    assert session.committed_snapshot() == cancelled
    assert session.draft_snapshot() is None
    assert session.has_draft is False


def test_commit_draft_replaces_committed_but_save_reads_only_committed_until_commit():
    session = ProjectSession()
    session.capture_committed({"w": 400.0})
    session.begin_draft()
    session.replace_draft({"w": 500.0})

    assert session.snapshot_for_save()["w"] == pytest.approx(400.0)

    committed = session.commit_draft()

    assert committed["w"] == pytest.approx(500.0)
    assert session.snapshot_for_save()["w"] == pytest.approx(500.0)
    assert session.has_draft is False


def test_load_project_sets_immutable_baseline_committed_and_path_and_replaces_old_draft(tmp_path):
    session = ProjectSession()
    session.capture_committed({"w": 300.0})
    session.begin_draft()
    session.replace_draft({"w": 350.0})

    path = tmp_path / "job.p6fold"
    loaded = session.load_project(path, {"w": 400.0, "nested": {"value": 1}})
    loaded["nested"]["value"] = 999

    assert session.project_path == str(path)
    assert session.has_draft is False
    assert session.loaded_baseline_snapshot() == {"w": 400.0, "nested": {"value": 1}}
    assert session.committed_snapshot() == {"w": 400.0, "nested": {"value": 1}}

    session.capture_committed({"w": 450.0})

    assert session.committed_snapshot()["w"] == pytest.approx(450.0)
    assert session.loaded_baseline_snapshot()["w"] == pytest.approx(400.0)

    session.set_project_path(None)
    assert session.project_path is None


def test_capture_committed_rejects_mutation_while_draft_is_active():
    session = ProjectSession()
    session.capture_committed({"w": 400.0})
    session.begin_draft()

    with pytest.raises(RuntimeError, match="active draft"):
        session.capture_committed({"w": 999.0})

    assert session.snapshot_for_save()["w"] == pytest.approx(400.0)
