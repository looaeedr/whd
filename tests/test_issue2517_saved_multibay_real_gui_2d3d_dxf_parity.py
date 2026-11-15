"""#2517 real persisted Receiving Set/Bay → original GUI → canonical 2D/3D/DXF.

Unlike the original in-memory multi-Bay acceptance, this round-trips the
authentic committed numeric NFB sources through a .p6fold project before
rebuilding each Bay's independent Engine FinalScene and invoking the shipped
GUI export_selected_dxf action. This remains a scoped software acceptance;
it does not certify welding, MFG-2/NC or Windows operator UAT.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project import export_actions as gui
import phase6_project_file as project
from tests.test_issue1502_current_csv_multi_bay_once import _multi, _provider
from tests.test_issue1502_multibay_original_gui_export_integration import (
    _native_callback_host,
)


def _reloaded_two_bays(tmp_path):
    authored = _multi()
    unmodified = deepcopy(authored)
    project_path = project.write_project(
        tmp_path / "original-two-bay-manufacturing.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": authored},
    )
    before_bytes = project_path.read_bytes()
    loaded = project.read_project(project_path)["snapshot"]
    assert authored == unmodified
    assert project_path.read_bytes() == before_bytes
    assert loaded["model"] == "受電箱"
    assert loaded["active_mode"] == "set_bay"
    original_layout = authored["receiving_layout"]
    new_layout = loaded["receiving_layout"]
    assert [bay["stable_id"] for bay in original_layout["sets"][0]["bays"]] == [
        bay["stable_id"] for bay in new_layout["sets"][0]["bays"]
    ]
    assert [bay["panel_name"] for bay in original_layout["sets"][0]["bays"]] == [
        bay["panel_name"] for bay in new_layout["sets"][0]["bays"]
    ]
    assert len(new_layout["sets"][0]["bays"]) == 2
    return project_path, authored, loaded, before_bytes


def _verify_two_physical_bay_scenes(authored, loaded):
    original_provider, original_calls = _provider(authored)
    reloaded_provider, reloaded_calls = _provider(loaded)
    for bay_index in (0, 1):
        before = original_provider(0, bay_index)
        after = reloaded_provider(0, bay_index)
        # Every selected physical part, including the independent 3-piece
        # BoxBody, must be re-derived from this Bay, never the active Bay cache.
        assert {p.part_key for p in before.parts} == {
            p.part_key for p in after.parts
        }
        before_body, after_body = before.part("box_body"), after.part("box_body")
        assert before_body is not None and after_body is not None
        source_pieces = before_body.render_data.pieces
        saved_pieces = after_body.render_data.pieces
        assert [p.role for p in source_pieces] == [
            "left_side", "back", "right_side"
        ]
        assert [p.role for p in saved_pieces] == [
            "left_side", "back", "right_side"
        ]
        for original, restored in zip(source_pieces, saved_pieces):
            assert original.render_data.material.equals(
                restored.render_data.material
            )
            assert original.render_data.scene == restored.render_data.scene
            assert original.render_data.fold_guides == (
                restored.render_data.fold_guides
            )
        for original, restored in zip(before.parts, after.parts):
            assert original.part_key == restored.part_key
            previous = original.render_data
            current = restored.render_data
            if not previous.pieces and not current.pieces:
                assert previous.material.equals(current.material)
                assert previous.scene == current.scene
                assert previous.fold_guides == current.fold_guides
        dimensions = (loaded["w"], loaded["h"], loaded["d"])
        before_3d = api.resolve_box_body_true_world_piece_meshes(
            before_body, dimensions=dimensions, thickness=loaded["t"],
        )
        after_3d = api.resolve_box_body_true_world_piece_meshes(
            after_body, dimensions=dimensions, thickness=loaded["t"],
        )
        assert len(before_3d) == len(after_3d) == 3
        assert all(mesh for _, mesh in after_3d)
        assert tuple((p.role, mesh) for p, mesh in before_3d) == tuple(
            (p.role, mesh) for p, mesh in after_3d
        )
    assert original_calls == reloaded_calls == [(0, 0), (0, 1)]


def _run_original_gui(monkeypatch, source, output):
    output.mkdir()
    used = []
    host = _native_callback_host(monkeypatch, source, used)
    # The real main GUI has a live baseline selector; witness its exact
    # original operator intent across all export and overwrite dialogs.
    host.baseline_var = SimpleNamespace(get=lambda: "受電箱")
    errors, infos = [], []
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **_kw: str(output))
    monkeypatch.setattr(
        gui.messagebox, "showerror", lambda title, detail:
        errors.append((title, detail)),
    )
    monkeypatch.setattr(
        gui.messagebox, "showwarning", lambda title, detail:
        errors.append((title, detail)),
    )
    monkeypatch.setattr(
        gui.messagebox, "showinfo", lambda title, detail:
        infos.append((title, detail)),
    )
    monkeypatch.setattr(
        gui.messagebox, "askyesno", lambda *_a, **_kw:
        pytest.fail("approved physical multi-Bay export cannot be partial"),
    )
    gui.export_selected_dxf(host)
    return used, errors, infos


def test_saved_two_bay_original_gui_2d_world_3d_and_all_actual_dxf(
    tmp_path, monkeypatch,
):
    path, authored, loaded, original_bytes = _reloaded_two_bays(tmp_path)
    _verify_two_physical_bay_scenes(authored, loaded)
    output = tmp_path / "original-gui-dxf"
    used, errors, infos = _run_original_gui(monkeypatch, loaded, output)
    assert not errors, errors
    assert len(infos) == 1
    assert used == [(0, 0), (0, 1)]
    all_outputs = tuple(sorted(output.iterdir()))
    dxfs = tuple(p for p in all_outputs if p.suffix.lower() == ".dxf")
    assert dxfs and len(dxfs) >= 20
    assert len({p.name for p in dxfs}) == len(dxfs)
    assert sum("fixing_plate" in p.name for p in dxfs) == 4
    assert sum("base_plate" in p.name and "fixing_plate" not in p.name
               for p in dxfs) == 2
    assert sum("inner_door" in p.name and "panel" in p.name
               for p in dxfs) == 2
    assert sum("left_side" in p.name for p in dxfs) >= 2
    assert sum("right_side" in p.name for p in dxfs) >= 2
    for actual in dxfs:
        doc = ezdxf.readfile(actual)
        assert not doc.audit().errors, actual.name
        assert any(entity.dxf.layer == "CUTTING" for entity in doc.modelspace())
    assert path.read_bytes() == original_bytes


def test_saved_two_bay_invalid_second_physical_source_never_partially_publishes(
    tmp_path, monkeypatch,
):
    path, _authored, loaded, original_bytes = _reloaded_two_bays(tmp_path)
    stale = deepcopy(loaded)
    second = stale["receiving_layout"]["sets"][0]["bays"][1]
    assert second["nfb_config_submitted"] is True
    # A real second Bay may be selected, but its original NFB CSV row can no
    # longer be resolved. It must never borrow the first Bay's geometry.
    second["nfb_config"]["holes"][0]["model_filename"] = (
        "nfbv5:士林:MISSING-CONFIRMED-SOURCE"
    )
    output = tmp_path / "invalid-second-bay"
    _used, errors, infos = _run_original_gui(monkeypatch, stale, output)
    assert errors and not infos
    assert not list(output.iterdir())
    assert path.read_bytes() == original_bytes
