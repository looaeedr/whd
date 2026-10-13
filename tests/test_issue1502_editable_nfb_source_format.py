# -*- coding: utf-8 -*-
"""#1502 editable operator original: DXF format is authority, not pinned SHA."""
from dataclasses import replace
from hashlib import sha256
import copy

import ezdxf
import pytest

from ae_engine.receiving_nfb_cutting_manufacturing import (
    read_nfb_runtime_source_profiles_csv,
)
from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source
from ae_engine.receiving_nfb_editable_source import resolve_editable_nfb_source_profile
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbConfiguredInnerDoorHole, configured_nfb_inner_door_render_data,
)
from ae_engine.receiving_nfb_ui1b_bridge import _nfb_config_proof_sha256
from gui_modules.application.receiving_nfb_base_partial_export_action import (
    export_verified_receiving_nfb_base_plate,
)
from tests.test_issue1497_configured_nfb_manufacturing_release import (
    _source, _state, _hole,
)
from tests.test_issue1502_live_nfb_base_partial_export import _live


def test_editing_upper_cutout_size_and_entity_handle_preserves_source_format(tmp_path):
    index, source, recorded = _source(tmp_path)
    original_bytes_sha = recorded.source_sha256
    drawing = ezdxf.readfile(source)
    msp = drawing.modelspace()
    old = next(e for e in msp if e.dxftype() == "LWPOLYLINE")
    old_handle = str(old.dxf.handle)
    msp.delete_entity(old)
    replacement = msp.add_lwpolyline(
        ((10., 20.), (73., 20.), (73., 104.), (10., 104.)),
        close=True, dxfattribs={"color": 150},
    )
    drawing.saveas(source)
    current = resolve_editable_nfb_source_profile(source, profile=recorded)
    assert current.source_sha256 == sha256(source.read_bytes()).hexdigest()
    assert current.source_sha256 != original_bytes_sha
    assert current.upper_handle != old_handle
    assert current.upper_handle == str(replacement.dxf.handle)
    assert current.upper_size_mm == pytest.approx((63., 84.))
    verified = configured_nfb_inner_door_render_data(
        _state(), "upper", holes=(_hole(),),
        index_path=index, source_path=source, profile=recorded,
    )
    assert verified.source_sha256 == current.source_sha256
    assert verified.render_data.metadata["nfb_source_handle"] == (
        current.source_sha256 + ":" + current.upper_handle
    )
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    cuts = tuple(p for p in verified.render_data.scene.primitives
                 if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"
                 and p.closed)
    last = cuts[-1]
    xs = [v.x for v in last.points]
    ys = [v.y for v in last.points]
    assert (max(xs) - min(xs), max(ys) - min(ys)) == pytest.approx((63., 84.))


def test_format_change_to_ambiguous_upper_color150_fails_without_output(tmp_path):
    index, source, profile = _source(tmp_path)
    drawing = ezdxf.readfile(source)
    drawing.modelspace().add_lwpolyline(
        ((90.,20.), (147.,20.), (147.,116.), (90.,116.)),
        close=True, dxfattribs={"color": 150},
    )
    drawing.saveas(source)
    target = tmp_path / "blocked.dxf"
    from ae_engine.receiving_nfb_manufacturing_release import save_configured_nfb_inner_door_dxf
    with pytest.raises(ValueError, match="unambiguous upper Color150"):
        save_configured_nfb_inner_door_dxf(
            _state(), "upper", target, holes=(_hole(),),
            index_path=index, source_path=source, profile=profile,
        )
    assert not target.exists()


