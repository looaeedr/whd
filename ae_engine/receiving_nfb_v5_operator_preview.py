# -*- coding: utf-8 -*-
"""#2517 Receiving NFB CSV-V5 physical trial source and display safety owner.

An editable GUI may request a read-only preview, but it cannot decide
physical BasePlate source identities, sheet geometry, or false manufacturing
approval. Canonical source validation and unapproved trials stay in Engine.
No trial here authorizes an actual DXF, welded EAR, PAD, or whole-cabinet MFG-2.
"""
from __future__ import annotations

from .receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorTrial, STATUS as DOOR_STATUS,
)
from .receiving_nfb_v5_actual_base_screws import (
    NfbV5ActualBaseScrewTrial, STATUS as BASE_STATUS,
)


def require_receiving_nfb_v5_inner_door_trial_preview(trial):
    """Return ONLY current unapproved trial geometry for read-only painting."""
    if (not isinstance(trial, NfbV5ConfiguredInnerDoorTrial)
            or trial.status != DOOR_STATUS or trial.manufacturing_ready
            or trial.render_data.metadata.get("nfb_trial_export_approved") is not False):
        raise ValueError("V5 內門只能繪製尚未驗證的真實 FinalScene 試作")
    return trial.render_data


def require_receiving_nfb_v5_base_trial_preview(trial):
    """Never let an approved/fake MFG-2 base masquerade as a pending trial."""
    if (not isinstance(trial, NfbV5ActualBaseScrewTrial)
            or trial.status != BASE_STATUS or trial.manufacturing_ready
            or trial.render_data.metadata.get("nfb_trial_export_approved") is not False
            or trial.render_data.metadata.get("nfb_base_mfg2_release_approved") is not False):
        raise ValueError("V5 底板只能顯示原實體 EAR 工作面未核准試作")
    return trial.render_data


def preview_receiving_nfb_v5_real_base_sources(
    snapshot, inner_door_id, *, door, configured_holes, root_base_spec,
):
    """One physical Base Plate source per NFB tier, without spoofing part IDs.

    The same #1502 Assembly PartSpec builder now supplies the source for 3D
    and this GUI. A not-yet-submitted Bay can still preview real INNER-DOOR
    CSV holes, but may not claim to have installed multi-tier Base Plates.
    """
    from ae_engine.contracts import BasePlatePartSpec
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    from ae_engine.receiving_nfb_layer_physical_parts import (
        source_receiving_nfb_tier_base_specs,
    )
    from ae_engine.receiving_nfb_v5_live_base_preview import (
        preview_v5_on_existing_receiving_base,
        preview_v5_on_existing_receiving_tier_bases,
    )

    entries = tuple(configured_holes)
    if not entries or not isinstance(root_base_spec, BasePlatePartSpec):
        raise ValueError("V5 底板尚未取得實際來源 PartSpec")
    counts = {row.layer_count for row in entries}
    if len(counts) != 1:
        raise ValueError("V5 不同 NFB 層數不可共用同一片實體底板")
    if counts == {1}:
        return (preview_v5_on_existing_receiving_base(
            snapshot, inner_door_id, door=door,
            configured_holes=entries, base_spec=root_base_spec,
        ),)
    if counts != {2}:
        raise ValueError("V5 尚未配置合法的實體 NFB 層數")
    # Root is only a SOURCE contract, never rename/copy it as another tier.
    current = receiving_base_plate_values(snapshot)
    if (current is None or root_base_spec.physical_id != "base_plate"
            or root_base_spec.features
            or any(abs(float(actual) - float(expected)) > 1e-6
                   for actual, expected in (
                       (root_base_spec.width, snapshot["w"]),
                       (root_base_spec.height, current["h"]),
                       (root_base_spec.thickness, snapshot["t"]),
                       (root_base_spec.bend, current["base_plate_bend"]),
                       (root_base_spec.shrink_left, current["base_plate_shrink_left"]),
                       (root_base_spec.shrink_right, current["base_plate_shrink_right"]),
                       (root_base_spec.shrink_top, current["base_plate_shrink_top"]),
                       (root_base_spec.shrink_bottom, current["base_plate_shrink_bottom"]),
                   ))
            or root_base_spec.receiving_bend_pattern != current["receiving_bend_pattern"]):
        raise ValueError("V5 原始實體底板與目前 Set/Bay/尺寸來源不同步")
    specs = source_receiving_nfb_tier_base_specs(snapshot)
    return preview_v5_on_existing_receiving_tier_bases(
        snapshot, inner_door_id,
        door=door, configured_holes=entries, base_specs=specs,
    )

