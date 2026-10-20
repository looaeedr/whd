# -*- coding: utf-8 -*-
"""#1502 current committed CSV, no legacy source DXF, independent base PART_ONLY."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.manufacturing_equivalence import ManufacturingParameters
from ae_engine.receiving_nfb_v5_part_only_manufacturing import (
    export_verified_csv_v5_single_base_part_only,
)
from tests.test_issue1502_existing_base_nfb_assembly import _snapshot
from tests.test_issue1502_source_derived_center_base import (
    _source_snapshot, _spec,
)


PARAMS = ManufacturingParameters("steel", 2., "laser")


def _current(*, width=800., model_second="3P125SN"):
    snap = _snapshot()
    source = _source_snapshot(width=width, shallow=model_second)
    snap.update({
        "w": width,
        "nfb_config_submitted": True,
        "_receiving_runtime_selection": deepcopy(source["_receiving_runtime_selection"]),
    })
    config = source["nfb_config"]
    for n, row in enumerate(config["holes"]):
        row.update({
            "layer_count": 1, "layer_index": 0, "slot_index": n,
            "manual_x_mm": (-150. if n == 0 else 150.),
            "manual_x_state": "CONFIRMED",
            "datum_revision": "WHD_SOURCE_CONFIRMED",
            "datum_snapshot": {"w": width, "inner_door": "upper"},
            "rotation_deg": 0,
        })
    snap["nfb_config"] = config
    source["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(config)
    snap["receiving_layout"] = source["receiving_layout"]
    return snap


def _export(snap, root, *, spec=None):
    return export_verified_csv_v5_single_base_part_only(
        snap, "upper", base_spec=spec or _spec(snap),
        output_directory=root, version_id="V1", quantity=3,
        parameters=PARAMS,
    )


def test_current_csv_center_part_only_exports_real_screws_ear_slots_and_bends(tmp_path):
    snap = _current()
    assert "receiving_base_plate" not in snap
    receipt = _export(snap, tmp_path / "approved")
    assert receipt.part_id == "base_plate"
    assert receipt.quantity == 3
    assert receipt.source_hole_ids == ("nfb:0", "nfb:1")
    assert len(receipt.check_q_key) == 64
    path = Path(receipt.path)
    assert path.exists()
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    screws = [v for v in msp
              if v.dxftype() == "CIRCLE" and v.dxf.layer == "CUTTING"]
    native = [v for v in msp
              if v.dxftype() == "LWPOLYLINE"
              and v.dxf.layer == "CUTTING" and v.closed]
    bends = [v for v in msp if v.dxf.layer == "BEND"]
    assert len(screws) == 8 and len(native) == 5
    assert bends
    from ae_engine.receiving_nfb_numeric_catalog import model_spec
    expected = sorted(
        round(model_spec("士林", model).screw_diameter_mm / 2., 6)
        for model in ("2P400", "3P125SN") for _ in range(4)
    )
    assert sorted(round(v.dxf.radius, 6) for v in screws) == expected
    # One independently checked sheet, not a full-cabinet DXF batch.
    assert len(list(path.parent.glob("*.dxf"))) == 1


def test_one_source_flat_left_variant_uses_current_csv_without_old_nfb_dxf(tmp_path):
    snap = _current()
    # Keep the original single 400 switch only: uniquely source-matched LEFT.
    snap["nfb_config"]["holes"] = snap["nfb_config"]["holes"][:1]
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    receipt = _export(snap, tmp_path / "left")
    msp = ezdxf.readfile(receipt.path).modelspace()
    assert len([v for v in msp
                if v.dxftype() == "CIRCLE" and v.dxf.layer == "CUTTING"]) == 4
    assert receipt.source_hole_ids == ("nfb:0",)


@pytest.mark.parametrize("fault,expected", (
    ("unsubmitted", "SUBMITTED"),
    ("unconfirmed_x", "NOT_CONFIRMED"),
    ("mismatched_bay", "IDENTITY_DRIFT"),
    ("wrong_variant", "PARTSPEC_VS_LIVE_SOURCE_MISMATCH"),
))
def test_wrong_current_source_or_unproven_world_x_produces_no_dxf(
    tmp_path, fault, expected,
):
    snap = _current()
    spec = _spec(snap)
    if fault == "unsubmitted":
        snap["nfb_config_submitted"] = False
    elif fault == "unconfirmed_x":
        snap["nfb_config"]["holes"][0]["manual_x_state"] = "RECONFIRM_REQUIRED"
        snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
            snap["nfb_config"]
        )
    elif fault == "mismatched_bay":
        snap["_receiving_runtime_selection"]["bay_id"] = "OTHER"
    else:
        spec = replace(spec, shrink_left=spec.shrink_left + 5.)
    root = tmp_path / fault
    with pytest.raises(ValueError, match=expected):
        _export(snap, root, spec=spec)
    assert not root.exists()


def test_csv_source_change_prevents_part_only_output(tmp_path):
    snap = _current()
    original_spec = _spec(snap)
    snap["nfb_config"]["holes"][1]["model_filename"] = "nfbv5:士林:3P500BAD"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    out = tmp_path / "source-changed"
    with pytest.raises((ValueError, KeyError)):
        _export(snap, out, spec=original_spec)
    assert not out.exists()


def test_saved_dxf_verification_failure_does_not_commit_any_file(monkeypatch, tmp_path):
    import ae_engine.receiving_nfb_v5_part_only_manufacturing as export_module
    snap = _current()
    monkeypatch.setattr(export_module, "verify_saved_part_render_data_dxf",
                        lambda *_args, **_kw: SimpleNamespace(ok=False))
    root = tmp_path / "reimport-failed"
    with pytest.raises(ValueError, match="SAVED_DXF_GEOMETRY_VERIFICATION_FAILED"):
        _export(snap, root)
    assert not list(root.glob("*.dxf"))


def test_existing_output_is_never_overwritten_implicitly(tmp_path):
    snap = _current()
    root = tmp_path / "one-version"
    first = _export(snap, root)
    before = Path(first.path).read_bytes()
    with pytest.raises(FileExistsError):
        _export(snap, root)
    assert Path(first.path).read_bytes() == before