def test_same_format_edited_lower_fixing_and_stale_index_sha_can_be_reverified(
    tmp_path,
):
    fixture = _live(tmp_path)
    # A different SHA recorded in the *editable* CSV is not a reason to
    # block the otherwise unchanged valid real source.
    p = fixture.profile
    p.write_text(p.read_text(encoding="utf-8-sig").replace(
        fixture.bundle.source_inventory.source_sha256, "a" * 64,
    ), encoding="utf-8")
    source = fixture.original
    original_sha = fixture.bundle.source_inventory.source_sha256
    drawing = ezdxf.readfile(source)
    msp = drawing.modelspace()
    circles = tuple(entity for entity in msp if entity.dxftype() == "CIRCLE"
                    and int(entity.dxf.get("color", 256)) == 3)
    assert len(circles) == 4
    circles[0].dxf.radius = 1.65
    drawing.saveas(source)
    assert sha256(source.read_bytes()).hexdigest() != original_sha

    # Reverification creates a fresh session receipt from the modified file;
    # the old submission is *never* silently reused after an edit.
    directory = tmp_path / "stale-block"
    directory.mkdir()
    with pytest.raises(ValueError, match="source bytes changed"):
        export_verified_receiving_nfb_base_plate(
            fixture.bundle, layout=fixture.layout,
            current_snapshot=fixture.snapshot, base_spec=fixture.plate,
            output_directory=directory, index_path=fixture.index,
            profile_path=fixture.profile,
        )
    assert not list(directory.iterdir())

    original_index_profile, = read_nfb_runtime_source_profiles_csv(fixture.profile)
    refreshed = resolve_editable_nfb_source_profile(source, profile=original_index_profile)
    assert refreshed.source_sha256 != original_index_profile.source_sha256
    current_inventory = inspect_nfb_dxf_source(source)
    new_config = copy.deepcopy(fixture.bundle.config)
    new_config["source_sha256"] = refreshed.source_sha256
    metadata = {
        **fixture.bundle.verified_door.render_data.metadata,
        "nfb_source_handle": refreshed.source_sha256 + ":" + refreshed.upper_handle,
        "nfb_profile_revision": refreshed.revision,
    }
    new_verified = replace(
        fixture.bundle.verified_door,
        source_sha256=refreshed.source_sha256,
        render_data=replace(fixture.bundle.verified_door.render_data, metadata=metadata)
        if hasattr(fixture.bundle.verified_door.render_data, "__dataclass_fields__")
        else type(fixture.bundle.verified_door.render_data)(metadata=metadata),
    )
    refreshed_bundle = replace(
        fixture.bundle, source_inventory=current_inventory,
        verified_door=new_verified,
        config=new_config,
        config_sha256_at_verification=_nfb_config_proof_sha256(new_config),
    )
    fixture.layout["sets"][0]["bays"][0]["nfb_config"] = new_config
    output_dir = tmp_path / "refreshed"
    output_dir.mkdir()
    path, result = export_verified_receiving_nfb_base_plate(
        refreshed_bundle, layout=fixture.layout,
        current_snapshot=fixture.snapshot, base_spec=fixture.plate,
        output_directory=output_dir, index_path=fixture.index,
        profile_path=fixture.profile,
    )
    circles_out = tuple(e for e in ezdxf.readfile(path).modelspace()
                        if e.dxftype() == "CIRCLE"
                        and abs(float(e.dxf.radius) - 1.65) < 1e-6)
    assert len(circles_out) == 2
    assert result.projection.source_sha256 == refreshed.source_sha256
    assert result.manufacturing_ready is False


def test_stale_sha_csv_with_unchanged_source_does_not_block_base_export(tmp_path):
    fixture = _live(tmp_path)
    csv_path = fixture.profile
    csv_path.write_text(csv_path.read_text(encoding="utf-8-sig").replace(
        fixture.bundle.source_inventory.source_sha256, "f" * 64,
    ), encoding="utf-8")
    output = tmp_path / "allowed"
    output.mkdir()
    path, rendered = export_verified_receiving_nfb_base_plate(
        fixture.bundle, layout=fixture.layout,
        current_snapshot=fixture.snapshot, base_spec=fixture.plate,
        output_directory=output, index_path=fixture.index,
        profile_path=fixture.profile,
    )
    assert ezdxf.readfile(path).modelspace() is not None
    assert rendered.projection.source_sha256 == fixture.bundle.source_inventory.source_sha256


def test_editable_csv_same_header_allows_blank_observation_fields(tmp_path):
    """New model/source edit requires no hand-maintained SHA or DXF handle."""
    _index, source, _old = _source(tmp_path)
    row = (
        "brand,indexed_filename,source_sha256,upper_handle,"
        "upper_width_mm,upper_height_mm,source_alias_status,revision\n"
        "士林,400_140X257_107.dxf,,,,,OPERATOR_EDITABLE,v1\n"
    )
    csv_path = tmp_path / "來源輪廓索引.csv"
    csv_path.write_text(row, encoding="utf-8")
    profiles = read_nfb_runtime_source_profiles_csv(csv_path)
    assert len(profiles) == 1
    assert profiles[0].source_sha256 == ""
    assert profiles[0].upper_handle == ""
    live = resolve_editable_nfb_source_profile(source, profile=profiles[0])
    assert live.source_sha256 == sha256(source.read_bytes()).hexdigest()
    assert live.upper_handle
    assert live.upper_size_mm == pytest.approx((57., 96.))
