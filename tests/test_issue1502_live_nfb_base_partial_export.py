# -*- coding: utf-8 -*-
"""#1502: live current Set/Bay -> real NFB physical plate PART_ONLY DXF."""
from dataclasses import replace
from types import SimpleNamespace
from hashlib import sha256
import csv

import ezdxf
import pytest

from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source
from ae_engine.receiving_nfb_ui1b_bridge import (
    NfbVerifiedDraftSubmission, _nfb_config_proof_sha256,
)
from ae_engine.receiving_nfb_lower_fixing_source import resolve_unique_nfb_lower_reference_handle
from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope
from ae_engine.receiving_nfb_persistence import normalize_nfb_config
from gui_modules.application.receiving_nfb_base_partial_export_action import (
    export_verified_receiving_nfb_base_plate,
)
from tests.test_issue1502_existing_base_nfb_assembly import (
    _snapshot, _upper_base, _native_original, _verified,
)


def _live(tmp_path, pattern="LEFT_FLAT_SIDE"):
    source, profile, lower = _native_original(tmp_path)
    native = inspect_nfb_dxf_source(source)
    old = _verified(profile)
    verified = replace(old, render_data=SimpleNamespace(metadata={
        **old.render_data.metadata,
        "nfb_source_handle": profile.source_sha256 + ":" + profile.upper_handle,
        "nfb_profile_revision": profile.revision,
    }))
    snapshot = _snapshot()
    plate = _upper_base(pattern)
    snapshot["receiving_base_plate"] = {
        "pattern": pattern, "height": float(plate.height),
        "shrink_top": plate.shrink_top, "shrink_bottom": plate.shrink_bottom,
        "shrink_left": plate.shrink_left, "shrink_right": plate.shrink_right,
        "bend": plate.bend,
    }
    holes = [{
        "physical_hole_id": physical_id, "model_filename": profile.indexed_filename,
        "manual_x_state": "CONFIRMED", "manual_x_mm": x,
        "datum_revision": "TEST_1502", "datum_snapshot": {"w": 800, "t": 2},
        "layer_count": count, "slot_index": slot,
        "rotation_deg": rotation,
    } for physical_id, x, count, slot, rotation in verified.verified_hole_locations]
    config = normalize_nfb_config({
        "layer_count": 1, "holes": holes, "source_sha256": profile.source_sha256,
    })
    # The real #1497 inner-door scope intentionally DOES NOT claim a base ID.
    # The physical plate owner must instead be verified from the live spec.
    scope = NfbPhysicalScope(
        set_id="setA", bay_id="bayA", version_id="v1", submitted=True,
        inner_door_part_id="inner_door:upper:panel",
    )
    layout = {"sets": [{"stable_id": "setA", "switch_brand": "士林", "bays": [{
        "stable_id": "bayA", "nfb_config_submitted": True, "nfb_config": config,
    }]}]}
    bundle = NfbVerifiedDraftSubmission(
        set_index=0, bay_index=0, version_id="v1", config=config, scope=scope,
        source_inventory=native, verified_door=verified,
        readiness=SimpleNamespace(can_submit=True),
        source_path=str(source), snapshot_at_verification=snapshot,
        bay_at_verification=layout["sets"][0]["bays"][0],
        config_sha256_at_verification=_nfb_config_proof_sha256(config),
    )
    index = tmp_path / "switch-index.csv"
    index.write_text("index\n", encoding="utf-8")
    profile_path = tmp_path / "來源輪廓索引.csv"
    with profile_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["brand","indexed_filename","source_sha256","upper_handle",
                         "upper_width_mm","upper_height_mm","source_alias_status","revision"])
        writer.writerow(["士林", profile.indexed_filename, profile.source_sha256,
                         profile.upper_handle, *profile.upper_size_mm,
                         profile.source_alias_status, profile.revision])
    return SimpleNamespace(
        bundle=bundle, layout=layout, snapshot=snapshot, plate=plate,
        index=index, profile=profile_path, original=source, lower=lower,
    )


