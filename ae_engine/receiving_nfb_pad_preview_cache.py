# -*- coding: utf-8 -*-
"""PAD GUI preview cache fingerprint: live CSV, tooling, real base geometry.

The 2D/3D source files may change *without* a snapshot edit. This is only a
cache invalidation key, never evidence of physical manufacture certification.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256


def pad_preview_source_fingerprint(snapshot, assembly_parts) -> str:
    if not isinstance(snapshot, Mapping):
        raise TypeError("PAD_PREVIEW_REQUIRES_SNAPSHOT")
    h=sha256()
    h.update(repr(snapshot).encode("utf-8"))
    config=snapshot.get("nfb_config")
    holes=config.get("holes") if isinstance(config, Mapping) else ()
    from .receiving_nfb_model_identity import parse_numeric_model_ref
    from .receiving_nfb_numeric_catalog import brand_csv_path
    from .receiving_nfb_pad_generator import TOOLING_RELATIVE_PATH
    from pathlib import Path

    brands=set()
    for row in holes if isinstance(holes,(tuple,list)) else ():
        if not isinstance(row,Mapping):
            continue
        reference=parse_numeric_model_ref(row.get("model_filename"))
        if reference is not None:
            brands.add(reference[0])
    if brands:
        tooling_path=Path(__file__).resolve().parents[1] / TOOLING_RELATIVE_PATH
        for name,path in [("PAD_SHARED_TOOLING",tooling_path)]+[
                ("NFB_CSV:"+brand,brand_csv_path(brand)) for brand in sorted(brands)]:
            h.update(name.encode("utf-8"))
            h.update(sha256(path.read_bytes()).digest())
    for part in assembly_parts:
        key=str(getattr(part,"part_key",""))
        if not key.startswith("base_plate"):
            continue
        data=getattr(part,"render_data",None)
        if data is None:
            raise ValueError("PAD_PREVIEW_PARENT_RENDER_DATA_MISSING")
        material=getattr(data,"material",None)
        if material is None or material.is_empty:
            raise ValueError("PAD_PREVIEW_PARENT_MATERIAL_MISSING")
        h.update(key.encode("utf-8"))
        h.update(repr(tuple(getattr(part,"offset",()) or ())).encode("utf-8"))
        h.update(sha256(material.wkb).digest())
        h.update(repr(tuple(getattr(data,"fold_guides",()) or ())).encode("utf-8"))
        h.update(repr(getattr(data,"unfolded_topology",None)).encode("utf-8"))
        h.update(repr(getattr(data,"metadata",None)).encode("utf-8"))
    return h.hexdigest()
