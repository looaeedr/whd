"""Isolated native consumer for the live source-bound CHECK API.

Do not store derived 2D or triangles here. Legacy V1/V2 remain separate.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType

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


TAIL_BOTTOM_PAIR = ("bottom_left", "bottom_right")


@dataclass(frozen=True)
class _TailBottomPairReplayEnvelope:
    """One GUI View transaction with one exact Engine-owned physical source.

    Neither saved rows nor transient CHECK projections are project state.
    The typed PartSpec, PartRenderData and source BEND object identities are
    retained together for the entire view call, including one-sheet 2D.
    """
    part: str
    target: str
    part_spec: object
    render_data: object
    replays: Mapping
    saved_rows: Mapping


def _selected_corners(host, part, target):
    pair = host._pair_for_corner_target(target)
    together = host.manual_corner_pair_same[part].get(pair)
    if part == "tail" and target == "bottom" and together is True:
        return TAIL_BOTTOM_PAIR
    if target in CORNERS and together is False:
        return (target,)
    raise ValueError("請選單一實體角；只有自訂封尾下方可同片選左右兩角")


def _selected_source(host, snapshot):
    part = host._current_manual_corner_part_key()
    if part not in PARTS:
        raise ValueError("V 型 CHECK 試算來源只適用於封頭／封尾")
    corner = host.manual_active_corner_var.get()
    _selected_corners(host, part, corner)
    # The main GUI snapshot owns *per-physical-part* Features and Fold.
    # The canonical PartSpec/FinalScene adapters consume selected-payload
    # `features` / `fold_profiles`, NOT root `part_features` maps.
    # Use one identical detached payload for capture and saved replay.
    if not isinstance(snapshot, Mapping):
        raise ValueError("ENDCAP_LIVE_V_CANONICAL_SNAPSHOT_REQUIRED")
    payload = deepcopy(dict(snapshot))
    part_features = snapshot.get("part_features")
    if part_features is not None:
        if not isinstance(part_features, Mapping):
            raise ValueError("ENDCAP_LIVE_V_PART_FEATURES_INVALID")
        payload["features"] = deepcopy(part_features.get(part, ()))
    part_profiles = snapshot.get("part_profiles")
    if part_profiles is not None and not isinstance(part_profiles, Mapping):
        raise ValueError("ENDCAP_LIVE_V_PART_PROFILES_INVALID")
    # An authored selected EndCap Fold is the physical source, including
    # non-default angles. Never overwrite it with BoxBody-linked defaults.
    # Only an EndCap WITHOUT any selected saved X/Y Fold may take the
    # existing Engine linked default that Project Open materializes.
    authored = part_profiles.get(part) if part_profiles is not None else None
    if authored is not None:
        if not isinstance(authored, Mapping):
            raise ValueError("ENDCAP_LIVE_V_AUTHORED_FOLD_INVALID")
        if authored:
            if not authored.get("X") or not authored.get("Y"):
                raise ValueError("ENDCAP_LIVE_V_PARTIAL_AUTHORED_FOLD_INVALID")
            payload["fold_profiles"] = deepcopy(authored)
        else:
            raise ValueError("ENDCAP_LIVE_V_EMPTY_AUTHORED_FOLD_INVALID")
    else:
        box_profile = snapshot.get("box_body_profile")
        if box_profile:
            linked = engine.build_linked_endcap_xy_fold_profiles(
                snapshot, box_profile,
            )
            if part not in linked or not isinstance(linked[part], Mapping):
                raise ValueError("ENDCAP_LIVE_V_LINKED_FOLD_SOURCE_UNAVAILABLE")
            payload["fold_profiles"] = deepcopy(linked[part])
    spec, _context = host._fold_designer_part_spec_from_payload(part, payload)
    native = host._query_fold_designer_render_data(part, payload)
    if spec is None or native is None:
        raise ValueError("ENDCAP_LIVE_V_CURRENT_NATIVE_SOURCE_UNAVAILABLE")
    return part, corner, spec, native


def capture_current(host):
    snapshot = host._make_original_fold_designer_snapshot()
    part, corner, spec, native = _selected_source(host, snapshot)
    targets = _selected_corners(host, part, corner)
    selections = engine.normalize_operator_v_miter_gui_choices(
        snapshot.get("v_miter_gui_check_corners"),
    )
    axes = engine.normalize_operator_v_miter_gui_first_bend_axes(
        snapshot.get("v_miter_gui_first_bend_axes"), selections,
    )
    if len(targets) == 2:
        if any(selections.get(part, {}).get(key) != "V_MITER_CHECK"
               for key in targets):
            raise ValueError("V_MITER_TAIL_PAIR_BOTH_V_CHOICES_REQUIRED")
        # One actual selected first X on EACH corner; no auto 90-degree choice.
        chosen_axes = {key: axes.get(part, {}).get(key) for key in targets}
        if any(chosen_axes[key] != "x" for key in targets):
            raise ValueError("V_MITER_TAIL_PAIR_EXPLICIT_X_FIRST_REQUIRED")
        saved_modes = engine.normalize_operator_v_miter_gui_relief_modes(
            snapshot.get("v_miter_gui_relief_modes"), selections,
        )
        # Only the committed per-corner mode is authoritative. An absent
        # map means the original ROUND_R default, not an unsaved Tk switch.
        modes = {
            key: saved_modes.get(part, {}).get(key, "ROUND_R")
            for key in targets
        }
        # Public Engine checks shared source and BOTH local results before
        # the one GUI state assignment. No partial left-only save on failure.
        rows = engine.capture_endcap_live_v_miter_bottom_pair_snapshots(
            spec, native, first_bend_axes=chosen_axes, relief_modes=modes,
        )
        records = deepcopy(getattr(host, ATTR, {}))
        records.setdefault(part, {}).update(rows)
        setattr(host, ATTR, validate_live_sources({KEY: records}))
        return rows
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


def replay_current(host, snapshot, *, frozen_pair_source=False):
    records = getattr(host, ATTR, {})
    if not records:
        return None  # old files keep read-only legacy V1/V2 metadata view
    part, corner, spec, native = _selected_source(host, snapshot)
    targets = _selected_corners(host, part, corner)
    if len(targets) == 2:
        saved = records.get(part, {})
        if any(key not in saved for key in targets):
            raise ValueError("V_MITER_TAIL_PAIR_SAVED_BOTH_SOURCES_REQUIRED")
        selected = engine.normalize_operator_v_miter_gui_choices(
            snapshot.get("v_miter_gui_check_corners"),
        )
        axes = engine.normalize_operator_v_miter_gui_first_bend_axes(
            snapshot.get("v_miter_gui_first_bend_axes"), selected,
        )
        modes = engine.normalize_operator_v_miter_gui_relief_modes(
            snapshot.get("v_miter_gui_relief_modes"), selected,
        )
        if any(
            selected.get(part, {}).get(key) != "V_MITER_CHECK"
            or axes.get(part, {}).get(key) != saved[key]["first_bend_axis"]
            or modes.get(part, {}).get(key, "ROUND_R") != saved[key]["relief_mode"]
            for key in targets
        ):
            raise ValueError("V_MITER_TAIL_PAIR_SAVED_SELECTION_CHANGED")
        # Both rows are source-checked against THIS SINGLE owned RenderData.
        # Ordinary callers keep their historical dict result, whereas the
        # actual main GUI needs the full bound source for its subsequent
        # one-piece 2D projection. Never rebuild a new RenderData just to
        # compare identity of real finite BEND objects.
        selected_rows = {key: deepcopy(saved[key]) for key in targets}
        replays = engine.replay_endcap_live_v_miter_bottom_pair_snapshots(
            spec, native, selected_rows,
        )
        if not frozen_pair_source:
            return replays
        return _TailBottomPairReplayEnvelope(
            part=part,
            target=corner,
            part_spec=spec,
            render_data=native,
            replays=MappingProxyType(dict(replays)),
            saved_rows=MappingProxyType({
                key: MappingProxyType(row) for key, row in selected_rows.items()
            }),
        )
    row = records.get(part, {}).get(corner)
    if row is None:
        raise ValueError("ENDCAP_LIVE_V_SOURCE_NOT_SAVED_FOR_SELECTION")
    return engine.replay_endcap_live_v_miter_check_snapshot(spec, native, row)


def project_current_tail_pair_one_sheet_2d(host, snapshot, replays):
    """One verified Engine projection from the SAME fresh saved-pair source.

    Caller must already have replayed both saved source records; this method
    does not create/store a second part or manufacture a merged source.
    """
    if isinstance(replays, _TailBottomPairReplayEnvelope):
        if (replays.part != "tail" or replays.target != "bottom"
                or set(replays.replays) != set(TAIL_BOTTOM_PAIR)
                or set(replays.saved_rows) != set(TAIL_BOTTOM_PAIR)):
            raise ValueError("V_MITER_TAIL_PAIR_2D_PAIR_SELECTION_REQUIRED")
        # Crucial: this MUST be the same exact PartSpec/PartRenderData already
        # bound by grouped replay. Engine retains its strict identity guard.
        return engine.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
            replays.part_spec, replays.render_data, replays.replays,
        )
    # Existing dict-based callers retain the old projection behavior.
    part, target, spec, native = _selected_source(host, snapshot)
    if (part != "tail" or target != "bottom"
            or _selected_corners(host, part, target) != TAIL_BOTTOM_PAIR):
        raise ValueError("V_MITER_TAIL_PAIR_2D_PAIR_SELECTION_REQUIRED")
    return engine.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
        spec, native, replays,
    )
