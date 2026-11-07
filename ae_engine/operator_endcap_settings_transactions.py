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
    commit_operator_box_fw_takeover, commit_endcap_fw, set_endcap_fw_follow,
)
from .operator_settings_transactions import normalize_operator_source_dimension


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


def operator_endcap_fw_follow(
    input_snapshot: Mapping[str, object],
    settings_values: Mapping[str, object],
    endcap_fw_state: Mapping[str, object],
    part_key: str,
    follow_box: bool,
) -> dict[str, object]:
    """Preserve legacy follow-box semantics using one Engine-owned state."""
    snapshot = deepcopy(dict(input_snapshot))
    snapshot.update(deepcopy(dict(settings_values)))
    state = deepcopy(dict(endcap_fw_state or {}))
    set_endcap_fw_follow(
        state, str(part_key), bool(follow_box),
        box_fw=_num(snapshot.get("fw", 25), 25),
    )
    return state


def operator_endcap_fw_override(
    input_snapshot: Mapping[str, object],
    settings_values: Mapping[str, object],
    endcap_fw_state: Mapping[str, object],
    part_key: str,
    value: object,
) -> dict[str, object]:
    """Head/Tail linked-edit and legacy defaults stay in canonical Engine."""
    snapshot = deepcopy(dict(input_snapshot))
    snapshot.update(deepcopy(dict(settings_values)))
    state = deepcopy(dict(endcap_fw_state or {}))
    commit_endcap_fw(
        state, str(part_key), _num(value),
        box_fw=_num(snapshot.get("fw", 25), 25),
    )
    return state


def operator_endcap_bottom_wrap(
    input_snapshot: Mapping[str, object],
    endcap_bottom_wrap_state: Mapping[str, object] | None,
    part_key: str,
    *,
    reserve_u: float,
    reserve_v: float,
) -> OperatorBottomWrapTransition:
    """Copy-on-write WRAP reserve commit with Engine Joint-aware readback."""
    snapshot = deepcopy(dict(input_snapshot))
    state = deepcopy(dict(endcap_bottom_wrap_state or {}))
    if not state:
        state.update(normalize_endcap_bottom_wrap_state(snapshot))
    commit_endcap_bottom_wrap(
        state, str(part_key),
        reserve_u=float(reserve_u), reserve_v=float(reserve_v),
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
