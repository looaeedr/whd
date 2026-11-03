"""#2517: a real multi-Bay DXF cannot consume truncated/nonfinite 3D source XYZ."""
from __future__ import annotations

from copy import deepcopy
from math import inf, nan
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import receiving_bay_assembly_offsets
from tests.test_issue1502_current_csv_multi_bay_once import _multi


def _resolved_part(offset=(3.0, 5.0, 7.0), placement="back"):
    return SimpleNamespace(
        part_key="box_body", render_data=object(),
        x_profile=(), y_profile=(), placement=placement, offset=offset,
    )


def test_real_multibay_anchor_is_removed_exactly_without_changing_source():
    layout = _multi()["receiving_layout"]
    original_layout = deepcopy(layout)
    for bay_index in (0, 1):
        anchor = receiving_bay_assembly_offsets(layout, set_index=0)[bay_index]
        part = _resolved_part(tuple(a + d for a, d in zip(anchor, (10., -5., 2.))))
        geometry = manufacturing_api.resolve_receiving_bay_local_export_geometry(
            (part,), layout, set_index=0, bay_index=bay_index,
        )
        assert geometry.parts[0].render_data is part.render_data
        assert geometry.parts[0].offset == pytest.approx((10., -5., 2.))
        assert part.offset == tuple(a + d for a, d in zip(anchor, (10., -5., 2.)))
    assert layout == original_layout


@pytest.mark.parametrize("offset", [
    None, (), (1., 2.), (1., 2., 3., 4.), {"x": 0, "y": 0, "z": 0},
    (True, 0., 0.), (0., False, 0.), (nan, 0., 0.),
    (0., inf, 0.), (0., 0., -inf), ("invalid", 0., 0.),
    (10 ** 1000, 0., 0.),
])
def test_multibay_dxf_never_accepts_missing_truncated_or_nonfinite_world_xyz(offset):
    layout = _multi()["receiving_layout"]
    source = deepcopy(layout)
    part = _resolved_part(offset)
    with pytest.raises(ValueError, match="RECEIVING_BAY_EXPORT_WORLD_OFFSET_INVALID"):
        manufacturing_api.resolve_receiving_bay_local_export_geometry(
            (part,), layout, set_index=0, bay_index=1,
        )
    assert layout == source and part.offset is offset


@pytest.mark.parametrize("index", [-1, 2, True, False, 1.0, None])
def test_multibay_export_rejects_nonphysical_or_out_of_bounds_bay_index(index):
    layout = _multi()["receiving_layout"]
    with pytest.raises(IndexError, match="RECEIVING_BAY_EXPORT_INDEX_INVALID"):
        manufacturing_api.resolve_receiving_bay_local_export_geometry(
            (_resolved_part(),), layout, set_index=0, bay_index=index,
        )


@pytest.mark.parametrize("placement", [None, "", False, 12])
def test_unowned_physical_placement_cannot_become_a_manufacturing_export(placement):
    with pytest.raises(ValueError, match="RECEIVING_BAY_EXPORT_PLACEMENT_INVALID"):
        manufacturing_api.resolve_receiving_bay_local_export_geometry(
            (_resolved_part(placement=placement),),
            _multi()["receiving_layout"], set_index=0, bay_index=0,
        )


def test_standalone_preview_remains_blocked_in_full_engine_export_api():
    with pytest.raises(ValueError, match="多連出圖禁止"):
        manufacturing_api.resolve_receiving_bay_local_export_geometry(
            (_resolved_part(placement="standalone"),),
            _multi()["receiving_layout"], set_index=0, bay_index=0,
        )


def test_multibay_gui_actual_head_export_valid_roundtrip_and_bad_xyz_atomic_rejection(
    tmp_path, monkeypatch,
):
    """Original GUI route; real head FinalScene and independent on-disk DXF."""
    import fold_designer_bridge as bridge
    from gui_modules.project import export_actions as actions
    from phase6_final_scene_contracts import AssemblyScenePart
    from tests.test_issue1504_ac09_ac24_original_multibay_independent_export import (
        _fresh_unrelated_geometry, _source_with_missing_second_model,
    )
    from tests.test_issue1502_multibay_original_gui_export_integration import (
        _native_callback_host,
    )
    from tests.test_issue1502_single_button_full_csv_receiving_export import _flags

    snapshot = _source_with_missing_second_model()
    original = deepcopy(snapshot)
    host = _native_callback_host(monkeypatch, snapshot, [])
    flags = _flags(
        box_body=False, head=True, tail=False, door=False,
        base_plate=False, indicator_box=False, indicator_door=False,
    )
    corrupt = {"on": False}

    class CurrentPhysicalBay:
        def receiving_bay_preview_request(self, namespace, si, bi, *, preview_layout=None):
            assert namespace is bridge.__dict__
            assert preview_layout is not None
            current = {
                **snapshot, "receiving_layout": preview_layout,
            }
            source = _fresh_unrelated_geometry(current, si, bi)
            anchor = receiving_bay_assembly_offsets(
                snapshot["receiving_layout"], set_index=si,
            )[bi]
            physical = []
            for part in source.parts:
                world = tuple(a + b for a, b in zip(part.offset, anchor))
                if corrupt["on"] and bi == 1 and part.part_key == "head":
                    world = world[:2]  # damaged physical source, never a valid XY-only sheet
                physical.append(AssemblyScenePart(
                    part_key=part.part_key, render_data=part.render_data,
                    x_profile=part.x_profile, y_profile=part.y_profile,
                    placement=part.placement, offset=world,
                ))
            return SimpleNamespace(
                render_data=SimpleNamespace(assembly_parts=tuple(physical)),
            )

    monkeypatch.setattr(bridge, "_phase6_composition", lambda _: CurrentPhysicalBay())
    folder = tmp_path / "valid"
    filenames, errors = actions._export_selected_resolved_parts(
        host, str(folder), flags,
    )
    assert not errors and len(filenames) == 2
    assert len(tuple(folder.glob("*.dxf"))) == 2
    for path in folder.glob("*.dxf"):
        assert ezdxf.readfile(path).modelspace() is not None

    corrupt["on"] = True
    blocked = tmp_path / "blocked"
    with pytest.raises(ValueError, match="RECEIVING_BAY_EXPORT_WORLD_OFFSET_INVALID"):
        actions._export_selected_resolved_parts(host, str(blocked), flags)
    assert not list(blocked.glob("*.dxf"))
    assert snapshot == original
