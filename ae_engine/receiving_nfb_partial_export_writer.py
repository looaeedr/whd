# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""#1501 live, source-bound partial DXF writer for verified NFB inner door.

The manifest is not a persisted permit. Every invocation regenerates true
#1497 CUTTING from current physical geometry and original source bytes,
matches canonical saved NFBConfig, and derives #1498 actual part readiness
before the first output file is written. Other MFG-2 parts are not emitted
by this entrypoint and must each earn their own geometry verification.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from .manufacturing_api import save_part_render_data_dxf
from .manufacturing_render_data import PartRenderData
from .receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from .receiving_nfb_cutting_preflight import NfbExistingCuttingClaim
from .receiving_nfb_dxf_source import inspect_nfb_dxf_source
from .receiving_nfb_export_manifest import (
    NfbActualPart,NfbPartialExportManifest,INNER_DOOR,
    derive_nfb_partial_export_manifest,
)
from .receiving_nfb_manufacturing_release import (
    NfbConfiguredInnerDoorHole,configured_nfb_inner_door_render_data,
)
from .receiving_nfb_part_readiness import NfbPhysicalScope


def export_current_nfb_inner_door_partial_dxf(
    snapshot:Mapping[str,object],
    inner_door_id:str,
    output_path:str|Path,
    *,
    saved_bay:Mapping[str,object],
    set_brand:str,
    physical_scope:NfbPhysicalScope,
    actual_parts:Sequence[NfbActualPart],
    holes:Sequence[NfbConfiguredInnerDoorHole],
    index_path:str|Path,
    source_path:str|Path,
    profile:NfbUpperSourceProfile,
    existing_claims:Sequence[NfbExistingCuttingClaim]=(),
    existing_render_data:PartRenderData|None=None,
    overwrite:bool=False,
)->tuple[str,NfbPartialExportManifest]:
    """Generate only an actually READY inner-door partial DXF.

    Revalidate from CURRENT snapshot, source, canonical saved Bay and
    physical scope. A ready indicator in the UI or a previously derived
    manifest never substitutes for live verification. CHECK/grouping is
    NOT handled here; the caller must pass the independently verified
    part into the canonical CHECK geometry-equivalence grouping stage.
    """
    if not isinstance(physical_scope,NfbPhysicalScope):
        raise TypeError("NFB partial DXF needs current physical scope")
    if physical_scope.submitted is not True:
        raise ValueError("NFB partial DXF requires submitted configuration")
    parts=tuple(actual_parts)
    if (not parts or sum(p.part_id==physical_scope.inner_door_part_id
                         and p.role==INNER_DOOR for p in parts)!=1):
        raise ValueError("NFB actual physical inner-door part absent/ambiguous")
    # It is important to manufacture from freshly inspected real geometry:
    # no use of stale NfbVerifiedDraftSubmission caches or UI badges.
    ready=configured_nfb_inner_door_render_data(
        snapshot,inner_door_id,holes=holes,index_path=index_path,
        source_path=source_path,profile=profile,
        existing_claims=existing_claims,
        existing_render_data=existing_render_data,
    )
    if ready.part_id!=physical_scope.inner_door_part_id:
        raise ValueError("NFB current inner-door physical part ID mismatch")
    inventory=inspect_nfb_dxf_source(source_path)
    manifest=derive_nfb_partial_export_manifest(
        scope=physical_scope,actual_parts=parts,
        saved_bay=saved_bay,set_brand=set_brand,
        source_inventory=inventory,verified_inner_door=ready,
        source_path=source_path,
    )
    manifest.require_export((ready.part_id,),partial=True)
    # Existing production serializer owns overwrite behavior and CUTTING
    # layer rules. The caller cannot request held plates with this API.
    path=save_part_render_data_dxf(
        ready.render_data,output_path,overwrite=overwrite,
    )
    return path,manifest
