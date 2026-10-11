# -*- coding: utf-8 -*-
"""#1502 split actual three-drawing base source for reference, not machining.

The user-supplied DXF has three separate NFB base patterns across the sheet:
left/right FLAT, middle BENT. Export native-entity *reference previews* with
original source handles and DXF arcs untouched. There is NO BEND entity
certification or verified physical NFB hole-to-base UV registration yet;
these DXFs must not pass production's CUTTING release.

Does not rewrite an original, does not create an upper/lower old BasePlate,
does not automatically guess a variant from NFB count/version.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import ezdxf

from .receiving_nfb_actual_base_source import (
    NfbActualBaseSource,
    inspect_receiving_nfb_actual_base,
    link_actual_base_to_verified_inner_door_nfb,
)
from .receiving_nfb_actual_base_contours import (
    audit_receiving_nfb_actual_base_contours,
)
from .receiving_nfb_manufacturing_release import NfbValidatedInnerDoorRender

REFERENCE_ONLY = "NFB_ACTUAL_BASE_NATIVE_SOURCE_PREVIEW_NOT_MFG2_DXF"
_FILENAMES = {
    "LEFT_FLAT": "受電箱底板_左_無折彎_來源預覽_禁止下料.dxf",
    "CENTER_BENT": "受電箱底板_中_有折彎_來源預覽_禁止下料.dxf",
    "RIGHT_FLAT": "受電箱底板_右_無折彎_來源預覽_禁止下料.dxf",
}
_TOL = 1e-4


@dataclass(frozen=True)
class NfbActualBaseSourcePreview:
    pattern_key: str
    source_sha256: str
    output_path: str
    original_handles: tuple[str, ...]
    native_loop_count: int
    unresolved_white_handle_count: int
    status: str = REFERENCE_ONLY
    manufacturing_ready: bool = False


def _annotation_x(e):
    kind = e.dxftype()
    if kind == "TEXT":
        return float(e.dxf.insert.x)
    if kind == "POINT":
        return float(e.dxf.location.x)
    if kind == "DIMENSION":
        return float(e.dxf.get("text_midpoint",e.dxf.defpoint).x)
    raise ValueError("NFB source unclassified annotation cannot be exported safely")


def _pattern_for_entity(e, patterns):
    kind=e.dxftype()
    if kind=="LINE":
        x0=min(float(e.dxf.start.x),float(e.dxf.end.x))
        x1=max(float(e.dxf.start.x),float(e.dxf.end.x))
    elif kind in ("ARC","CIRCLE"):
        from ezdxf import bbox
        bounds=bbox.extents([e])
        if not bounds.has_data:
            raise ValueError("NFB original base circle/arc has no bounds")
        x0,x1=float(bounds.extmin.x),float(bounds.extmax.x)
    else:
        x0=x1=_annotation_x(e)
    matches=[
        p.key for p in patterns
        if p.x_bounds_native[0]-_TOL<=x0<=x1<=p.x_bounds_native[1]+_TOL
    ]
    if len(matches)!=1:
        raise ValueError("NFB original base entity does not belong to exactly one pattern")
    return matches[0]


def split_actual_nfb_base_reference_dxf(
    source_path: str | Path,
    output_directory: str | Path, *,
    pattern_key: str | None = None,
    verified_inner_door: NfbValidatedInnerDoorRender | None = None,
    index_path: str | Path | None = None,
) -> tuple[NfbActualBaseSourcePreview, ...]:
    """Copy exact native source graph into independent *unreleased* DXFs.

    An explicit single selected option may be linked to the existing
    verified inner-door configuration. No independent X or fold position is
    accepted. A full 3-option reference split needs no selected NFB version,
    but is never registered as manufactured parts.
    """
    source_path=Path(source_path)
    options={} if index_path is None else {"index_path":index_path}
    source=inspect_receiving_nfb_actual_base(source_path,**options)
    audited=audit_receiving_nfb_actual_base_contours(
        source_path,source=source,index_path=index_path,
    )
    audits={v.pattern_key:v for v in audited}
    if pattern_key is not None:
        if pattern_key not in _FILENAMES:
            raise ValueError("NFB real base pattern option invalid")
        if verified_inner_door is None:
            raise ValueError("NFB selected real base requires verified inner-door NFB")
        linked=link_actual_base_to_verified_inner_door_nfb(
            source,pattern_key,verified_inner_door=verified_inner_door,
        )
        if linked.manufacturing_ready:
            raise ValueError("NFB source preview cannot become production")
        keys=(pattern_key,)
    else:
        if verified_inner_door is not None:
            raise ValueError("NFB verified NFB owner must select one explicit base pattern")
        keys=tuple(_FILENAMES)
    destination=Path(output_directory)
    if not destination.exists() or not destination.is_dir():
        raise ValueError("NFB output reference directory must already exist")
    outputs={key:destination/_FILENAMES[key] for key in keys}
    if any(path.exists() for path in outputs.values()):
        raise FileExistsError("NFB base source previews cannot overwrite existing file")
    fingerprint=sha256(source_path.read_bytes()).hexdigest()
    if fingerprint!=source.sha256:
        raise ValueError("NFB source bytes changed during reference export")
    doc=ezdxf.readfile(source_path)
    by_key={key:[] for key in _FILENAMES}
    for e in doc.modelspace():
        key=_pattern_for_entity(e,source.patterns)
        by_key[key].append(str(e.dxf.handle).upper())
    all_handles={h for part in by_key.values() for h in part}
    source_handles={str(e.dxf.handle).upper() for e in doc.modelspace()}
    if (all_handles!=source_handles
            or sum(len(x) for x in by_key.values())!=len(source_handles)):
        raise ValueError("NFB source split has missing/duplicated original entities")
    previews=[]
    written=[]
    try:
        for key in keys:
            target=outputs[key]
            # Re-read the untouched original for each variant so no part ever
            # borrows another pattern's geometry or inherits a previous edit.
            fresh=ezdxf.readfile(source_path)
            model=fresh.modelspace()
            allowed=set(by_key[key])
            for item in tuple(model):
                if str(item.dxf.handle).upper() not in allowed:
                    model.delete_entity(item)
            if target.exists():
                raise FileExistsError("NFB preview target appeared during export")
            fresh.saveas(target)
            written.append(target)
            roundtrip=ezdxf.readfile(target)
            observed={str(item.dxf.handle).upper() for item in roundtrip.modelspace()}
            if observed!=allowed or len(roundtrip.modelspace())!=len(allowed):
                raise ValueError("NFB preview DXF lost/duplicated original source entities")
            a=audits[key]
            previews.append(NfbActualBaseSourcePreview(
                pattern_key=key,source_sha256=source.sha256,
                output_path=str(target),
                original_handles=tuple(by_key[key]),
                native_loop_count=len(a.closed_loop_handle_groups),
                unresolved_white_handle_count=len(a.unresolved_white_source_handles),
            ))
        if sha256(source_path.read_bytes()).hexdigest()!=source.sha256:
            raise ValueError("NFB base source changed while saving reference DXFs")
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return tuple(previews)
