# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""#1497: verified WHD W800x3 X datum -> actual source-verified inner-door CUTTING.

The W800/T2 upper-1100 three-unit X positions are determined by the live
WHD-generated 723 mm CUTTING and real assembly placement (#1494). Callers
still explicitly configure every physical hole identity, Y layer and rotation,
and must provide the original DXF, exact SHA-bound source profile and index.
No customer DXF outer boundary sets the manufactured X datum.

This adapter does not add a second hole renderer or another authorization
registry. It delegates actual holes, legacy claims, Q16 atomic checking,
physical Y, FinalScene and export to #1497's existing manufacturing API.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .manufacturing_api import save_part_render_data_dxf
from .manufacturing_render_data import PartRenderData
from .receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from .receiving_nfb_cutting_preflight import NfbExistingCuttingClaim
from .receiving_nfb_manufacturing_release import (
    NfbConfiguredInnerDoorHole,
    NfbValidatedInnerDoorRender,
    configured_nfb_inner_door_render_data,
)
from .receiving_nfb_x_projection import (
    W800_THREE_DATUM_REVISION,
    resolve_w800_three_whd_x,
    reverse_w800_three_whd_x,
)

W800_THREE_CUTTING_ADAPTER_REVISION = "WHD-1497-W800X3-CANONICAL-X-TO-CUTTING-V1"


@dataclass(frozen=True)
class NfbW800ThreeRow:
    """One operator-configured vertical layer of THREE actual NFB units.

    There is no default unit identity or guessed single-unit centering.
    Slot index 0/1/2 is horizontal; layer_index 0/1 is vertical (#1495).
    """

    layer_index: int
    physical_hole_ids: tuple[str, str, str]
    rotations_deg: tuple[int, int, int] = (0, 0, 0)


def _three_hole_rows(
    snapshot: Mapping[str, object],
    inner_door_id: str,
    rows: Sequence[NfbW800ThreeRow],
) -> tuple[NfbConfiguredInnerDoorHole, ...]:
    given = tuple(rows)
    if len(given) not in (1, 2):
        raise ValueError("NFB W800x3 requires one or two configured layers")
    if any(type(row) is not NfbW800ThreeRow for row in given):
        raise TypeError("NFB W800x3 requires typed row configurations")
    if tuple(row.layer_index for row in given) != tuple(range(len(given))):
        raise ValueError("NFB W800x3 layer order must be contiguous from zero")

    known_ids: set[str] = set()
    prepared: list[NfbConfiguredInnerDoorHole] = []
    for row in given:
        if (len(row.physical_hole_ids) != 3 or len(row.rotations_deg) != 3):
            raise ValueError("NFB W800x3 row must contain three actual slots")
        for horizontal_slot in range(3):
            hole_id = row.physical_hole_ids[horizontal_slot]
            angle = row.rotations_deg[horizontal_slot]
            if (not isinstance(hole_id, str) or not hole_id.strip()
                    or hole_id in known_ids):
                raise ValueError("NFB W800x3 physical hole ids must be unique and nonempty")
            if type(angle) is not int or angle not in (0, 90, 180, 270):
                raise ValueError("NFB W800x3 rotation must be 0/90/180/270")
            known_ids.add(hole_id)
            evidence = resolve_w800_three_whd_x(
                snapshot, inner_door_id, slot_index=horizontal_slot,
            )
            if evidence.revision != W800_THREE_DATUM_REVISION or (
                    reverse_w800_three_whd_x(
                        snapshot, inner_door_id, slot_index=horizontal_slot,
                        box_world_x_mm=evidence.box_world_x_mm,
                    ) != evidence.blank_x_from_cutting_left_mm):
                raise ValueError("NFB W800x3 physical X evidence revision/inverse mismatch")
            prepared.append(NfbConfiguredInnerDoorHole(
                physical_hole_id=hole_id,
                world_x_mm=evidence.box_world_x_mm,
                layer_count=len(given),
                slot_index=row.layer_index,
                rotation_deg=angle,
            ))
    return tuple(prepared)


def configured_w800_three_nfb_inner_door_render_data(
    snapshot: Mapping[str, object],
    inner_door_id: str,
    *,
    rows: Sequence[NfbW800ThreeRow],
    index_path: str | Path,
    source_path: str | Path,
    profile: NfbUpperSourceProfile,
    existing_claims: Sequence[NfbExistingCuttingClaim] = (),
    existing_render_data: PartRenderData | None = None,
) -> NfbValidatedInnerDoorRender:
    """Execute the actual #1497 source-verified CUTTING on WHD canonical 3-up X.

    Strictly requires W800/T2/top1100, a real physical inner-door part and
    complete three-slot operator configuration. The downstream manufacturer
    checks source identity/shape, Y, fold bounds, legacy owner and collisions
    for all slots atomically; failures cannot create partial output.
    """
    holes = _three_hole_rows(snapshot, inner_door_id, rows)
    return configured_nfb_inner_door_render_data(
        snapshot, inner_door_id, holes=holes,
        index_path=index_path, source_path=source_path, profile=profile,
        existing_claims=existing_claims,
        existing_render_data=existing_render_data,
    )


def save_w800_three_nfb_inner_door_dxf(
    snapshot: Mapping[str, object],
    inner_door_id: str,
    output_path: str | Path,
    *,
    rows: Sequence[NfbW800ThreeRow],
    index_path: str | Path,
    source_path: str | Path,
    profile: NfbUpperSourceProfile,
    existing_claims: Sequence[NfbExistingCuttingClaim] = (),
    existing_render_data: PartRenderData | None = None,
    overwrite: bool = False,
) -> str:
    """Create one real CUTTING DXF only after ALL configured holes pass."""
    verified = configured_w800_three_nfb_inner_door_render_data(
        snapshot, inner_door_id, rows=rows,
        index_path=index_path, source_path=source_path, profile=profile,
        existing_claims=existing_claims,
        existing_render_data=existing_render_data,
    )
    return save_part_render_data_dxf(
        verified.render_data, output_path, overwrite=overwrite,
    )
