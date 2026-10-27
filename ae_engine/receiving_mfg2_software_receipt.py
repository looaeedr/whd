# -*- coding: utf-8 -*-
"""#1490 software MFG-2 release: physical-source-complete whole-cabinet DXF.

A source-certified cabinet drawing package is independently inspectable.
No NC machine type, factory weld workmanship or metadata ready flag is inferred.
The existing physical CSV, FinalScene, contact, bend and DXF safety gates
remain authoritative and this adds the *entire inventory* acceptance gate.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping


RECEIPT_FILENAME = "WHD_1490_MFG2_SOFTWARE_RECEIPT.json"
RECEIPT_KEY = "__whd_1490_software_mfg2__"
RECEIPT_SCHEMA = "WHD_NFB_WHOLE_CABINET_SOURCE_MFG2_SOFTWARE_V1"


def require_complete_cabinet_physical_selection(original_geometry, selected_geometry):
    from .manufacturing_export import resolved_physical_render_parts

    original = tuple(resolved_physical_render_parts(original_geometry))
    selected = tuple(resolved_physical_render_parts(selected_geometry))
    original_ids = tuple(key for key, _ in original)
    selected_ids = tuple(key for key, _ in selected)
    if (not original or len(set(original_ids)) != len(original_ids)
            or len(set(selected_ids)) != len(selected_ids)):
        raise ValueError("RECEIVING_MFG2_DUPLICATE_OR_EMPTY_PHYSICAL_INVENTORY")
    if set(original_ids) != set(selected_ids):
        missing = sorted(set(original_ids) - set(selected_ids))
        extra = sorted(set(selected_ids) - set(original_ids))
        raise ValueError(
            "RECEIVING_MFG2_WHOLE_CABINET_MISSING_PHYSICAL_SHEETS:"
            + json.dumps({"missing": missing, "extra": extra}, ensure_ascii=False)
        )
    for part in tuple(original_geometry.parts or ()):
        if getattr(part, "placement", None) == "standalone":
            raise ValueError("RECEIVING_MFG2_WHOLE_CABINET_STANDALONE_PART")
    return tuple(sorted(original_ids))


def stage_whole_cabinet_mfg2_receipt(
    staged_path: Path, *, snapshot: Mapping, original_physical_ids: tuple[str, ...],
    output_rows, formed_ear_ids, pad_ids, staged_dxfs,
) -> dict:
    """Make a sha256-linked receipt from fully *saved and reopened* real DXFs.

    Called only after the existing authenticated BEND/CUTTING/MARKING/Z
    preflights, and within the same directory transaction as the DXF sheets.
    """
    from .receiving_nfb_committed_final_scene import _submitted_csv_holes

    pair = _submitted_csv_holes(snapshot)
    if not pair or not pair[1]:
        raise ValueError("RECEIVING_MFG2_CURRENT_SUBMITTED_CSV_REQUIRED")
    if (set(staged_dxfs) !=
            set(key for key, _filename, _render in output_rows)
            | set(formed_ear_ids) | set(pad_ids)):
        raise ValueError("RECEIVING_MFG2_DXF_PHYSICAL_OWNER_SET_DRIFT")
    rows = []
    for part_id, file in sorted(staged_dxfs.items()):
        file = Path(file)
        if not file.is_file() or file.suffix.lower() != ".dxf":
            raise ValueError("RECEIVING_MFG2_MISSING_REAL_DXF:" + part_id)
        import ezdxf
        modelspace = ezdxf.readfile(str(file)).modelspace()
        layers = {}
        for entity in modelspace:
            name = entity.dxf.layer
            layers[name] = layers.get(name, 0) + 1
        if not layers.get("CUTTING"):
            raise ValueError("RECEIVING_MFG2_MISSING_CUTTING:" + part_id)
        rows.append({
            "physical_id": part_id,
            "filename": file.name,
            "sha256": sha256(file.read_bytes()).hexdigest(),
            "layers": dict(sorted(layers.items())),
            "entity_count": len(modelspace),
            "quantity": 1,
        })
    if len(rows) != len({r["filename"] for r in rows}):
        raise ValueError("RECEIVING_MFG2_DUPLICATED_DXF_FILENAME")
    pin = sha256(json.dumps(
        snapshot.get("nfb_config"), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()
    payload = {
        "schema": RECEIPT_SCHEMA,
        "status": "SOFTWARE_WHOLE_CABINET_DXF_SOURCE_CERTIFIED",
        "meaning": "MFG2 software geometry and DXF; not factory equipment approval",
        "source": {
            "nfb_config_sha256": pin,
            "submitted_current_csv_v5_hole_count": len(pair[1]),
            "model": snapshot.get("model"),
            "dimensions_mm": {k: float(snapshot[k]) for k in ("w", "h", "d")},
            "thickness_mm": float(snapshot["t"]),
        },
        "original_cabinet_physical_ids": list(original_physical_ids),
        "formed_ear_ids": sorted(formed_ear_ids),
        "verified_pad_ids": sorted(pad_ids),
        "output_dxf_count": len(rows),
        "sheet_quantity": sum(row["quantity"] for row in rows),
        "files": rows,
        "nc_machine_format_certified": False,
        "factory_welding_workmanship_certified": False,
        "generic_unverified_manufacturing_export_unlocked": False,
    }
    staged_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if json.loads(staged_path.read_text(encoding="utf-8")) != payload:
        raise ValueError("RECEIVING_MFG2_RECEIPT_READBACK_MISMATCH")
    return payload
