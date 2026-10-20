# -*- coding: utf-8 -*-
"""#1502 the operator CSV base path reaches the real PartRenderData DXF writer."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.manufacturing_api import build_part_render_data
from gui_modules.application.receiving_csv_v5_base_export_action import (
    csv_base_part_only_ready,
    export_current_receiving_csv_base_part_from_gui,
)
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
from tests.test_issue1502_source_derived_center_base import _spec


def _assembly(snap):
    spec = _spec(snap)
    actual = build_part_render_data(spec)
    return spec, (SimpleNamespace(
        part_key="base_plate", render_data=actual,
        placement="offset", offset=(0.0, 0.0, 0.0),
    ),)


def test_current_csv_operator_without_manual_base_or_legacy_session_exports(tmp_path):
    snap = _current()
    assert "receiving_base_plate" not in snap
    assert csv_base_part_only_ready(snap)
    spec, parts = _assembly(snap)
    output = export_current_receiving_csv_base_part_from_gui(
        snap, base_spec=spec, assembly_parts=parts,
        output_directory=tmp_path / "parts",
    )
    assert output.part_id == "base_plate" and output.quantity == 1
    assert output.source_hole_ids == ("nfb:0", "nfb:1")
    assert len(output.check_q_key) == 64
    saved = Path(output.path)
    assert saved.is_file()
    model = ezdxf.readfile(saved).modelspace()
    cutting = [item for item in model
               if item.dxftype() == "CIRCLE" and item.dxf.layer == "CUTTING"]
    ears = [item for item in model
            if item.dxftype() == "LWPOLYLINE"
            and item.closed and item.dxf.layer == "CUTTING"]
    assert len(cutting) == 8 and len(ears) == 5
    assert len(list(saved.parent.glob("*.dxf"))) == 1


def test_single_csv_variant_ready_only_with_confirmed_x_and_real_plate(tmp_path):
    snap = _current()
    spec, parts = _assembly(snap)
    snap["nfb_config"]["holes"][0]["manual_x_state"] = "RECONFIRM_REQUIRED"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    assert not csv_base_part_only_ready(snap)
    with pytest.raises(ValueError, match="NOT_CONFIRMED"):
        export_current_receiving_csv_base_part_from_gui(
            snap, base_spec=spec, assembly_parts=parts, output_directory=tmp_path,
        )
    assert not list(tmp_path.glob("*.dxf"))


def test_no_borrowed_bay_or_fake_assembly_plate_or_missing_source(tmp_path):
    snap = _current()
    spec, parts = _assembly(snap)
    wrong_bay = deepcopy(snap)
    wrong_bay["_receiving_runtime_selection"]["bay_id"] = "other"
    assert not csv_base_part_only_ready(wrong_bay)
    with pytest.raises(ValueError, match="IDENTITY_DRIFT"):
        export_current_receiving_csv_base_part_from_gui(
            wrong_bay, base_spec=spec, assembly_parts=parts, output_directory=tmp_path,
        )
    with pytest.raises(ValueError, match="不在目前已解析"):
        export_current_receiving_csv_base_part_from_gui(
            snap, base_spec=spec,
            assembly_parts=(SimpleNamespace(part_key="box_body", render_data=parts[0].render_data),),
            output_directory=tmp_path,
        )
    with pytest.raises(ValueError, match="不在目前已解析"):
        export_current_receiving_csv_base_part_from_gui(
            snap, base_spec=spec, assembly_parts=(parts[0], parts[0]),
            output_directory=tmp_path,
        )
    wrong = replace(parts[0], placement="standalone")
    with pytest.raises(ValueError, match="已裝配"):
        export_current_receiving_csv_base_part_from_gui(
            snap, base_spec=spec, assembly_parts=(wrong,),
            output_directory=tmp_path,
        )
    assert not list(tmp_path.glob("*.dxf"))


def test_unrecognized_csv_plate_variant_does_not_create_operator_button():
    snap = _current()
    snap["nfb_config"]["holes"][1]["model_filename"] = "nfbv5:士林:3P999UNKNOWN"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    assert not csv_base_part_only_ready(snap)


def test_csv_button_wiring_is_independent_of_legacy_dxfs():
    """Check exported live operator hooks, not just the lower-level writer."""
    import inspect
    from gui_modules.application import (
        fold_designer_composition_receiving as composition,
        receiving_multi_settings_window as window,
    )
    source = inspect.getsource(composition)
    gui_source = inspect.getsource(window)
    assert '"csv_base_partial_export": export_csv_base_part' in source
    assert '"csv_base_part_ready"' in source
    assert "receiving_bay_preview_request(namespace, set_index, bay_index)" in source
    assert 'text="輸出 CSV 底板 DXF（單片）"' in gui_source
    assert 'live_ports["csv_base_partial_export"](' in gui_source
    assert 'live_ports["pair_partial_export"](' in gui_source
