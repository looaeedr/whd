"""EndCap FW / bottom-WRAP / Joint settings transaction facade.

Operator inputs are copied and handed to the existing Engine state machines;
no Tk/Phase6 dependencies, no second geometry, no new certification scope.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping

from .assembly_joint import set_part_edge_relation
from .box_body_fold_profile import _num
from .endcap_bottom_wrap_state import (
    commit_endcap_bottom_wrap, normalize_endcap_bottom_wrap_state,
    resolve_endcap_bottom_wrap,
)
from .endcap_factory_fold import (
    ENDCAP_FW_PARTS, FW_FOLLOW_HEAD, FW_FOLLOW_TAIL,
    commit_operator_box_fw_takeover, commit_endcap_fw,
    normalize_endcap_fw_state, project_operator_endcap_fw_controls,
    set_endcap_fw_follow,
)
from .operator_settings_transactions import (
    normalize_operator_settings_boolean, normalize_operator_source_dimension,
)


@dataclass(frozen=True)
class OperatorBottomWrapTransition:
    state: dict[str, object]
    resolved: dict[str, object]



def project_operator_box_fw_live_state(
    endcap_fw_state: Mapping[str, object],
    *,
    previous_box_fw: object,
    requested_box_fw: object,
) -> dict[str, object]:
    """Stage a main-GUI or Fold Designer box-FW edit via the canonical four-state owner.

    A real box-FW change explicitly retakes both Head/Tail regardless of their
    previous leader/split state. No-op settings synchronization must preserve
    that state. The original saved source is never mutated by the projection.
    """
    if not isinstance(endcap_fw_state, Mapping):
        raise ValueError("ENDCAP_FW_STATE_INVALID")
    previous = normalize_operator_source_dimension(previous_box_fw, field="fw")
    requested = normalize_operator_source_dimension(requested_box_fw, field="fw")
    state = deepcopy(dict(endcap_fw_state))
    if previous != requested:
        commit_operator_box_fw_takeover(state, requested)
    return state



def commit_operator_baseline_endcap_fw(
    state: dict[str, object], raw_box_fw: object,
) -> dict[str, object]:
    """Apply a loaded Vault baseline FW without stealing Head/Tail control.

    Baseline reload is not an operator's explicit box-FW takeover. Preserve
    the four-state owner and update only physically following rows. Validate
    both saved rows before touching any live dictionary or nested GUI alias.
    """
    if type(state) is not dict:
        raise ValueError("ENDCAP_BASELINE_FW_STATE_REQUIRED")
    for part in ENDCAP_FW_PARTS:
        if part in state and type(state[part]) is not dict:
            raise ValueError("ENDCAP_FW_SOURCE_ROW_INVALID")

    box_fw = normalize_operator_source_dimension(raw_box_fw, field="fw")
    # The original read-only projection validates serialized follow_box and
    # inactive physical FW. It must run BEFORE legacy normalize_endcap_fw_state
    # because bool("false") in the old compatibility reader is True.
    rows = project_operator_endcap_fw_controls(state, box_fw)
    candidate = deepcopy(state)
    for part in ENDCAP_FW_PARTS:
        if part in candidate:
            candidate[part]["follow_box"] = rows[part]["follow_box"]

    canonical = normalize_endcap_fw_state({
        "fw": box_fw, "endcap_fw": candidate,
    })
    for part in ENDCAP_FW_PARTS:
        row = candidate.setdefault(part, {})
        row["follow_box"] = canonical[part]["follow_box"]
        if row["follow_box"]:
            # FOLLOW_BODY and a legacy independent follower receive the new
            # box FW; legacy stored follower values may still be stale.
            row["value"] = box_fw
        elif canonical["mode"] in (FW_FOLLOW_HEAD, FW_FOLLOW_TAIL):
            # Explicit Head/Tail leadership stays with its current value.
            row["value"] = canonical[part]["value"]
    if "mode" in candidate:
        candidate["mode"] = canonical["mode"]
    project_operator_endcap_fw_controls(candidate, box_fw)

    for part in ENDCAP_FW_PARTS:
        if part not in state:
            state[part] = candidate[part]
        else:
            # Preserve live Head/Tail row references used by the GUI.
            state[part].clear()
            state[part].update(candidate[part])
    if "mode" in state:
        state["mode"] = candidate["mode"]
    return state


def _stage_operator_endcap_fw_source(
    input_snapshot: Mapping[str, object],
    settings_values: Mapping[str, object],
    endcap_fw_state: Mapping[str, object],
) -> tuple[dict[str, object], float]:
    """Validate the physical box-FW authority before staging a Head/Tail edit.

    GUI and saved settings may contain strings, but a missing, nonpositive,
    boolean or nonfinite FW must never silently become the old default 25.
    """
    if not all(isinstance(source, Mapping) for source in (
        input_snapshot, settings_values, endcap_fw_state,
    )):
        raise ValueError("ENDCAP_FW_OPERATOR_SOURCE_INVALID")
    source = dict(input_snapshot)
    source.update(dict(settings_values))
    box_fw = normalize_operator_source_dimension(source.get("fw"), field="fw")
    # The original set_endcap_fw_follow mutates one row before inspecting both;
    # refuse corrupt saved counterparts before any staged candidate is accepted.
    for part in ENDCAP_FW_PARTS:
        if part in endcap_fw_state and not isinstance(endcap_fw_state[part], Mapping):
            raise ValueError("ENDCAP_FW_SOURCE_ROW_INVALID")
    return deepcopy(dict(endcap_fw_state)), box_fw


def operator_endcap_fw_follow(
    input_snapshot: Mapping[str, object],
    settings_values: Mapping[str, object],
    endcap_fw_state: Mapping[str, object],
    part_key: str,
    follow_box: bool,
) -> dict[str, object]:
    """Apply a typed follow-box edit using the existing Engine four-state owner."""
    state, box_fw = _stage_operator_endcap_fw_source(
        input_snapshot, settings_values, endcap_fw_state,
    )
    follow = normalize_operator_settings_boolean(follow_box)
    set_endcap_fw_follow(
        state, str(part_key), follow, box_fw=box_fw,
    )
    return state


def operator_endcap_fw_override(
    input_snapshot: Mapping[str, object],
    settings_values: Mapping[str, object],
    endcap_fw_state: Mapping[str, object],
    part_key: str,
    value: object,
) -> dict[str, object]:
    """Validate finished FW, then delegate Head/Tail linked edit to Engine."""
    state, box_fw = _stage_operator_endcap_fw_source(
        input_snapshot, settings_values, endcap_fw_state,
    )
    requested_fw = normalize_operator_source_dimension(value, field="fw")
    commit_endcap_fw(
        state, str(part_key), requested_fw, box_fw=box_fw,
    )
    return state


def commit_operator_endcap_fw_profile_save(
    input_snapshot: Mapping[str, object],
    state: dict[str, object],
    part_key: str,
    fw_segment: Mapping[str, object] | None,
) -> dict[str, object]:
    """Commit the real Head/Tail Fold-editor FW through one Engine transaction.

    Validate the *original* segment length and optional adjacent-BEND
    compensation before the legacy UI length reader can turn bool into 1 mm,
    nonfinite values into defaults, or a missing box FW into 25 mm. The
    original four-mode Head/Tail owner decides no-op versus leader/split.
    Only after staging and checking both rows is the live dict updated,
    retaining the original Head/Tail row identities used by GUI controls.
    """
    from .cabinet_types import policy as cabinet_family_policy
    from .endcap_factory_fold import (
        project_operator_endcap_fw_controls, resolve_endcap_fw,
        commit_operator_endcap_fw_value,
    )
    from .endcap_xy_readback import fold_material_segment_outside_length
    from .operator_settings_transactions import normalize_operator_settings_updates

    if not isinstance(input_snapshot, Mapping) or type(state) is not dict:
        raise ValueError("ENDCAP_FW_PROFILE_SOURCE_INVALID")
    if type(part_key) is not str or part_key not in ENDCAP_FW_PARTS:
        raise ValueError("ENDCAP_FW_PART_REQUIRED")
    body_fw = normalize_operator_source_dimension(
        input_snapshot.get("fw"), field="fw",
    )
    rows = project_operator_endcap_fw_controls(state, body_fw)
    for part in ENDCAP_FW_PARTS:
        if part in state and type(state[part]) is not dict:
            raise ValueError("ENDCAP_FW_SOURCE_ROW_INVALID")

    staged = deepcopy(state)
    staged.setdefault(part_key, {"follow_box": True, "value": body_fw})
    if fw_segment is not None:
        if not isinstance(fw_segment, Mapping) or "len" not in fw_segment:
            raise ValueError("ENDCAP_FW_PROFILE_SEGMENT_INVALID")
        material = cabinet_family_policy.endcap_fw_profile_uses_material_dimensions(
            input_snapshot,
        )
        source = {"segment_len": fw_segment["len"]}
        if material and "ui_len_add" in fw_segment:
            source["segment_add"] = fw_segment["ui_len_add"]
        accepted = normalize_operator_settings_updates(
            {key: 0.0 for key in source}, source,
        )
        if len(accepted) != len(source):
            raise ValueError("ENDCAP_FW_PROFILE_SEGMENT_INVALID")
        segment = {"len": accepted["segment_len"]}
        if "segment_add" in accepted:
            segment["ui_len_add"] = accepted["segment_add"]
        edited = normalize_operator_source_dimension(
            fold_material_segment_outside_length(segment), field="fw",
        )
        # Serialized follower strings are qualified by the Engine projection
        # before the legacy four-state resolver sees them. No GUI bool() gate.
        canonical = deepcopy(staged)
        for part in ENDCAP_FW_PARTS:
            if part in canonical:
                canonical[part]["follow_box"] = rows[part]["follow_box"]
                canonical[part]["value"] = rows[part]["display_fw"]
        effective = normalize_operator_source_dimension(
            resolve_endcap_fw({"fw": body_fw}, part_key, state=canonical),
            field="fw",
        )
        if abs(edited - effective) > 1e-9:
            commit_operator_endcap_fw_value(
                canonical, part_key, edited, box_fw=body_fw,
            )
            staged = canonical
    project_operator_endcap_fw_controls(staged, body_fw)

    # Keep caller-owned root dict AND nested Head/Tail rows stable. Never
    # mutate them during the failed-validation phase above.
    for part in ENDCAP_FW_PARTS:
        if part not in staged:
            continue
        if part in state:
            state[part].clear()
            state[part].update(staged[part])
        else:
            state[part] = staged[part]
    if "mode" in staged:
        state["mode"] = staged["mode"]
    return state


def operator_endcap_bottom_wrap(
    input_snapshot: Mapping[str, object],
    endcap_bottom_wrap_state: Mapping[str, object] | None,
    part_key: str,
    *,
    reserve_u: object,
    reserve_v: object,
) -> OperatorBottomWrapTransition:
    """Copy-on-write WRAP reserve commit with Engine Joint-aware readback."""
    snapshot = deepcopy(dict(input_snapshot))
    state = deepcopy(dict(endcap_bottom_wrap_state or {}))
    if not state:
        state.update(normalize_endcap_bottom_wrap_state(snapshot))
    # The public operator transaction requires both original reserve inputs;
    # do not erase bool/NaN/negative evidence before the canonical Engine gate.
    if reserve_u is None or reserve_v is None:
        raise ValueError("WRAP 預留量必須提供 X／Y 原始來源")
    commit_endcap_bottom_wrap(
        state, str(part_key),
        reserve_u=reserve_u, reserve_v=reserve_v,
    )
    snapshot["endcap_bottom_wrap"] = deepcopy(state)
    resolved = resolve_endcap_bottom_wrap(snapshot, str(part_key), state=state)
    return OperatorBottomWrapTransition(
        state=deepcopy(state),
        resolved=deepcopy(resolved),
    )


def operator_endcap_edge_relation(
    input_snapshot: Mapping[str, object],
    part_key: str,
    edge: str,
    relation: object,
) -> dict[str, object]:
    """Commit the actual typed Assembly Joint without GUI-owned mutation."""
    return set_part_edge_relation(
        deepcopy(dict(input_snapshot)),
        str(part_key), str(edge).upper(), relation,
    )