@pytest.mark.parametrize("pattern", (
    "LEFT_FLAT_SIDE", "CENTER_DOUBLE_SIDE_FOLD", "RIGHT_FLAT_SIDE",
))
def test_submitted_nfb_to_existing_base_is_real_part_only_dxf(pattern, tmp_path):
    v = _live(tmp_path, pattern)
    assert resolve_unique_nfb_lower_reference_handle(v.original, profile=(
        __import__("ae_engine.receiving_nfb_cutting_manufacturing",
                   fromlist=["read_nfb_runtime_source_profiles_csv"])
        .read_nfb_runtime_source_profiles_csv(v.profile)[0]
    )) == v.lower
    root = tmp_path / "part"
    root.mkdir()
    filename, result = export_verified_receiving_nfb_base_plate(
        v.bundle, layout=v.layout, current_snapshot=v.snapshot, base_spec=v.plate,
        output_directory=root, index_path=v.index, profile_path=v.profile,
    )
    assert result.manufacturing_ready is False
    assert result.render_data.metadata["receiving_base_ear_weld_z_verified"] is False
    assert result.render_data.metadata["receiving_base_ear_mount_center_world_xy_mm"] == (
        result.render_data.metadata["receiving_base_nfb_row_center_world_xy_mm"]
    )
    doc = ezdxf.readfile(filename)
    actual = tuple(x for x in doc.modelspace() if x.dxftype() == "CIRCLE"
                   and x.dxf.layer == "CUTTING")
    # The synthetic sample has DISTINCT upper Color30 circles and native
    # lower NFB screws: 8 upper + 8 lower, NOT one alias group. Do not
    # silently discard one group or force it to 8 to make a test green.
    assert len(actual) == 16
    from ae_engine.sheetmetal_drawing import CirclePrimitive
    cutting = tuple(p for p in result.render_data.scene.primitives
                    if isinstance(p, CirclePrimitive) and p.layer == "CUTTING")
    lower = tuple(p for p in cutting
                  if p.source_type == "NFB_LOWER_NATIVE_FIXING_CIRCLE")
    assert len(cutting) == 16 and len(lower) == 8
    assert len(tuple(root.glob("*.dxf"))) == 1
    assert sha256(v.original.read_bytes()).hexdigest() == v.bundle.source_inventory.source_sha256


@pytest.mark.parametrize("mutation,reason", (
    ("no_plate", "not configured"),
    ("wrong_ear", "physical spec differs"),
    ("wrong_saved_config", "owner/config does not match"),
    ("source_corrupt", "source bytes changed"),
    ("no_submitted", "owner/config does not match"),
    ("wrong_source_profile", "profile is missing or changed"),
    ("missing_original", None),
))
def test_reject_changed_nfb_source_or_plate_before_manufacturing(tmp_path, mutation, reason):
    v = _live(tmp_path)
    root = tmp_path / "part"
    root.mkdir()
    spec, config = v.plate, v.snapshot
    if mutation == "no_plate":
        config = {**v.snapshot, "receiving_base_plate": None}
    elif mutation == "wrong_ear":
        spec = replace(spec, height=spec.height + 1)
    elif mutation == "wrong_saved_config":
        v.layout["sets"][0]["bays"][0]["nfb_config"] = {"holes": []}
    elif mutation == "source_corrupt":
        v.original.write_bytes(v.original.read_bytes() + b"corruption")
    elif mutation == "no_submitted":
        v.layout["sets"][0]["bays"][0]["nfb_config_submitted"] = False
    elif mutation == "wrong_source_profile":
        v.profile.write_text(v.profile.read_text(encoding="utf-8-sig").replace(
            v.bundle.source_inventory.source_sha256, "a" * 64
        ), encoding="utf-8")
    elif mutation == "missing_original":
        v.original.unlink()
    with pytest.raises((ValueError, OSError), match=reason):
        export_verified_receiving_nfb_base_plate(
            v.bundle, layout=v.layout, current_snapshot=config, base_spec=spec,
            output_directory=root, index_path=v.index, profile_path=v.profile,
        )
    assert list(root.iterdir()) == []


def test_lower_source_ambiguous_reference_fails_without_world_placement(tmp_path):
    v = _live(tmp_path)
    doc = ezdxf.readfile(v.original)
    doc.modelspace().add_lwpolyline(
        [(-45, 40), (45, 40), (45, 60), (-45, 60)],
        close=True, dxfattribs={"color": 3},
    )
    doc.saveas(v.original)
    # Profile SHA follows the changed native file for this ambiguity test.
    profile = replace(
        __import__("ae_engine.receiving_nfb_cutting_manufacturing",
                   fromlist=["read_nfb_runtime_source_profiles_csv"])
        .read_nfb_runtime_source_profiles_csv(v.profile)[0],
        source_sha256=sha256(v.original.read_bytes()).hexdigest(),
    )
    with pytest.raises(ValueError, match="absent or ambiguous"):
        resolve_unique_nfb_lower_reference_handle(v.original, profile=profile)


def test_sha_identical_numbered_download_keeps_single_source_identity(tmp_path):
    """#1497 explicitly permits a browser-numbered ORIGINAL file copy."""
    v = _live(tmp_path)
    copied = tmp_path / (v.original.stem + "(1).dxf")
    copied.write_bytes(v.original.read_bytes())
    bundle = replace(v.bundle, source_path=str(copied))
    directory = tmp_path / "export-numbered"
    directory.mkdir()
    path, composed = export_verified_receiving_nfb_base_plate(
        bundle, layout=v.layout, current_snapshot=v.snapshot, base_spec=v.plate,
        output_directory=directory, index_path=v.index, profile_path=v.profile,
    )
    assert composed.projection.source_sha256 == v.bundle.source_inventory.source_sha256
    assert ezdxf.readfile(path).modelspace() is not None
    assert copied.read_bytes() == v.original.read_bytes()
