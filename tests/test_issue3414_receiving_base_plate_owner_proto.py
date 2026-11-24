"""Scratch witness: scope denotes a persisted board, never its recycled topology ID."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import normalize_receiving_layout, rename_receiving_panel
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from tests.test_issue1502_current_csv_multi_bay_once import _multi


OWNER = "base_plate_owner_id"


def _bay(source, si=0, bi=0):
    return source["receiving_layout"]["sets"][si]["bays"][bi]


def _resize(source, **kwargs):
    result = deepcopy(source)
    result["receiving_layout"], _removed = (
        api.resize_receiving_operator_topology_with_removed_ids(
            result["receiving_layout"], **kwargs,
        )
    )
    return result


def _write(path, source):
    return write_project(path, {"schema": PROJECT_SCHEMA, "snapshot": source})


def _roundtrip(tmp_path, name, source):
    return read_project(_write(tmp_path / (name + ".p6fold"), source))["snapshot"]


@pytest.mark.parametrize("kind", ["Bay", "Set"])
def test_actual_codec_recycled_topology_does_not_reuse_board(tmp_path, kind):
    old = _roundtrip(tmp_path, "legacy", _multi())
    assert OWNER not in _bay(old)
    if kind == "Bay":
        remove = {"set_index": 0, "bay_count": 1}
        add = {"set_index": 0, "bay_count": 2}
        slot = (0, 1)
        old = _resize(old, **remove)
    else:
        remove = {"set_count": 1}
        add = {"set_count": 2}
        slot = (1, 0)
    created = _roundtrip(tmp_path, "create", _resize(old, **add))
    created_bay = _bay(created, *slot)
    owner = created_bay[OWNER]
    renamed = deepcopy(created)
    renamed["receiving_layout"] = rename_receiving_panel(
        renamed["receiving_layout"], set_index=slot[0], bay_index=slot[1],
        panel_name="QA late board",
    )
    restored = _roundtrip(tmp_path, "rename", renamed)
    assert _bay(restored, *slot)[OWNER] == owner
    assert _bay(restored, *slot)["panel_name"] == "QA late board"
    resaved = _roundtrip(tmp_path, "again", restored)
    assert _bay(resaved, *slot)[OWNER] == owner
    deleted = _roundtrip(tmp_path, "deleted", _resize(resaved, **remove))
    recreated = _roundtrip(tmp_path, "recreated", _resize(deleted, **add))
    actual = _bay(recreated, *slot)
    assert actual["stable_id"] == created_bay["stable_id"]
    assert [actual[k] for k in ("width", "height", "depth")] == [
        created_bay[k] for k in ("width", "height", "depth")
    ]
    assert actual[OWNER] != owner
    assert OWNER not in _bay(recreated)


def test_explicit_fresh_board_and_append_allocate_different_ids_and_validate(tmp_path):
    source = _multi()
    source["receiving_layout"] = api.operator_new_receiving_layout(
        width=800, height=1600, depth=350, new_physical_board=True,
    )
    owner = _bay(source)[OWNER]
    duplicate = _roundtrip(tmp_path, "explicit-grow", _resize(source, set_index=0, bay_count=2))
    assert _bay(duplicate)[OWNER] == owner
    assert _bay(duplicate, 0, 1)[OWNER] != owner
    assert "part_features" not in _bay(duplicate, 0, 1)
    _bay(duplicate, 0, 1)[OWNER] = owner
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_OWNER_DUPLICATE"):
        normalize_receiving_layout(duplicate["receiving_layout"])
    _bay(duplicate, 0, 1)[OWNER] = "receiving:set:1:bay:2"
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_OWNER_INVALID"):
        _write(tmp_path / "invalid.p6fold", duplicate)
    assert not (tmp_path / "invalid.p6fold").exists()


def test_primary_original_menu_saves_and_reopens_new_owner(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog
    import gui

    source = _resize(_resize(_multi(), set_index=0, bay_count=1), set_index=0, bay_count=2)
    owner = _bay(source, 0, 1)[OWNER]
    initial = _write(tmp_path / "initial.p6fold", source)
    saved = tmp_path / "primary.p6fold"
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root)
        designer = host.fold_designer_app
        menu = designer.project_file_menu
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **_: str(initial))
        assert "開啟" in menu.entrycget(0, "label")
        menu.invoke(0)
        root.update()
        assert host.project_controller.project_path == str(initial)
        assert _bay(designer._phase6_input_snapshot, 0, 1)[OWNER] == owner
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_: str(saved))
        assert "另存" in menu.entrycget(2, "label")
        menu.invoke(2)
        root.update()
        assert saved.exists()
        assert _bay(read_project(saved)["snapshot"], 0, 1)[OWNER] == owner
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **_: str(saved))
        menu.invoke(0)
        root.update()
        assert host.project_controller.project_path == str(saved)
        assert _bay(designer._phase6_input_snapshot, 0, 1)[OWNER] == owner
    finally:
        root.destroy()


def test_fresh_set_bay_mode_and_committed_family_plan_allocate_owners(tmp_path):
    from tests.test_issue2517_family_model_transition_engine_api import _call, _snapshot

    dimensions = {"w": 800, "h": 1600, "d": 350}
    set_bay = api.fresh_receiving_mode("set_bay", dimensions)
    owner = _bay(_roundtrip(tmp_path, "fresh-mode", set_bay))[OWNER]
    assert OWNER not in repr(api.fresh_receiving_mode("quantity", dimensions))
    family = _call("受電箱", "金庫型", _snapshot()).input_snapshot
    family_owner = _bay(_roundtrip(tmp_path, "family-transition", family))[OWNER]
    assert family_owner != owner
