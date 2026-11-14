"""Engine-owned physical BoxBody side/back Fold edit transaction.

The GUI submits operator Fold rows, the aggregate source and saved structure.
This owner alone maps physical child material rows into shared BoxBody source,
back-panel width compensation and right-side native traversal. It never
produces a cutting approval or a new DXF exporter.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from collections.abc import Mapping

from .box_body_editor_readback import (
    read_box_body_outside_dimensions,
    reverse_box_body_fold_traversal,
)
from .box_body_fold_profile import apply_outside_dimension_compensation
from .box_body_structure_state import (
    set_side_back_geometry,
    set_side_back_piece_profile,
)
from .operator_settings_transactions import normalize_operator_source_dimension


@dataclass(frozen=True)
class OperatorBoxBodyPieceFoldPlan:
    """Detached, fully validated source to apply through existing GUI services."""

    structure_state: dict[str, object]
    aggregate_profile: tuple[dict[str, object], ...]
    settings_values: dict[str, object] | None


def plan_operator_box_body_piece_fold_commit(
    part_key: str,
    profiles: Mapping[str, object],
    *,
    structure_state: Mapping[str, object],
    aggregate_profile: object,
    original_snapshot: Mapping[str, object],
    thickness: object,
    total_width: object,
    box_height: object,
) -> OperatorBoxBodyPieceFoldPlan:
    """Stage the existing side/back editor semantics without touching GUI state.

    Headless callers and the Phase6 physical-piece editor get the same plan.
    Only the Engine's preexisting structure and material Fold owners perform
    the physical decisions. Failed input rejects before any source write.
    """
    if type(part_key) is not str or part_key not in (
        "box_body:left_side", "box_body:back", "box_body:right_side",
    ):
        raise ValueError("BOX_BODY_PHYSICAL_PIECE_REQUIRED")
    if not isinstance(profiles, Mapping):
        raise ValueError("BOX_BODY_PIECE_FOLD_MAPPING_REQUIRED")
    if not isinstance(structure_state, Mapping):
        raise ValueError("BOX_BODY_STRUCTURE_MAPPING_REQUIRED")
    if not isinstance(original_snapshot, Mapping):
        raise ValueError("BOX_BODY_SOURCE_SNAPSHOT_REQUIRED")

    role = part_key.split(":", 1)[1]
    t = normalize_operator_source_dimension(thickness, field="t")
    w = normalize_operator_source_dimension(total_width, field="w")
    h = normalize_operator_source_dimension(box_height, field="h")
    rows = deepcopy(list(profiles.get("X") or ()))
    if not rows:
        raise ValueError("BOX_BODY_PIECE_X_FOLD_REQUIRED")
    if not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("BOX_BODY_PIECE_FOLD_ROW_MAPPING_REQUIRED")
    rows = [dict(row) for row in rows]

    # Validate the saved Fold through its original authoritative owner first.
    # In particular, malformed late Right/Back rows must not partially change
    # aggregate FW/D or the side/back structure state.
    stored_rows = reverse_box_body_fold_traversal(rows) if role == "right_side" else deepcopy(rows)
    for row in stored_rows:
        row.pop("phase6_ui_sign", None)
    structure = set_side_back_piece_profile(structure_state, role, stored_rows)

    aggregate = deepcopy(list(aggregate_profile or ()))
    if not all(isinstance(row, Mapping) for row in aggregate):
        raise ValueError("BOX_BODY_AGGREGATE_FOLD_ROW_MAPPING_REQUIRED")
    aggregate = [dict(row) for row in aggregate]
    by_key = {
        str(row.get("phase6_key") or ""): row
        for row in aggregate if str(row.get("phase6_key") or "")
    }
    piece_by_key = {
        str(row.get("phase6_key") or ""): row
        for row in rows if str(row.get("phase6_key") or "")
    }

    def copy_material_length(source_key, targets):
        source = piece_by_key.get(source_key)
        if source is None:
            return
        length = float(source["len"])  # already validated by set_side_back_piece_profile
        for target in targets:
            if target in by_key:
                by_key[target]["len"] = length

    if role == "left_side":
        copy_material_length("zl1", ("zl1",))
        copy_material_length("zl2", ("zl2",))
        copy_material_length("fw_left", ("fw_left", "fw_right"))
        copy_material_length("d_left", ("d_left", "d_right"))
    elif role == "right_side":
        copy_material_length("d_right", ("d_left", "d_right"))
        copy_material_length("fw_right", ("fw_left", "fw_right"))
        copy_material_length("zr2", ("zr2",))
        copy_material_length("zr1", ("zr1",))
    else:
        back = piece_by_key.get("back_panel")
        if back is not None:
            # Engine owns the unique material-W to physical back compensation.
            comp_t = max(0.0, (w - float(back["len"])) / t)
            structure = set_side_back_geometry(
                structure, back_width_comp_t=comp_t,
            )

    values = None
    if aggregate:
        apply_outside_dimension_compensation(aggregate, t)
        values = read_box_body_outside_dimensions(aggregate, original_snapshot)
        if role == "left_side":
            signed = piece_by_key.get("zl1")
            if signed is not None and "phase6_ui_sign" in signed:
                try:
                    sign = float(signed["phase6_ui_sign"])
                except (ValueError, TypeError, OverflowError) as exc:
                    raise ValueError("BOX_BODY_PIECE_UI_SIGN_INVALID") from exc
                if sign != sign or sign in (float("inf"), -float("inf")):
                    raise ValueError("BOX_BODY_PIECE_UI_SIGN_INVALID")
                values["zl1"] = (-1.0 if sign < 0.0 else 1.0) * abs(float(values["zl1"]))
        values["h"] = h

    return OperatorBoxBodyPieceFoldPlan(
        structure_state=structure,
        aggregate_profile=tuple(deepcopy(aggregate)),
        settings_values=None if values is None else deepcopy(values),
    )
