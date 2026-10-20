# -*- coding: utf-8 -*-
"""#1502: live Receiving Set/Bay CSV Base Plate PART_ONLY GUI adapter.

The operator sees a CSV-specific action even when there is no old NFB DXF
session and no obsolete separately-entered BasePlate pattern. One selected
physical Bay, one NFB tier, one actual installed BasePlate, one saved DXF.
Manufacturing checks are performed again by the CSV-first engine writer.
"""
from __future__ import annotations

from collections.abc import Mapping

from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_equivalence import ManufacturingParameters
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_nfb_v5_part_only_manufacturing import (
    _current_single_tier_csv_holes,
    export_verified_csv_v5_single_base_part_only,
)


def _unique_upper_inner_door(snapshot):
    upper = tuple(p for p in derive_inner_door_panels(snapshot)
                  if str(p.cell_key).split(":")[-1] == "0")
    if len(upper) != 1:
        raise ValueError("CSV 底板需要唯一的上層實體內門")
    return upper[0].inner_door_id


def csv_base_part_only_ready(snapshot):
    """Read-only source eligibility, never a cached GUI manufacturing approval."""
    try:
        door = _unique_upper_inner_door(snapshot)
        _current_single_tier_csv_holes(snapshot, door)
        if receiving_base_plate_values(snapshot) is None:
            return False
    except (ValueError, TypeError, KeyError, IndexError, OSError):
        return False
    return True


def export_current_receiving_csv_base_part_from_gui(
    snapshot, *, base_spec: BasePlatePartSpec,
    assembly_parts, output_directory,
):
    """Use the same installed physical-part FinalScene the 2D/3D UI shows.

    Old DXF proof and saved manual base-plate fields are not inputs. No
    attempt is made to guess a right-side variant or an unconfirmed NFB X.
    The single sheet has Q=1; Set/Bay are the true stable version-scope
    identifiers, not an invented candidate/version record.
    """
    if not isinstance(snapshot, Mapping):
        raise TypeError("CSV 底板輸出需要當前 Set/Bay 實體資料")
    door = _unique_upper_inner_door(snapshot)
    _holes, set_id, bay_id = _current_single_tier_csv_holes(snapshot, door)
    if receiving_base_plate_values(snapshot) is None:
        raise ValueError("CSV 底板來源板型無法唯一決定")
    parts = tuple(assembly_parts or ())
    bases = tuple(p for p in parts if getattr(p, "part_key", None) == "base_plate")
    if len(bases) != 1:
        raise ValueError("CSV 底板不在目前已解析的實體組合體中，或板件重複")
    selected = bases[0]
    if getattr(selected, "placement", None) == "standalone":
        raise ValueError("CSV 底板必須取自已裝配的實體板件")
    # Only this one sheet is output. The manufacturing equivalence process
    # label describes the DXF output, NOT a fabricated steel/laser order.
    parameters = ManufacturingParameters(
        material="UNSPECIFIED_SHEET",
        thickness=float(snapshot["t"]),
        process="CUTTING_DXF",
    )
    return export_verified_csv_v5_single_base_part_only(
        snapshot, door, base_spec=base_spec,
        existing_base_render_data=selected.render_data,
        output_directory=output_directory,
        version_id=f"{set_id}/{bay_id}",
        quantity=1,
        parameters=parameters,
        overwrite=False,
    )
