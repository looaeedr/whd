"""Isolated native consumer for the live source-bound CHECK API.

Do not store derived 2D or triangles here. Legacy V1/V2 remain separate.
"""
from collections.abc import Mapping
from copy import deepcopy

from ae_engine import manufacturing_api as engine

KEY = "v_miter_endcap_live_check_sources"
ATTR = "_v_miter_endcap_live_check_sources"
PARTS = frozenset(("head", "tail"))
CORNERS = frozenset(("bottom_left", "bottom_right", "top_left", "top_right"))


def validate_live_sources(snapshot):
    """Normalize storage shape only; no geometric replay during Open."""
    if KEY not in snapshot:
        return {}
    data = snapshot[KEY]
    if not isinstance(data, Mapping) or not set(data) <= PARTS:
        raise ValueError("ENDCAP_LIVE_V_PROJECT_PART_KEYS_INVALID")
    out = {}
    for part, records in data.items():
        if not isinstance(records, Mapping) or not set(records) <= CORNERS:
            raise ValueError("ENDCAP_LIVE_V_PROJECT_CORNER_KEYS_INVALID")
        for corner, record in records.items():
            # The Engine, not this GUI module, owns full record validation.
            row = engine.normalize_endcap_live_v_miter_check_snapshot(record)
            if row["corner_key"] != corner:
                raise ValueError("ENDCAP_LIVE_V_PROJECT_SOURCE_SCOPE_MISMATCH")
            out.setdefault(part, {})[corner] = row
    return out


def _selected_source(host, snapshot):
    part = host._current_manual_corner_part_key()
    if part not in PARTS:
        raise ValueError("V 型 CHECK 試算來源只適用於封頭／封尾")
    corner = host.manual_active_corner_var.get()
    pair = host._pair_for_corner_target(corner)
    if corner not in CORNERS or host.manual_corner_pair_same[part].get(pair):
        raise ValueError("請指定實際單一角落，不代選成對截角")
    spec, _context = host._fold_designer_part_spec_from_payload(part, snapshot)
    native = host._query_fold_designer_render_data(part, snapshot)
    if spec is None or native is None:
        raise ValueError("ENDCAP_LIVE_V_CURRENT_NATIVE_SOURCE_UNAVAILABLE")
    return part, corner, spec, native


def capture_current(host):
    snapshot = host._make_original_fold_designer_snapshot()
    part, corner, spec, native = _selected_source(host, snapshot)
    axes = engine.normalize_operator_v_miter_gui_first_bend_axes(
        snapshot.get("v_miter_gui_first_bend_axes"), snapshot.get("v_miter_gui_check_corners"),
    )
    axis = axes.get(part, {}).get(corner)
    if axis not in ("x", "y"):
        raise ValueError("請先指定目前角落的實體第一折")
    relief_var = getattr(host, "v_miter_relief_mode_var", None)
    kwargs = {"relief_mode": relief_var.get()} if relief_var is not None else {}
    row = engine.capture_endcap_live_v_miter_check_snapshot(
        spec, native, corner, first_bend_axis=axis, **kwargs,
    )
    records = deepcopy(getattr(host, ATTR, {}))
    records.setdefault(part, {})[corner] = row
    setattr(host, ATTR, validate_live_sources({KEY: records}))
    return row


def replay_current(host, snapshot):
    records = getattr(host, ATTR, {})
    if not records:
        return None  # old files keep read-only legacy V1/V2 metadata view
    part, corner, spec, native = _selected_source(host, snapshot)
    row = records.get(part, {}).get(corner)
    if row is None:
        raise ValueError("ENDCAP_LIVE_V_SOURCE_NOT_SAVED_FOR_SELECTION")
    return engine.replay_endcap_live_v_miter_check_snapshot(spec, native, row)
