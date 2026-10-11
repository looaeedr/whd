"""Regression: a fresh head/tail candidate must not overwrite version one."""

from pathlib import Path

from ae_engine.receiving_hole_candidates import (
    create_candidate, candidates_for, update_candidate, version_label,
)


def test_head_and_tail_new_version_preserves_previous_candidate():
    library = None
    for role in ("head", "tail"):
        library, first = create_candidate(library, role, [{"hole": "first"}])
        library, second = create_candidate(library, role, [{"hole": "second"}])
        assert first == f"{role}-v1"
        assert second == f"{role}-v2"
        assert version_label(second) == "版本二"
        assert [item["id"] for item in candidates_for(library, role)] == [first, second]
        assert [item["features"] for item in candidates_for(library, role)] == [
            [{"hole": "first"}], [{"hole": "second"}],
        ]
        library = update_candidate(library, role, second, [{"hole": "edited"}])
        assert candidates_for(library, role)[0]["features"] == [{"hole": "first"}]
        assert candidates_for(library, role)[1]["features"] == [{"hole": "edited"}]


def test_version_manager_new_button_opens_editor_with_no_existing_version_id():
    source = (Path(__file__).resolve().parents[1] /
              "gui_modules/application/receiving_multi_settings_window.py").read_text(encoding="utf-8")
    assert 'text="新增版本", command=lambda: create_new_version()' in source
    assert 'get_candidate_ports()["edit"](\n                role, None,' in source
    assert "def editor_saved(role, version_id):" in source
    assert "candidate_selected[role] = version_id" in source
