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
from .endcap_factory_fold import commit_endcap_fw, set_endcap_fw_follow


@dataclass(frozen=True)
class OperatorBottomWrapTransition:
    state: dict[str, object]
    resolved: dict[str, object]


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
