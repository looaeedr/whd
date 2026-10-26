# -*- coding: utf-8 -*-
"""#1504 AC51/SWT30: ephemeral exact-source status after verified V5 export.

The source-model selector itself is ALWAYS a preview. Only an actually
committed, exact Set/Bay/physical part scope whose existing paired DXF export
has just succeeded may display 可製造（內門）. This is PART_ONLY, not MFG-2.
This module never writes a DXF, sets a manufacturing flag or caches a claim
inside a .p6fold file. It refuses stale CSV, edits, deleted/changed DXFs,
cross-Bay use and fabricated legacy-model approvals.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

PREVIEW = "僅預覽"
VERIFIED_DOOR = "可製造（內門）｜僅本連已驗證的成對部分 DXF"


@dataclass(frozen=True)
class VerifiedCurrentV5PairScope:
    scope_digest: str
    paths: tuple[str, ...]
    file_digests: tuple[str, ...]
    models: tuple[str, ...]
    hole_ids: tuple[str, ...]
    # No full-cabinet, PAD, independent EAR or other width-row authorizations.
    manufacturing_scope: str = "VERIFIED_CURRENT_CSV_PAIR_PART_ONLY"


def _source_digest(snapshot: Mapping[str, object]):
    from .receiving_nfb_committed_final_scene import _submitted_csv_holes
    from .receiving_nfb_numeric_catalog import brand_csv_path

    if not isinstance(snapshot, Mapping):
        raise ValueError("NFB current source snapshot required")
    source = _submitted_csv_holes(snapshot)
    if not source or snapshot.get("nfb_config_submitted") is not True:
        raise ValueError("NFB current Bay not submitted")
    door_id, holes = source
    if not holes or any(
        not str(getattr(h, "model_ref", "")).startswith("nfbv5:")
        for h in holes
    ):
        raise ValueError("NFB current numeric V5 source only")
    from .receiving_nfb_model_identity import parse_numeric_model_ref
    brands = set()
    models = []
    physical_ids = []
    for hole in holes:
        parsed = parse_numeric_model_ref(hole.model_ref)
        if parsed is None:
            raise ValueError("NFB invalid V5 model")
        brands.add(parsed[0])
        models.append(hole.model_ref)
        physical_ids.append(hole.physical_hole_id)
    # Snapshot contains the actual stored Set/Bay/version/NFBConfig, W/H/D/T,
    # inner door features and layout. Unsupported values fail closed rather
    # than silently omitting geometry-dependent inputs from the fingerprint.
    try:
        encoded = json.dumps(
            snapshot, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        brand_bytes = tuple(
            (brand, sha256(brand_csv_path(brand).read_bytes()).hexdigest())
            for brand in sorted(brands)
        )
    except (TypeError, ValueError, OSError, UnicodeError) as exc:
        raise ValueError("NFB physical scope cannot be fingerprinted") from exc
    data = json.dumps(
        (door_id, brand_bytes, encoded.decode("utf-8")), ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(data).hexdigest(), tuple(models), tuple(physical_ids)


def verified_pair_after_export(snapshot, receipt):
    """Accept only the actual just-returned V5 pair writer's receipt.

    This is an operator disclosure, not the export authorization function.
    The writer already reverified real physical FinalScene, DXF roundtrip and Q
    before returning. No state is stored in the source snapshot or project.
    """
    from gui_modules.application.receiving_nfb_pair_partial_export_action import (
        NfbCsvPairedPartOnlyDxf, NfbCsvTwoTierPartOnlyDxf,
    )

    if not isinstance(receipt, (NfbCsvPairedPartOnlyDxf, NfbCsvTwoTierPartOnlyDxf)):
        raise ValueError("NFB status requires native current V5 export receipt")
    scope_digest, models, hole_ids = _source_digest(snapshot)
    if tuple(receipt.source_hole_ids) != hole_ids:
        raise ValueError("NFB actual export hole identity drift")
    if isinstance(receipt, NfbCsvPairedPartOnlyDxf):
        paths = (receipt.inner_door_path, receipt.base_plate_path)
        keys = (receipt.check_q_key,)
    else:
        paths = (receipt.inner_door_path, *receipt.base_plate_paths)
        keys = tuple(receipt.check_q_keys)
    if (len(paths) not in (2, 3) or len(keys) != len(paths)-1
            or any(not isinstance(k, str) or len(k) != 64 for k in keys)
            or len(set(paths)) != len(paths)):
        raise ValueError("NFB actual pair DXF/Q receipt incomplete")
    from ezdxf import readfile
    hashes = []
    for source in paths:
        path = Path(source)
        if path.suffix.lower() != ".dxf" or not path.is_file():
            raise ValueError("NFB actual exported DXF missing")
        try:
            doc = readfile(path)
            if not any(e.dxf.layer == "CUTTING" for e in doc.modelspace()):
                raise ValueError("NFB saved DXF no actual CUTTING")
            hashes.append(sha256(path.read_bytes()).hexdigest())
        except (OSError, ValueError, UnicodeError) as exc:
            raise ValueError("NFB actual exported DXF re-open failed") from exc
    return VerifiedCurrentV5PairScope(
        scope_digest, tuple(map(str, paths)), tuple(hashes), models, hole_ids,
    )


def scoped_current_v5_selector_status(snapshot, selected_model, evidence=None):
    """Live recomputation: never promote one model or nominal pitch globally."""
    if not isinstance(evidence, VerifiedCurrentV5PairScope):
        return PREVIEW
    try:
        current_digest, models, hole_ids = _source_digest(snapshot)
        if (evidence.manufacturing_scope != "VERIFIED_CURRENT_CSV_PAIR_PART_ONLY"
                or current_digest != evidence.scope_digest
                or models != evidence.models or hole_ids != evidence.hole_ids
                or selected_model not in models
                or len(evidence.paths) != len(evidence.file_digests)):
            return PREVIEW
        for name, expected in zip(evidence.paths, evidence.file_digests):
            path = Path(name)
            if not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected:
                return PREVIEW
        return VERIFIED_DOOR
    except (TypeError, ValueError, KeyError, OSError, UnicodeError):
        return PREVIEW
