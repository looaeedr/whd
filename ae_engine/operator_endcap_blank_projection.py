# -*- coding: utf-8 -*-
"""Read-only legacy operator EndCap/baseline projections owned by Engine.

The baseline-first main-window summary and known-Vault Fold defaults retain
their existing presentation semantics. Neither API authorizes manufacturing.
"""
from __future__ import annotations

from collections.abc import Mapping

from . import ae
from .cabinet_types import policy as cabinet_family_policy


def project_operator_endcap_blank_dimensions(
    values: Mapping[str, object], *, baseline_model: str = "",
) -> tuple[float, float]:
    """Return the existing main-window EndCap W/D display values.

    Committed Fold profiles must still use the authoritative FinalScene;
    this function is only the legacy no-profile summary fallback.
    """
    if baseline_model:
        geom = ae.get_stretched_end_cap_data(
            baseline_model, values["w"], values["h"], values["d"], values["t"],
            FW_val=values["fw"], is_tail=False,
        )
        return float(geom.params["total_width"]), float(geom.params["total_depth"])
    return (
        float(ae.calculate_y_width(
            values["yl1"], values["yr1"], values["w"], values["t"],
        )),
        float(ae.calculate_y_depth(
            values["ytop1"], values["ybottom1"], values["d"],
            values["t"], values["fw"],
        )),
    )


def read_operator_baseline_fold_defaults(
    model_name: str, *, thickness: float,
) -> dict[str, dict[str, float] | None]:
    """Read known-family baseline defaults for operator controls only.

    Missing Door baseline leaves existing editor values intact. If a known
    Door DXF exists but fails to parse, retain the previous UI's four display
    defaults while leaving the EndCap read failure visible to the caller.
    """
    t = float(thickness)
    geom = ae.get_stretched_end_cap_data(
        model_name, 500, 500, 150, t, FW_val=None, is_tail=False,
    )
    p = geom.params
    endcap = {
        key: float(p[key])
        for key in ("yl1", "yr1", "ytop1", "ybottom1", "fw")
    }
    door = None
    if ae.has_baseline_part(model_name, "門.dxf"):
        try:
            material_fw = cabinet_family_policy.door_material_frame_width(
                model_name, frame_width=endcap["fw"], thickness=t,
            )
            pd = ae.get_stretched_door_data(
                model_name, 500, 500, t, material_fw,
            ).params
            door = {
                key: float(pd[key])
                for key in ("door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b")
            }
        except Exception:
            # Historical operator-control fallback, not certified DXF values.
            door = {
                "door_fold_l": 19.0, "door_fold_r": 15.0,
                "door_fold_t": 15.0, "door_fold_b": 15.0,
            }
    return {"endcap": endcap, "door": door}
