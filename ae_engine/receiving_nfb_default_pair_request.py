# -*- coding: utf-8 -*-
"""Project a committed Receiving Bay into the EXISTING NFB pair Request.

No geometry is authored by the external caller. The original Engine inner
Door, BasePlate PartSpec, FinalScene resolver and verified paired exporter own
all manufactured CUTTING, mounting holes, folds and physical coordinates.
"""
from __future__ import annotations

from collections.abc import Mapping

from .cabinet_types.policy import derive_inner_door_panels
from .contracts import BasePlatePartSpec
from .manufacturing_contracts import (
    ManufacturingPartInput, ManufacturingResolveRequest,
)
from .receiving_base_plate_config import receiving_base_plate_values
from .receiving_layout import (
    normalize_receiving_layout, project_receiving_bay_legacy_aliases,
)
from .receiving_mode_session import fresh_receiving_mode
from .receiving_nfb_committed_final_scene import _submitted_csv_holes


def receiving_committed_nfb_pair_request_for_bay(
    layout: Mapping[str, object], *, set_index: int, bay_index: int,
    thickness_mm: object,
) -> ManufacturingResolveRequest:
    """One exact real Bay -> immutable original Door/BasePlate physical input.

    Do not accept caller-provided PartSpecs, hole X, transformed contours or
    cached CSV-cut scenes. A Bay with no confirmed NFB/inner-door source fails
    before request construction. Batch export still rechecks source and every
    independent DXF before the atomic commit.
    """
    normalized = normalize_receiving_layout(layout)
    if type(set_index) is not int or not 0 <= set_index < len(normalized["sets"]):
        raise ValueError("NFB_PAIR_REQUEST_SET_IDENTITY_INVALID")
    bays = normalized["sets"][set_index]["bays"]
    if type(bay_index) is not int or not 0 <= bay_index < len(bays):
        raise ValueError("NFB_PAIR_REQUEST_BAY_IDENTITY_INVALID")
    bay = bays[bay_index]
    state = bay.get("door_state")
    if (not isinstance(state, Mapping)
            or not state.get("inner_doors")
            or state.get("multi_door_enabled") is not True
            or not state.get("door_layout_columns")):
        raise ValueError("NFB_PAIR_REQUEST_REAL_INNER_DOOR_REQUIRED")
    seed = fresh_receiving_mode(
        "set_bay",
        {"w": bay["width"], "h": bay["height"], "d": bay["depth"]},
        thickness=thickness_mm,
    )
    seed["receiving_layout"] = normalized
    snapshot = project_receiving_bay_legacy_aliases(
        seed, set_index=set_index, bay_index=bay_index,
        validate_common=False,
    )
    verified = _submitted_csv_holes(snapshot)
    if not verified:
        raise ValueError("NFB_PAIR_REQUEST_CURRENT_PHYSICAL_X_NOT_APPROVED")
    inner = tuple(
        panel for panel in derive_inner_door_panels(snapshot)
        if panel.inner_door_id == verified[0]
        and str(panel.cell_key).split(":")[-1] == "0"
    )
    if len(inner) != 1:
        raise ValueError("NFB_PAIR_REQUEST_UPPER_INNER_DOOR_IDENTITY_INVALID")
    from .manufacturing_api import (
        build_inner_door_panel_render_data, build_part_render_data,
    )
    panel = inner[0]
    values = receiving_base_plate_values(snapshot)
    if values is None:
        raise ValueError("NFB_PAIR_REQUEST_PHYSICAL_BASE_SOURCE_MISSING")
    # The identical established BasePlatePartSpec factory input used by the
    # original NFB GUI source path. No independent geometry or X calculation.
    spec = BasePlatePartSpec(
        width=float(snapshot["w"]), height=float(values["h"]),
        thickness=float(snapshot["t"]),
        shrink_top=float(values["base_plate_shrink_top"]),
        shrink_bottom=float(values["base_plate_shrink_bottom"]),
        shrink_left=float(values["base_plate_shrink_left"]),
        shrink_right=float(values["base_plate_shrink_right"]),
        bend=float(values["base_plate_bend"]), model_name="受電箱",
        receiving_bend_pattern=values["receiving_bend_pattern"],
        receiving_nfb_depth_pair_mm=values["receiving_nfb_depth_pair_mm"],
        physical_id="base_plate",
    )
    return ManufacturingResolveRequest(
        input_snapshot=snapshot, settings={"t": snapshot["t"]},
        canonical_part_keys=(panel.stable_id, "base_plate"),
        parts=(
            ManufacturingPartInput(
                part_key=panel.stable_id,
                render_data=build_inner_door_panel_render_data(panel),
            ),
            ManufacturingPartInput(
                part_key="base_plate",
                render_data=build_part_render_data(spec),
                x_profile=(), y_profile=(),
            ),
        ),
        cabinet_model="受電箱",
    )
