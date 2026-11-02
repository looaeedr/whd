# -*- coding: utf-8 -*-
"""Engine-owned source witnesses for Receiving raw PartRenderData preview reuse.

These keys only select an existing *operator preview* raw material cache.
Every manufacturing result still goes through the authoritative Engine
resolver. No missing/changed DXF, unknown Feature or spoofed Family may
create a cache hit; no cached preview authorizes external export.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .baseline_source import baseline_source_fingerprint
from .cabinet_types import policy as family_policy
from .contracts import ManufacturingContext
from .manufacturing_contracts import manufacturing_fingerprint
from . import manufacturing_baseline_policy, receiving_frame_baseline


@dataclass(frozen=True)
class ReceivingRawSourceCacheTicket:
    kind: str
    signature: str
    source_paths: tuple[str, ...] = ()
    source_stamps: tuple = ()
    physical_part_id: str = ""
    baseline_model: str = ""


def receiving_raw_source_cache_kind(part_key, payload):
    """Only source-owned, active Receiving Bay physical sheets are eligible."""
    from .cabinet_types.policy import canonical_family_name
    if (not isinstance(payload, Mapping)
            or canonical_family_name(payload) != "受電箱"
            or payload.get("active_mode") != "set_bay"):
        return None
    key = str(part_key or "")
    if key.startswith("inner_door:") and key.endswith(":panel"):
        return "panel"
    if key.startswith("inner_door:") and key.endswith("_frame"):
        return "frame"
    if key.startswith("box_body:divider:"):
        return "divider"
    return None


def _source_stamp(path: Path):
    """Parser revision and exact source bytes both affect cache validity."""
    return str(path), baseline_source_fingerprint(path), sha256(path.read_bytes()).hexdigest()


def project_receiving_raw_source_cache_ticket(part_key, payload, *, typed_part=None):
    """Return a read-only canonical cache key with source proof or None.

    Frame/Divider typed_part is the existing public Engine-derived physical
    part returned by the legacy GUI compatibility callback. It is NOT trusted
    to approve manufacturing, only to identify an immutable raw preview.
    """
    kind = receiving_raw_source_cache_kind(part_key, payload)
    if kind is None:
        return None
    key = str(part_key or "")
    features = tuple(payload.get("features") or ())
    if kind == "panel":
        panels = family_policy.derive_inner_door_panels(dict(payload))
        panel = next((part for part in panels if part.stable_id == key), None)
        if panel is None:
            return None
        try:
            signature = manufacturing_fingerprint({
                "panel": panel, "features": features,
            })
        except (TypeError, ValueError, OverflowError):
            return None
        return ReceivingRawSourceCacheTicket(kind=kind, signature=signature,
                                            physical_part_id=key)
    if typed_part is None:
        return None
    if kind == "frame":
        if getattr(typed_part, "side", None) not in ("top", "left", "right"):
            return None
        source = receiving_frame_baseline.frame_source_file()
        try:
            witness = _source_stamp(source)
            signature = manufacturing_fingerprint({
                "frame": typed_part, "source": witness[1],
                "sha256": witness[2], "features": features,
            })
        except (OSError, TypeError, ValueError, OverflowError):
            return None
        return ReceivingRawSourceCacheTicket(
            kind=kind, signature=signature,
            source_paths=(str(source),), source_stamps=(witness,),
            physical_part_id=key,
        )
    model = family_policy.baseline_feature_model_name(typed_part.model_name)
    if not family_policy.divider_uses_endcap_6p4_shared_datum(typed_part.model_name):
        return None
    ctx = ManufacturingContext()
    required = tuple(
        manufacturing_baseline_policy._baseline_path(model, name, ctx)
        for name in ("中隔.dxf", "封頭尾.dxf")
    )
    if any(source is None for source in required):
        return None
    try:
        witnesses = tuple(_source_stamp(path) for path in required)
        signature = manufacturing_fingerprint({
            "divider": typed_part, "features": features,
            "sources": witnesses,
        })
    except (OSError, TypeError, ValueError, OverflowError):
        return None
    return ReceivingRawSourceCacheTicket(
        kind=kind, signature=signature,
        source_paths=tuple(str(path) for path in required),
        source_stamps=witnesses, physical_part_id=str(typed_part.stable_id),
        baseline_model=model,
    )


def receiving_raw_source_cache_entry_valid(ticket, material) -> bool:
    """Accept a source-backed cache entry only with unchanged original DXFs.

    This is a post-factory *raw material caching* condition, not a statement
    that production/CUTTING certification has been granted.
    """
    if not isinstance(ticket, ReceivingRawSourceCacheTicket):
        return False
    if ticket.kind == "panel":
        return True
    try:
        current = tuple(_source_stamp(Path(p)) for p in ticket.source_paths)
    except (OSError, ValueError, TypeError):
        return False
    if current != ticket.source_stamps:
        return False
    metadata = dict(getattr(material, "metadata", {}) or {})
    if ticket.kind == "frame":
        return (
            len(current) == 1
            and metadata.get("receiving_frame_source_sha256") == current[0][2]
            and metadata.get("receiving_frame_source_path") == current[0][0]
        )
    return (
        ticket.kind == "divider" and len(current) == 2
        and metadata.get("stable_id") == ticket.physical_part_id
        and metadata.get("baseline_feature_model") == ticket.baseline_model
        and metadata.get("endcap_shared_6p4_mother_rule") is not None
    )
