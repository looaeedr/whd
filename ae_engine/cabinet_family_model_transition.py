# -*- coding: utf-8 -*-
"""Canonical Engine Family-model transition for WHD GUI and headless clients.

Controls manufacturing-family defaults, topology, Receiving Set/Bay initial
CSV-sourced NFB, corner presets, assembly intent, EndCap wrap and BoxBody
structure. The GUI owns only operator model selection and presentation.
No new geometry, NFB dimensions or alternative CSV source are defined here.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping

from .cabinet_types import policy as cabinet_family_policy
from .assembly_intent_transactions import (
    normalize_assembly_type, commit_assembly_intent_state,
)
from .corner_state_transactions import apply_corner_preset
from .endcap_bottom_wrap_state import normalize_endcap_bottom_wrap_state


@dataclass(frozen=True)
class FamilyModelTransition:
    new_model: str
    old_model: str
    editable: bool
    defaults: dict[str, object]
    family_values: dict[str, object]
    assembly_type: object
    structure_state: dict[str, object] | None
    remember_non_receiving_structure: dict[str, object] | None


@dataclass(frozen=True)
class FamilyModelPlan:
    input_snapshot: dict[str, object]
    corner_state: dict[str, object]
    corner_pair_same: dict[str, object]
    endcap_bottom_wrap_state: dict[str, object]
    assembly_type: object
    desired_structure: dict[str, object] | None
    transition: FamilyModelTransition


def plan_cabinet_family_model_transition(
    new_model: object,
    old_model: object,
    *,
    new_editable: bool,
    old_editable: bool,
    input_snapshot: Mapping[str, object],
    settings_values: Mapping[str, object],
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    endcap_bottom_wrap_state: Mapping[str, object] | None,
    assembly_type: object,
    fixed_corner_state: Mapping[str, object] | None = None,
    available_parts: tuple[object, ...] | list[object] = (),
    current_structure: Mapping[str, object] | None = None,
    previous_non_receiving_structure: Mapping[str, object] | None = None,
) -> FamilyModelPlan:
    target_model = str(new_model or "").strip()
    previous_model = str(old_model or "").strip()
    snapshot = deepcopy(dict(input_snapshot))
    corners = deepcopy(dict(corner_state or {}))
    pairs = deepcopy(dict(corner_pair_same or {}))
    wrap_state = deepcopy(dict(endcap_bottom_wrap_state or {}))
    canonical_assembly = normalize_assembly_type(assembly_type)
    old_snapshot_model = str(
        snapshot.get("model") or previous_model or ""
    ).strip()

    # Aliases of one family are not a cabinet-family transition: resetting
    # fixed corners when toggling "受電箱" / "RECEIVING" loses operator edits.
    previous_family = cabinet_family_policy.canonical_family_name(previous_model)
    target_family = cabinet_family_policy.canonical_family_name(target_model)
    if (
        (not new_editable and target_model and target_family != previous_family)
        or (new_editable and previous_model and not old_editable)
    ):
        preset = apply_corner_preset(corners, pairs, fixed_corner_state)
        corners = preset.corner_state
        pairs = preset.corner_pair_same

    snapshot["model"] = target_model
    defaults: dict[str, object] = {}
    family_values: dict[str, object] = {}
    old_snapshot_family = cabinet_family_policy.canonical_family_name(
        old_snapshot_model
    )

    if (
        not new_editable
        and target_model
        and target_family != old_snapshot_family
    ):
        runtime_presets = dict(snapshot.get("_runtime_family_presets") or {})
        preset_runtime = deepcopy(
            dict(
                runtime_presets.get(target_model)
                or runtime_presets.get(target_family)
                or {}
            )
        )
        preset_base = dict(preset_runtime.get("settings") or {})
        if not preset_base:
            preset_base = dict(snapshot.get("factory_defaults") or {})
        if not preset_base:
            preset_base = {
                key: value
                for key, value in snapshot.items()
                if key in settings_values
            }

        fresh_defaults = dict(
            cabinet_family_policy.apply_fresh_family_defaults(
                preset_base, target_model
            )
        )
        # UI presentation preferences are global operator state, not cabinet-family
        # geometry defaults. A baseline/family switch must never reset text size.
        defaults = {
            key: value
            for key, value in fresh_defaults.items()
            if key != "ui_text_size"
        }
        snapshot.update(defaults)
        if target_family == "受電箱":
            # A newly selected Family must immediately own one real CSV NFB,
            # its inner-door CUTTING and derived Base/EAR sources. This path
            # never runs for a saved project's load/reload normalization.
            from .receiving_fresh_nfb_defaults import (
                seed_fresh_receiving_nfb_source,
            )
            from .receiving_layout import (
                RECEIVING_RUNTIME_SELECTION_KEY, new_receiving_layout,
            )
            snapshot["active_mode"] = "set_bay"
            snapshot.pop("quantity", None)
            snapshot.pop("receiving_quantity_box", None)
            snapshot.pop(RECEIVING_RUNTIME_SELECTION_KEY, None)
            # A NEW Family is not a re-entry into the previous project's
            # unconfigured Quantity/Bay. Reusing its saved ReceivingLayout
            # can carry an alternate switch brand and silently skip the
            # required one-NFB initial source. Start Set1/Bay1 from the
            # current Family dimensions, then seed the CSV-derived source.
            snapshot["receiving_layout"] = new_receiving_layout(
                width=snapshot["w"], height=snapshot["h"], depth=snapshot["d"],
            )
            snapshot = seed_fresh_receiving_nfb_source(snapshot)
        if "ui_text_size" in settings_values:
            snapshot["ui_text_size"] = settings_values["ui_text_size"]

        runtime_field_map = {
            "multi_door_enabled": "multi_door_enabled",
            "door_layout_columns": "door_layout_columns",
            "door_layout_scope": "door_layout_scope",
            "door_handle_edges": "door_handle_edges",
            "receiving_inner_doors": "inner_doors",
            "door_nameplate_center_datum_top": (
                "door_nameplate_center_datum_top"
            ),
        }
        for source_key, target_key in runtime_field_map.items():
            if source_key in preset_runtime:
                snapshot[target_key] = deepcopy(preset_runtime[source_key])

        # Receiving owns Door-cell topology and its derived physical parts.
        # A switch to another known family must not carry that topology forward
        # merely because the target preset does not mention Receiving-only keys.
        # Custom remains carry-forward by design.
        if (
            not new_editable
            and cabinet_family_policy.canonical_family_name(target_model) != "受電箱"
        ):
            snapshot["multi_door_enabled"] = False
            snapshot["door_layout_columns"] = []
            snapshot["door_layout_scope"] = "main"
            snapshot["door_handle_edges"] = {}
            snapshot["inner_doors"] = []
            snapshot["door_nameplate_center_datum_top"] = None

        family_values = {
            key: value
            for key, value in defaults.items()
            if key in settings_values
        }

        intent_result = commit_assembly_intent_state(
            snapshot,
            corners,
            pairs,
            cabinet_family_policy.fresh_assembly_intent(target_model),
            available_parts=available_parts,
            project_legacy_corner=False,
        )
        snapshot = intent_result.input_snapshot
        corners = intent_result.corner_state
        pairs = intent_result.corner_pair_same
        canonical_assembly = intent_result.assembly_type

        wrap_state = normalize_endcap_bottom_wrap_state(
            {"model": target_model}
        )
        snapshot["endcap_bottom_wrap"] = deepcopy(wrap_state)

    remember_structure = None
    desired_structure = None
    current = (
        None if current_structure is None
        else deepcopy(dict(current_structure))
    )

    if target_family == "受電箱":
        if old_snapshot_family != "受電箱" and current is not None:
            remember_structure = deepcopy(current)
        desired_structure = cabinet_family_policy.resolve_box_body_structure_state(
            target_model,
            current if old_snapshot_family == "受電箱" else None,
        )
    elif old_snapshot_family == "受電箱":
        runtime_presets = dict(snapshot.get("_runtime_family_presets") or {})
        preset_runtime = deepcopy(
            dict(
                runtime_presets.get(target_model)
                or runtime_presets.get(target_family)
                or {}
            )
        )
        previous = preset_runtime.get("box_body_structure")
        if previous is None:
            previous = previous_non_receiving_structure
        if previous:
            desired_structure = deepcopy(dict(previous))

    transition = FamilyModelTransition(
        new_model=target_model,
        old_model=previous_model,
        editable=bool(new_editable),
        defaults=deepcopy(defaults),
        family_values=deepcopy(family_values),
        assembly_type=canonical_assembly,
        structure_state=(
            None if desired_structure is None
            else deepcopy(desired_structure)
        ),
        remember_non_receiving_structure=(
            None if remember_structure is None
            else deepcopy(remember_structure)
        ),
    )
    return FamilyModelPlan(
        input_snapshot=snapshot,
        corner_state=corners,
        corner_pair_same=pairs,
        endcap_bottom_wrap_state=deepcopy(wrap_state),
        assembly_type=canonical_assembly,
        desired_structure=(
            None if desired_structure is None
            else deepcopy(desired_structure)
        ),
        transition=transition,
    )


