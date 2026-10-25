# -*- coding: utf-8 -*-
"""#1503 real GUI click -> actual BoxBody/EAR -> DXF -> reload coordinates."""
import json
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from gui_modules.project import export_actions
from ae_engine.receiving_fixed_plate_side_check_dxf import (
    export_receiving_ear_side_check_only_dxf,
)
from tests.test_issue1050_receiving_mother_plate_marking import (
    _full_receiving_geometry,
)
from tests.test_issue1503_real_ear_side_weld_skin_mating import _real_world
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _geometry(factory):
    snapshot, _world = _real_world(factory)
    return snapshot, _full_receiving_geometry(snapshot)


def _marking_signature(paths):
    signature = {}
    for owner, filepath in paths:
        lines = []
        for entity in ezdxf.readfile(filepath).modelspace():
            if entity.dxftype() != "LINE" or entity.dxf.layer.upper() != "MARKING":
                continue
            p1 = (round(entity.dxf.start.x, 6), round(entity.dxf.start.y, 6))
            p2 = (round(entity.dxf.end.x, 6), round(entity.dxf.end.y, 6))
            lines.append(tuple(sorted((p1, p2))))
        signature[owner] = tuple(sorted(lines))
    return signature


@pytest.mark.parametrize("factory,expected_per_side", (
    (_assembled, 1), (_two_tier, 2),
))
def test_real_received_project_json_reload_produces_same_side_check_mark_uv(
    factory, expected_per_side, tmp_path,
):
    snapshot, geometry = _geometry(factory)
    before = export_receiving_ear_side_check_only_dxf(
        snapshot, geometry, tmp_path / "before",
        dimensions=(800, 1600, 350), sheet_thickness=2.,
    )
    restored = json.loads(json.dumps(snapshot, ensure_ascii=False))
    restored_geometry = _full_receiving_geometry(restored)
    after = export_receiving_ear_side_check_only_dxf(
        restored, restored_geometry, tmp_path / "restored",
        dimensions=(800, 1600, 350), sheet_thickness=2.,
    )
    expected = _marking_signature(before.output_paths)
    assert expected == _marking_signature(after.output_paths)
    assert set(expected) == {"box_body:left_side", "box_body:right_side"}
    assert all(len(rows) == expected_per_side for rows in expected.values())
    assert before.part_ids == after.part_ids
    assert before.physical_contact_area_mm2 == after.physical_contact_area_mm2
    assert not before.manufacturing_ready and not after.manufacturing_ready
    assert len(geometry.part("box_body").render_data.pieces) == len(
        restored_geometry.part("box_body").render_data.pieces)


def test_actual_gui_action_creates_two_reopened_check_dxfs_not_normal_mfg(
    tmp_path, monkeypatch,
):
    snapshot, geometry = _geometry(_assembled)
    events = []
    class FakeDesigner:
        _phase6_input_snapshot = snapshot
        def _phase6_resolve_manufacturing_geometry(self):
            events.append("canonical_resolve")
            return geometry
    host = SimpleNamespace(
        fold_designer_app=FakeDesigner(),
        _flush_phase6_authoritative_state=lambda: events.append("flush"),
    )
    monkeypatch.setattr(export_actions.filedialog, "askdirectory",
                        lambda **kw: str(tmp_path))
    monkeypatch.setattr(export_actions.messagebox, "showinfo",
                        lambda *args: events.append(("success", args)))
    monkeypatch.setattr(export_actions.messagebox, "showerror",
                        lambda *args: events.append(("error", args)))
    original = tuple(
        tuple(piece.render_data.scene.primitives or ())
        for piece in geometry.part("box_body").render_data.pieces
    )
    result = export_actions.export_receiving_ear_side_check_dxf(host)
    assert result is not None
    assert result.status == "RECEIVING_EAR_SIDE_CHECK_DXF_ONLY"
    assert result.saved_dxf_roundtrip_verified
    assert not result.manufacturing_ready
    assert events[0:2] == ["flush", "canonical_resolve"]
    assert len([x for x in events if isinstance(x, tuple) and x[0] == "success"]) == 1
    assert not [x for x in events if isinstance(x, tuple) and x[0] == "error"]
    assert set(dict(result.output_paths)) == {
        "box_body:left_side", "box_body:right_side"
    }
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    assert all("CHECK_ONLY" in Path(path).name for _owner, path in result.output_paths)
    assert all(len(lines) == 1
               for lines in _marking_signature(result.output_paths).values())
    assert original == tuple(
        tuple(piece.render_data.scene.primitives or ())
        for piece in geometry.part("box_body").render_data.pieces
    )
