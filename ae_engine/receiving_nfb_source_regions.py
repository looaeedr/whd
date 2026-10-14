# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""#1502 read-only native DXF upper/lower source-group evidence, NOT MFG-2.

The source handles come from operator-verified profile DATA. A split plane
is derived only when actual upper/lower closed references have a strict
geometric gap, with every real source entity wholly on one side. Colors
are preserved WITH region membership; Color212 cannot be mapped to a
single plate just because of its ACI. Lower source is deferred by v1.4.
No UV translation, CUTTING, MARKING, CHECK Q or approval is emitted.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path

from .receiving_nfb_dxf_source import (
    NfbSourceInventory, inspect_nfb_dxf_source,
)

UPPER="UPPER_SOURCE"
LOWER="LOWER_SOURCE"
OBSERVED="SOURCE_GROUPS_OBSERVED_NOT_MANUFACTURING_APPROVED"
DEFERRED="LOWER_PAD_GEOMETRY_DEFERRED"


@dataclass(frozen=True)
class NfbNativeSourceRegion:
    region: str
    source_sha256: str
    reference_handle: str
    entity_handles: tuple[str,...]
    effective_color_counts: tuple[tuple[int,int],...]
    region_status: str
    manufacturing_ready: bool = False


@dataclass(frozen=True)
class NfbNativeSourceRegions:
    indexed_filename: str
    source_sha256: str
    separation_y_mm: float
    upper: NfbNativeSourceRegion
    lower: NfbNativeSourceRegion
    status: str = OBSERVED
    manufacturing_ready: bool = False


def _rect_bounds(entity):
    import ezdxf
    from ezdxf import bbox
    bounds=bbox.extents([entity])
    if not bounds.has_data:
        raise ValueError("NFB original source entity has no supported bounds")
    a,b,c,d=(float(bounds.extmin.x),float(bounds.extmin.y),
             float(bounds.extmax.x),float(bounds.extmax.y))
    if (not all(isfinite(v) for v in (a,b,c,d))
            or a>c or b>d):
        raise ValueError("NFB original entity has invalid physical bounds")
    return a,b,c,d


def inspect_nfb_original_source_regions(
    source_path:str|Path,*,indexed_filename:str,expected_sha256:str,
    upper_reference_handle:str,lower_reference_handle:str,
    expected_upper_width_mm:float|None=None,
    expected_upper_height_mm:float|None=None,
)->NfbNativeSourceRegions:
    """Fail closed if the two native groups cannot be distinguished.

    No per-model hardcoded Y/ACI offsets; data-only handle and SHA mapping.
    Does not assume the LOWER group's geometry belongs in BASE/MIDDLE UV.
    """
    import ezdxf

    source=Path(source_path)
    if not indexed_filename.lower().endswith(".dxf"):
        raise ValueError("NFB source group requires indexed DXF basename")
    if not isinstance(expected_sha256,str) or len(expected_sha256)!=64:
        raise ValueError("NFB group requires exact original SHA256")
    data=source.read_bytes()
    digest=sha256(data).hexdigest()
    if digest!=expected_sha256.lower():
        raise ValueError("NFB source group original DXF SHA does not match")
    inventory=inspect_nfb_dxf_source(source)
    if (inventory.source_sha256!=digest or inventory.diagnostics
            or inventory.unresolved_color_entities):
        raise ValueError("NFB group has unresolved source geometry/colors")
    document=ezdxf.readfile(source)
    entities=tuple(document.modelspace())
    # An INSERT or unhandled entity is not silently reduced to unrelated
    # geometry. A separate future verified virtual-entity group resolver
    # is required for such original files.
    if (len(entities)!=len(inventory.entities)
            or any(e.dxftype() not in {
                "LINE","ARC","CIRCLE","LWPOLYLINE","POLYLINE"
            } for e in entities)):
        raise ValueError("NFB original groups contain unresolved INSERT/entities")
    by_handle={e.dxf.handle:e for e in entities}
    if (not upper_reference_handle or not lower_reference_handle
            or upper_reference_handle==lower_reference_handle
            or upper_reference_handle not in by_handle
            or lower_reference_handle not in by_handle):
        raise ValueError("NFB upper/lower source anchors absent or ambiguous")
    upper=by_handle[upper_reference_handle]
    lower=by_handle[lower_reference_handle]
    if (upper.dxftype()!="LWPOLYLINE" or not upper.closed
            or upper.dxf.get("color",256)!=150
            or lower.dxftype()!="LWPOLYLINE" or not lower.closed
            or lower.dxf.get("color",256)!=3):
        raise ValueError("NFB physical upper/lower reference must be typed closed source")
    ux0,uy0,ux1,uy1=_rect_bounds(upper)
    lx0,ly0,lx1,ly1=_rect_bounds(lower)
    if expected_upper_width_mm is not None and abs(ux1-ux0-expected_upper_width_mm)>1e-5:
        raise ValueError("NFB upper source width does not match actual profile")
    if expected_upper_height_mm is not None and abs(uy1-uy0-expected_upper_height_mm)>1e-5:
        raise ValueError("NFB upper source height does not match actual profile")
    if not uy0>ly1:
        raise ValueError("NFB upper/lower original groups have no proven gap")
    split=(uy0+ly1)/2.0
    joined=[]
    for entity in entities:
        _x0,y0,_x1,y1=_rect_bounds(entity)
        if y0>split:
            group=UPPER
        elif y1<split:
            group=LOWER
        else:
            raise ValueError("NFB original entity crosses upper/lower group split")
        joined.append((group,entity.dxf.handle))
    color_by_handle={x.handle_path:x.effective_color_aci for x in inventory.entities}
    if (len(color_by_handle)!=len(entities)
            or any(handle not in color_by_handle for _,handle in joined)):
        raise ValueError("NFB source ancestry cannot be matched to all native handles")

    def pack(group,reference,status):
        ids=tuple(handle for region,handle in joined if region==group)
        counts=Counter(color_by_handle[h] for h in ids)
        if reference not in ids or not ids:
            raise ValueError("NFB source group reference not in its own region")
        return NfbNativeSourceRegion(
            region=group,source_sha256=digest,
            reference_handle=reference,entity_handles=ids,
            effective_color_counts=tuple(sorted(counts.items())),
            region_status=status,
        )

    return NfbNativeSourceRegions(
        indexed_filename=indexed_filename,source_sha256=digest,
        separation_y_mm=split,
        upper=pack(UPPER,upper_reference_handle,OBSERVED),
        lower=pack(LOWER,lower_reference_handle,DEFERRED),
    )
