"""#2517 persisted Receiving two-Set 4-Bay: original GUI grouped DXF/total.

The shipped GUI's grouped selector, Engine group plan and physical Bay FinalScene
must use the same real project source after Save→Reload. Reopen every actually
composed DXF: an Engine grouping plan or a mocked file list is NOT acceptance.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import RECEIVING_DOOR_STATE_KEYS, update_receiving_bay
from gui_modules.project import export_actions as gui
import phase6_project_file as project
from tests.test_issue1502_multibay_original_gui_export_integration import (
    _native_callback_host,
)
from tests.test_issue2517_saved_two_sets_four_bays_bom_collision_gui_dxf import (
    _saved_two_sets,
)


STAMP = "202611151620"
PREFIX = f"{STAMP}_p1~p4"
BAYS = ((0, 0), (0, 1), (1, 0), (1, 1))


@pytest.fixture(autouse=True)
def _freeze_engine_group_stamp(monkeypatch):
    # The Engine, not the GUI, owns the actual Taiwan-minute output stamp.
    monkeypatch.setattr(
        "ae_engine.receiving_dxf_groups._taipei_output_stamp",
        lambda: STAMP,
    )


def _run_gui_group(monkeypatch, source, output, *, mode, with_nfb=False,
                   on_folder=None):
    output.mkdir()
    callbacks = []
    host = _native_callback_host(monkeypatch, source, callbacks)
    # The original callback now passes an Engine-planned preview_layout for
    # independent selected Head-only operations. This fixture's genuine
    # physical provider already resolves the SAME confirmed per-Bay source;
    # accept the current GUI callback signature without inventing geometry.
    import fold_designer_bridge as bridge
    composition = bridge._phase6_composition(host.fold_designer_app)
    actual_preview = composition.receiving_bay_preview_request
    def preview(namespace, si, bi, *, preview_layout=None):
        return actual_preview(namespace, si, bi)
    composition.receiving_bay_preview_request = preview
    host.baseline_var = SimpleNamespace(get=lambda: "受電箱")
    current_mode = [mode]
    host.receiving_dxf_group_mode_var = SimpleNamespace(
        get=lambda: current_mode[0],
    )
    # Head is the source-independent released manufacturing reference.
    # NFB-enabled run adds actual committed Door/Base pair from this saved
    # source, without selecting other not-yet whole-assembly-certified items.
    host.export_z_var.value = False
    host.export_tail_var.value = False
    host.export_door_var.value = with_nfb
    host.export_base_plate_var.value = with_nfb
    errors, infos = [], []

    def folder(**_kwargs):
        if on_folder is not None:
            on_folder(current_mode)
        return str(output)

    monkeypatch.setattr(gui.filedialog, "askdirectory", folder)
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, msg: errors.append((title, msg)))
    monkeypatch.setattr(gui.messagebox, "showwarning",
                        lambda title, msg: errors.append((title, msg)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda title, msg: infos.append((title, msg)))
    monkeypatch.setattr(gui.messagebox, "askyesno",
                        lambda *_a, **_kw: pytest.fail(
                            "grouped verified export cannot silently become partial"
                        ))
    gui.export_selected_dxf(host)
    return callbacks, errors, infos


def _actual_dxf(path):
    doc = ezdxf.readfile(path)
    assert not doc.audit().errors, path.name
    assert any(e.dxf.layer == "CUTTING" for e in doc.modelspace())
    return doc


def _check_texts(doc):
    return tuple(
        e.plain_text() for e in doc.modelspace()
        if e.dxftype() == "MTEXT" and e.dxf.layer == "CHECK"
    )


def _saved_with_real_inner_door_state(tmp_path):
    """Author every physical Bay Door source with the actual Engine writer.

    A confirmed CSV alone may NOT authorize NFB Door/Base composition. Build
    real submitted InnerDoor topology and Save→Reload that added operator state
    before requesting any paired manufacturing output.
    """
    _previous_path, _previous_bytes, _authored, source = _saved_two_sets(tmp_path)
    updated = deepcopy(source)
    fresh = api.fresh_receiving_mode(
        "set_bay", {"w": updated["w"], "h": updated["h"], "d": updated["d"]},
        thickness=updated["t"],
    )
    door = {
        key: deepcopy(fresh[key])
        for key in RECEIVING_DOOR_STATE_KEYS if key in fresh
    }
    assert door.get("inner_doors") and door.get("multi_door_enabled") is True
    assert door.get("door_layout_columns")
    layout = updated["receiving_layout"]
    for si, bi in BAYS:
        layout = update_receiving_bay(
            layout, set_index=si, bay_index=bi,
            door_state=door,
        )
    updated["receiving_layout"] = layout
    saved = project.write_project(
        tmp_path / "four-real-bays-with-confirmed-inner-door.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": updated},
    )
    original_bytes = saved.read_bytes()
    loaded = project.read_project(saved)["snapshot"]
    assert loaded["receiving_layout"] == layout
    assert all(
        bay["door_state"].get("inner_doors")
        for group in loaded["receiving_layout"]["sets"] for bay in group["bays"]
    )
    return saved, original_bytes, loaded


@pytest.mark.parametrize("mode, group_names, member_counts", (
    ("ALL", ("全部",), (4,)),
    ("PER_SET", ("第1套", "第2套"), (2, 2)),
    ("END_VS_MIDDLE", ("頭尾盤",), (4,)),
))
def test_saved_four_bay_original_gui_grouping_and_compact_total(
    tmp_path, monkeypatch, mode, group_names, member_counts,
):
    project_file, before_bytes, _authored, restored = _saved_two_sets(tmp_path)
    original = deepcopy(restored)
    source_groups = api.plan_receiving_grouped_dxf(
        restored["receiving_layout"], mode,
    )
    assert tuple(name.removesuffix(".dxf") for name, _ in source_groups) == group_names
    assert tuple(len(cells) for _name, cells in source_groups) == member_counts
    output = tmp_path / f"gui-{mode.lower()}"
    calls, errors, infos = _run_gui_group(
        monkeypatch, restored, output, mode=mode,
    )
    assert not errors, errors
    assert len(infos) == 1
    assert calls == list(BAYS)
    expected_names = {
        *(PREFIX + name + ".dxf" for name in group_names),
        PREFIX + "總計.dxf",
    }
    actual_files = tuple(sorted(output.iterdir()))
    assert {p.name for p in actual_files} == expected_names
    for name, count in zip(group_names, member_counts):
        doc = _actual_dxf(output / (PREFIX + name + ".dxf"))
        # Each original physical Head remains an independent CHECK identity
        # in the full machining group, not a second set's duplicated preview.
        labels = _check_texts(doc)
        assert labels.count("head") == count, (name, labels)
    total = _actual_dxf(output / (PREFIX + "總計.dxf"))
    total_texts = _check_texts(total)
    assert any("總計：4片" in s for s in total_texts), total_texts
    assert any("head × 4" in s for s in total_texts), total_texts
    assert project_file.read_bytes() == before_bytes
    assert restored == original


def test_saved_four_bay_original_gui_all_group_retains_real_nfb_pairs(
    tmp_path, monkeypatch,
):
    project_file, original_bytes, source = _saved_with_real_inner_door_state(tmp_path)
    output = tmp_path / "gui-nfb-composed"
    calls, errors, infos = _run_gui_group(
        monkeypatch, source, output, mode="ALL", with_nfb=True,
    )
    assert not errors, errors
    assert len(infos) == 1
    assert calls == list(BAYS)
    files = tuple(output.iterdir())
    assert {p.name for p in files} == {
        PREFIX + "全部.dxf", PREFIX + "總計.dxf",
    }
    composed = _actual_dxf(output / (PREFIX + "全部.dxf"))
    labels = _check_texts(composed)
    assert labels.count("head") == 4
    assert labels.count("base_plate") == 4
    assert len(tuple(s for s in labels if s.startswith("inner_door:")
                     and " × " not in s)) == 4
    total = _actual_dxf(output / (PREFIX + "總計.dxf"))
    assert any("總計：" in line for line in _check_texts(total))
    assert project_file.read_bytes() == original_bytes


def test_group_selector_changes_during_original_gui_folder_dialog_are_rejected(
    tmp_path, monkeypatch,
):
    saved, original_bytes, _authored, source = _saved_two_sets(tmp_path)
    output = tmp_path / "changed-group-after-dialog"
    calls, errors, infos = _run_gui_group(
        monkeypatch, source, output, mode="ALL",
        on_folder=lambda mode: mode.__setitem__(0, "PER_SET"),
    )
    assert errors and not infos
    assert not list(output.iterdir())
    assert saved.read_bytes() == original_bytes


def test_saved_second_set_csv_failure_refuses_entire_group_and_total(
    tmp_path, monkeypatch,
):
    saved, original_bytes, source = _saved_with_real_inner_door_state(tmp_path)
    damaged = deepcopy(source)
    bay = damaged["receiving_layout"]["sets"][1]["bays"][1]
    assert bay["nfb_config_submitted"] is True
    bay["nfb_config"]["holes"][0]["model_filename"] = (
        "nfbv5:士林:MISSING-SAVED-SET2-BAY2-CSV-ROW"
    )
    output = tmp_path / "grouped-invalid-csv"
    calls, errors, infos = _run_gui_group(
        monkeypatch, damaged, output, mode="PER_SET", with_nfb=True,
    )
    assert errors and not infos
    assert not list(output.iterdir())
    assert saved.read_bytes() == original_bytes
