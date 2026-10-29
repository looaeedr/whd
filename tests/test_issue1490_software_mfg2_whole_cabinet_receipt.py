# -*- coding: utf-8 -*-
"""#1490: signed source-certified software MFG2, not NC machine-code output."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import ezdxf
import pytest

from ae_engine.receiving_ear_side_manufacturing_marking import (
    with_verified_receiving_ear_side_markings,
)
from ae_engine.receiving_fixed_plate_formed_manufacturing import (
    save_verified_receiving_formed_fixing_plate_bundle,
)
from ae_engine.receiving_mfg2_software_receipt import (
    RECEIPT_SCHEMA, RECEIPT_FILENAME,
)
from tests.test_issue1502_single_button_full_csv_receiving_export import _prepare


def _source(two_tiers=False):
    source, actual = _prepare(two_tiers)
    dim = tuple(float(source[k]) for k in ("w", "h", "d"))
    marked = with_verified_receiving_ear_side_markings(
        source, actual, dimensions=dim, sheet_thickness=float(source["t"]),
    )
    return source, actual, marked, dim


def _certify(source, actual, marked, dimensions, dest):
    return save_verified_receiving_formed_fixing_plate_bundle(
        source, actual, marked, dest, dimensions=dimensions,
        sheet_thickness=float(source["t"]),
        require_complete_cabinet_inventory=True,
        certify_software_mfg2=True,
    )


@pytest.mark.parametrize("two_tiers,pad_count,ear_count", [
    (False, 1, 2),
    (True, 0, 4),
])
def test_whole_software_mfg2_source_proves_all_original_sheets_and_atomic_sha_receipt(
    tmp_path, two_tiers, pad_count, ear_count,
):
    source, original, marked, dimensions = _source(two_tiers)
    result = _certify(source, original, marked, dimensions, tmp_path / "cabinet")
    assert result.software_mfg2_receipt_path
    assert result.scope == "SOFTWARE_MFG2_WHOLE_CABINET_DXF_SOURCE_CERTIFIED"
    file = Path(result.software_mfg2_receipt_path)
    assert file.name == RECEIPT_FILENAME and file.exists()
    data = json.loads(file.read_text(encoding="utf-8"))
    assert data["schema"] == RECEIPT_SCHEMA
    assert data["status"] == "SOFTWARE_WHOLE_CABINET_DXF_SOURCE_CERTIFIED"
    assert len(data["verified_pad_ids"]) == pad_count
    assert len(data["formed_ear_ids"]) == ear_count
    assert data["nc_machine_format_certified"] is False
    assert data["factory_welding_workmanship_certified"] is False
    assert data["generic_unverified_manufacturing_export_unlocked"] is False
    dxf = dict(result.output_paths)
    assert len(data["files"]) == len(dxf) == data["output_dxf_count"]
    assert data["sheet_quantity"] == len(dxf)
    assert len(list(file.parent.glob("*.dxf"))) == len(dxf)
    original_ids = set(data["original_cabinet_physical_ids"])
    assert original_ids.issubset(set(dxf))
    assert set(data["formed_ear_ids"]).issubset(set(dxf))
    assert set(data["verified_pad_ids"]).issubset(set(dxf))
    for sheet in data["files"]:
        local = file.parent / sheet["filename"]
        assert local.is_file() and dxf[sheet["physical_id"]] == str(local)
        assert sha256(local.read_bytes()).hexdigest() == sheet["sha256"]
        assert len(ezdxf.readfile(str(local)).modelspace()) == sheet["entity_count"]
        assert sheet["layers"]["CUTTING"] > 0


def test_missing_installed_head_is_not_mfg2_even_with_nfb_door_base_and_sides(tmp_path):
    source, actual, marked, dims = _source()
    selected = replace(marked, parts=tuple(
        part for part in marked.parts if part.part_key != "head"
    ))
    target = tmp_path / "missing_head"
    with pytest.raises(ValueError, match="RECEIVING_MFG2_WHOLE_CABINET_MISSING_PHYSICAL_SHEETS"):
        _certify(source, actual, selected, dims, target)
    assert not target.exists()


def test_cannot_claim_software_mfg2_in_part_only_selected_mode(tmp_path):
    source, actual, marked, dims = _source()
    target = tmp_path / "partial"
    with pytest.raises(ValueError, match="RECEIVING_MFG2_SOFTWARE_REQUIRES_STRICT_INVENTORY"):
        save_verified_receiving_formed_fixing_plate_bundle(
            source, actual, marked, target, dimensions=dims,
            sheet_thickness=float(source["t"]),
            require_complete_cabinet_inventory=False,
            certify_software_mfg2=True,
        )
    assert not target.exists()


def test_receipt_stage_failure_rolls_back_all_dxfs_and_receipt(tmp_path, monkeypatch):
    import ae_engine.receiving_mfg2_software_receipt as receipt

    def refuse(*args, **kwargs):
        raise ValueError("SOFTWARE_MFG2_RECEIPT_STAGE_FAIL_CLOSED")

    monkeypatch.setattr(receipt, "stage_whole_cabinet_mfg2_receipt", refuse)
    source, actual, marked, dims = _source()
    target = tmp_path / "failed_receipt"
    with pytest.raises(ValueError, match="SOFTWARE_MFG2_RECEIPT_STAGE_FAIL_CLOSED"):
        _certify(source, actual, marked, dims, target)
    assert not list(target.glob("*.dxf"))
    assert not (target / RECEIPT_FILENAME).exists()


def test_stale_real_base_z_never_creates_mfg2_receipt_or_dxfs(tmp_path):
    source, original, marked, dims = _source()
    broken = replace(original, parts=tuple(
        replace(p, offset=(p.offset[0], p.offset[1], p.offset[2] + 2))
        if p.part_key == "base_plate" else p
        for p in original.parts
    ))
    target = tmp_path / "stale_base"
    with pytest.raises(ValueError):
        _certify(source, broken, marked, dims, target)
    assert not target.exists()
