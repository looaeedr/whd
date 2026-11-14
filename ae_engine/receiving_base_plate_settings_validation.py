# -*- coding: utf-8 -*-
"""Source-verified Receiving Base Plate settings preflight in manufacturing Engine."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from .receiving_base_plate_config import receiving_base_plate_blank_dimensions


def validate_receiving_base_plate_settings(
    *, input_snapshot: dict, settings_values: Mapping, config: Mapping | None,
):
    """Validate physical plate and weld EAR slots before accepting operator state."""
    if not isinstance(input_snapshot, dict):
        raise ValueError("受電箱實體底板缺少可提交的專案狀態")
    from .cabinet_types.policy import canonical_family_name
    if canonical_family_name(input_snapshot) != "受電箱":
        raise ValueError("只有受電箱可選擇專用底板")
    if config is not None and not isinstance(config, Mapping):
        raise ValueError("受電箱底板配置必須是完整欄位")

    if config is not None:
        probe = dict(input_snapshot)
        for key in ("w", "t"):
            if key in settings_values:
                probe[key] = settings_values[key]
        probe["receiving_base_plate"] = dict(config)
        receiving_base_plate_blank_dimensions(probe)

        # Validate the true EAR mounting holes through their manufacturing
        # owner, BEFORE accepting a new pattern.  LEFT/RIGHT blanks cannot
        # silently reuse the CENTER fold's shrink dimensions.
        from ae_engine.sheetmetal_part_adapters import build_receiving_base_plate_result
        from ae_engine.ae import _receiving_base_weld_ear_mount_slots
        from ae_engine.sheetmetal_drawing import DrawingScene

        result = build_receiving_base_plate_result(
            w=float(probe["w"]), h=float(config["height"]), t=float(probe["t"]),
            shrink_top=float(config["shrink_top"]),
            shrink_bottom=float(config["shrink_bottom"]),
            shrink_left=float(config["shrink_left"]),
            shrink_right=float(config["shrink_right"]),
            bend=float(config["bend"]),
            pattern=str(config["pattern"]),
        )
        _receiving_base_weld_ear_mount_slots(
            DrawingScene(), result=result, pattern=str(config["pattern"]),
            box_w=float(probe["w"]), t=float(probe["t"]),
        )

    return None if config is None else deepcopy(dict(config))



def commit_receiving_base_plate_settings(
    *, input_snapshot: dict, settings_values: Mapping,
    config: Mapping | None, submit_geometry_update=None,
):
    """Commit one validated Receiving physical Base Plate selection atomically.

    The Engine alone owns the persisted physical selection key.  A caller
    may supply a zero-argument update notification; it is optional for
    headless clients and does not participate in manufacturing calculations.
    A failed notification restores the exact previous source object.
    """
    if submit_geometry_update is not None and not callable(submit_geometry_update):
        raise TypeError("RECEIVING_BASE_PLATE_UPDATE_NOTIFICATION_NOT_CALLABLE")
    accepted = validate_receiving_base_plate_settings(
        input_snapshot=input_snapshot, settings_values=settings_values,
        config=config,
    )
    existed = "receiving_base_plate" in input_snapshot
    previous = input_snapshot.get("receiving_base_plate")
    try:
        if accepted is None:
            input_snapshot.pop("receiving_base_plate", None)
        else:
            input_snapshot["receiving_base_plate"] = accepted
        if submit_geometry_update is not None:
            submit_geometry_update()
    except Exception:
        if existed:
            input_snapshot["receiving_base_plate"] = previous
        else:
            input_snapshot.pop("receiving_base_plate", None)
        raise
    return deepcopy(input_snapshot.get("receiving_base_plate"))



def project_operator_receiving_quantity_base_plate_settings(snapshot, config):
    """Produce verified COMPLETE Quantity Base Plate source with no mutation.

    The saved common physical box is the W/H/D owner, not the GUI Settings
    defaults or the synthetic one-Bay/root aliases. The caller may publish
    the detached source using its existing mode-navigation transaction.
    """
    from .cabinet_types.policy import canonical_family_name
    from .receiving_quantity_box import (
        normalize_common_box, positive_dimension, project_common_box,
        update_common_box,
    )
    from .receiving_quantity_versions import QuantityModel

    if (not isinstance(snapshot, Mapping)
            or canonical_family_name(snapshot) != "受電箱"
            or snapshot.get("active_mode") != "quantity"):
        raise ValueError("RECEIVING_QUANTITY_BASE_PLATE_MODE_REQUIRED")
    if ("receiving_quantity_box" not in snapshot
            or "quantity" not in snapshot):
        raise ValueError("RECEIVING_QUANTITY_BASE_PLATE_SOURCE_REQUIRED")

    # Fail closed on absent or invalid physical version / material thickness;
    # never reconstruct a manufactured source from a UI default seed.
    QuantityModel.from_payload(snapshot["quantity"])
    box = normalize_common_box(snapshot["receiving_quantity_box"])
    thickness = positive_dimension(snapshot.get("t"), "t")

    # Rebuild stale root W/H/D, synthetic Bay and runtime selection from the
    # one persisted Quantity common physical-box authority first.
    physical = project_common_box(snapshot)
    accepted = validate_receiving_base_plate_settings(
        input_snapshot=physical,
        settings_values={"w": box["w"], "t": thickness},
        config=config,
    )
    projected = update_common_box(
        physical, {"receiving_base_plate": accepted},
    )
    if (projected.get("receiving_base_plate") != accepted
            or projected["receiving_quantity_box"].get("receiving_base_plate")
            != accepted):
        raise ValueError("RECEIVING_QUANTITY_BASE_PLATE_PROJECTION_DRIFT")
    return projected
