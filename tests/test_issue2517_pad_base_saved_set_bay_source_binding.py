"""#2517: PAD+Base CHECK/Q must bind GUI Set/Bay intent to physical saved IDs.

Actual persisted committed NFB source, public Engine selector and the shipped
GUI button must refuse a stale but nonblank selected ID, stale physical index
or switched Bay/NFB, without writing a single DXF or changing the project.
This does not certify PAD/EAR welding or whole-cabinet manufacturing.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import resize_receiving_bays, update_receiving_bay
from gui_modules.project import export_actions as gui
import phase6_project_file as project
from tests.test_issue1502_current_csv_multi_bay_once import _multi
from tests.test_issue2517_reloaded_pad_base_real_gui_button_check_q import (
    _call_real_gui, _physical_gui_saved_source,
)


def _selection(snapshot, si=0, bi=0):
    group = snapshot["receiving_layout"]["sets"][si]
    return {
        "set_id": group["stable_id"],
        "bay_id": group["bays"][bi]["stable_id"],
        "set_index": si,
        "bay_index": bi,
    }


@pytest.mark.parametrize("bad", (
    "set_id", "bay_id", "set_index_bool", "bay_index_bool",
    "set_index_out_of_range", "bay_index_out_of_range",
    "set_index_str", "bay_index_float", "missing_index",
))
def test_actual_save_reload_rejects_stale_nonblank_set_bay_runtime(
    tmp_path, bad,
):
    saved_path, loaded, _selected, _parts, _sheets = (
        _physical_gui_saved_source(tmp_path)
    )
    saved_disk = saved_path.read_bytes()
    original = deepcopy(loaded)
    control = deepcopy(loaded)
    runtime = dict(_selection(control))
    if bad in {"set_id", "bay_id"}:
        runtime[bad] = "stale-but-nonblank-id"
    elif bad == "set_index_bool":
        runtime["set_index"] = True
    elif bad == "bay_index_bool":
        runtime["bay_index"] = False
    elif bad == "set_index_out_of_range":
        runtime["set_index"] = 1
    elif bad == "bay_index_out_of_range":
        runtime["bay_index"] = 1
    elif bad == "set_index_str":
        runtime["set_index"] = "0"
    elif bad == "bay_index_float":
        runtime["bay_index"] = 0.0
    elif bad == "missing_index":
        del runtime["bay_index"]
    control["_receiving_runtime_selection"] = runtime
    before = deepcopy(control)
    with pytest.raises(ValueError, match="Set／Bay 實體選取已失效"):
        api.resolve_receiving_pad_base_export_source(control)
    assert control == before and loaded == original
    assert saved_path.read_bytes() == saved_disk
    assert not list(tmp_path.glob("*.dxf"))


@pytest.mark.parametrize("change", ("nfb_unsubmitted", "nfb_mismatch"))
def test_saved_selected_bay_cannot_borrow_other_nfb_snapshot(
    tmp_path, change,
):
    path, loaded, _selection_result, _parts, _sheets = (
        _physical_gui_saved_source(tmp_path)
    )
    snapshot = deepcopy(loaded)
    bay = snapshot["receiving_layout"]["sets"][0]["bays"][0]
    if change == "nfb_unsubmitted":
        bay["nfb_config_submitted"] = False
    else:
        bay["nfb_config"] = {"source": "different-physical-bay"}
    before = deepcopy(snapshot)
    with pytest.raises(ValueError, match="NFB 來源已失效"):
        api.resolve_receiving_pad_base_export_source(snapshot)
    assert snapshot == before
    assert path.is_file()
    assert not list(tmp_path.glob("*.dxf"))


def test_real_saved_two_bay_layout_cannot_select_unsubmitted_cloned_bay(
    tmp_path,
):
    original_path, loaded, _selection_result, _parts, _sheets = (
        _physical_gui_saved_source(tmp_path)
    )
    saved = deepcopy(loaded)
    # Tail clone copies the NFB submitted fact but invalidates its world-X
    # confirmation. Explicitly withdraw its submission through the original
    # Engine transaction; never treat an unconfirmed clone as manufactured.
    saved["receiving_layout"] = update_receiving_bay(
        resize_receiving_bays(
            saved["receiving_layout"], set_index=0, bay_count=2,
        ),
        set_index=0, bay_index=1, nfb_config_submitted=False,
    )
    target = project.write_project(
        tmp_path / "two-physical-bays.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": saved},
    )
    restored = project.read_project(target)["snapshot"]
    group = restored["receiving_layout"]["sets"][0]
    assert len(group["bays"]) == 2 and len(group["joints"]) == 1
    assert group["bays"][1].get("nfb_config_submitted") is not True
    original = deepcopy(restored)

    # The only original committed physical Bay remains selectable.
    first = deepcopy(restored)
    first["_receiving_runtime_selection"] = _selection(first, 0, 0)
    assert api.resolve_receiving_pad_base_export_source(first).version_id == (
        group["stable_id"] + "__" + group["bays"][0]["stable_id"]
    )

    # A copied Bay without independently confirmed NFB cannot acquire
    # CHECK/Q eligibility by borrowing root selected NFB.
    second = deepcopy(restored)
    second["_receiving_runtime_selection"] = _selection(second, 0, 1)
    with pytest.raises(ValueError, match="NFB 來源已失效"):
        api.resolve_receiving_pad_base_export_source(second)
    assert restored == original
    assert original_path.is_file() and target.is_file()


def test_two_actual_bays_choose_only_their_real_submitted_nfb():
    source = _multi()
    saved = source["receiving_layout"]["sets"][0]
    assert len(saved["bays"]) == 2
    for bi in (0, 1):
        selected = deepcopy(source)
        selected["nfb_config"] = deepcopy(saved["bays"][bi]["nfb_config"])
        selected["nfb_config_submitted"] = True
        selected["_receiving_runtime_selection"] = _selection(selected, 0, bi)
        before = deepcopy(selected)
        result = api.resolve_receiving_pad_base_export_source(selected)
        assert result.version_id == (
            saved["stable_id"] + "__" + saved["bays"][bi]["stable_id"]
        )
        assert result.snapshot == selected
        assert selected == before
        switched = deepcopy(selected)
        switched["_receiving_runtime_selection"] = _selection(
            switched, 0, 1 - bi,
        )
        with pytest.raises(ValueError, match="NFB 來源已失效"):
            api.resolve_receiving_pad_base_export_source(switched)


@pytest.mark.parametrize("change", ("fake_bay_id", "fake_bay_index"))
def test_actual_gui_button_never_publishes_check_q_for_stale_saved_identity(
    tmp_path, monkeypatch, change,
):
    saved_path, loaded, _selected, original_parts, _sheets = (
        _physical_gui_saved_source(tmp_path)
    )
    stable_bytes = saved_path.read_bytes()
    runtime = loaded["_receiving_runtime_selection"]
    if change == "fake_bay_id":
        runtime["bay_id"] = "replaced-bay"
    else:
        runtime["bay_index"] = 9
    source = deepcopy(loaded)
    with pytest.raises(ValueError, match="Set／Bay 實體選取已失效"):
        api.resolve_receiving_pad_base_export_source(source)

    # No Engine API is mocked. The actual GUI CHECK/Q action must fail
    # before real physical DXFs are staged or reported as successful.
    result, events = _call_real_gui(
        monkeypatch, loaded, original_parts, tmp_path,
    )
    assert result is None
    assert events and all(kind != "success" for kind, *_ in events)
    assert not any(p.is_dir() for p in tmp_path.iterdir())
    assert not list(tmp_path.glob("*.dxf"))
    assert saved_path.read_bytes() == stable_bytes
