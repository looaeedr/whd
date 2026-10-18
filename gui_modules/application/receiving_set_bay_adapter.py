# -*- coding: utf-8 -*-
"""Pure application adapter for Receiving Set/Bay editing.

The canonical project authority remains ``receiving_layout``.  This adapter owns
only UI selection plus destructive-confirmation bookkeeping; it never mirrors a
second persisted topology.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

from ae_engine.receiving_manufacturing_readiness import (
    ReceivingManufacturingFailure,
    evaluate_receiving_manufacturing_readiness,
    receiving_readiness_projection,
)
from ae_engine.receiving_layout import (
    append_receiving_set,
    normalize_receiving_layout,
    project_receiving_bay_legacy_aliases,
    receiving_destructive_tail_ids,
    receiving_joint_alignment_editability,
    resize_receiving_bays,
    resize_receiving_sets,
    update_receiving_bay,
    update_receiving_joint_alignment,
)


class ReceivingDestructiveEditConfirmationRequired(RuntimeError):
    def __init__(self, stable_ids: Iterable[str]):
        self.stable_ids = tuple(str(value) for value in stable_ids)
        super().__init__(
            "Receiving destructive tail edit requires confirmation: "
            + ", ".join(self.stable_ids)
        )


def receiving_layout_stable_ids(layout: Mapping[str, object]) -> tuple[str, ...]:
    normalized = normalize_receiving_layout(layout)
    result: list[str] = []
    for set_row in normalized["sets"]:
        result.append(str(set_row["stable_id"]))
        result.extend(str(row["stable_id"]) for row in set_row["bays"])
        result.extend(str(row["stable_id"]) for row in set_row["joints"])
    return tuple(result)


@dataclass(frozen=True)
class ReceivingSelection:
    set_index: int = 0
    bay_index: int = 0


class ReceivingSetBayAdapter:
    """Selection/edit facade over one canonical ReceivingLayout value."""

    def __init__(
        self,
        layout: Mapping[str, object],
        *,
        persisted_ids: Iterable[str] = (),
        confirm_destructive: Callable[[tuple[str, ...]], bool] | None = None,
    ) -> None:
        self._layout = normalize_receiving_layout(layout)
        self._selection = ReceivingSelection()
        self._persisted_ids = {str(value) for value in persisted_ids}
        self._session_dirty_ids: set[str] = set()
        self._confirm_destructive = confirm_destructive
        self._nfb_undo_receipts = []  # transient transaction history, not persisted

    @property
    def layout(self) -> dict[str, object]:
        return deepcopy(self._layout)

    @property
    def selection(self) -> ReceivingSelection:
        return self._selection

    def visible_set_numbers(self) -> tuple[int, ...]:
        """Existing Sets plus exactly one progressive next-Set affordance."""
        count = len(self._layout["sets"])
        return tuple(range(1, count + 2))

    def bay_count(self, set_index: int | None = None) -> int:
        index = self._selection.set_index if set_index is None else int(set_index)
        return len(self._layout["sets"][index]["bays"])

    def select_set(self, set_number: int) -> bool:
        wanted = int(set_number)
        existing = len(self._layout["sets"])
        if wanted < 1 or wanted > existing + 1:
            raise IndexError("Receiving Set selection is not progressively available")
        created = wanted == existing + 1
        if created:
            self._layout = append_receiving_set(self._layout)
        self._selection = ReceivingSelection(set_index=wanted - 1, bay_index=0)
        return created

    def select_bay(self, bay_number: int) -> None:
        wanted = int(bay_number)
        count = self.bay_count()
        if wanted < 1 or wanted > count:
            raise IndexError("Receiving Bay selection out of range")
        self._selection = ReceivingSelection(
            set_index=self._selection.set_index,
            bay_index=wanted - 1,
        )

    def current_bay(self) -> dict[str, object]:
        return deepcopy(
            self._layout["sets"][self._selection.set_index]["bays"][self._selection.bay_index]
        )

    def mark_current_bay_dirty(self) -> None:
        self._session_dirty_ids.add(str(self.current_bay()["stable_id"]))

    def mark_clean(self) -> None:
        self._persisted_ids = set(receiving_layout_stable_ids(self._layout))
        self._session_dirty_ids.clear()

    def _confirm_if_required(self, removed: tuple[str, ...]) -> None:
        protected = tuple(
            stable_id
            for stable_id in removed
            if stable_id in self._persisted_ids or stable_id in self._session_dirty_ids
        )
        if not protected:
            return
        if self._confirm_destructive is None:
            raise ReceivingDestructiveEditConfirmationRequired(protected)
        if not bool(self._confirm_destructive(protected)):
            raise ReceivingDestructiveEditConfirmationRequired(protected)

    def set_bay_count(self, bay_count: int) -> None:
        wanted = int(bay_count)
        current = self.bay_count()
        if wanted < current:
            removed = receiving_destructive_tail_ids(
                self._layout,
                set_index=self._selection.set_index,
                bay_count=wanted,
            )
            self._confirm_if_required(removed)
            self._persisted_ids.difference_update(removed)
            self._session_dirty_ids.difference_update(removed)
        candidate = resize_receiving_bays(
            self._layout,
            set_index=self._selection.set_index,
            bay_count=wanted,
        )
        if wanted > current:
            # New Bay dimensions originate from the Receiving Family authority,
            # not from the previously selected Bay's possibly custom size.
            from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS
            defaults = tuple(float(BOX_BODY_DEFAULTS[axis]) for axis in ("w", "h", "d"))
            if any(not value.is_integer() or value <= 0 for value in defaults):
                raise ValueError("受電箱預設 W/H/D 必須為正整數毫米")
            builder = ReceivingSetBayAdapter(candidate)
            builder.apply_dimensions_to_bays(
                self._selection.set_index, tuple(range(current, wanted)),
                width=int(defaults[0]), height=int(defaults[1]),
                depth=int(defaults[2]), expected_count=wanted - current,
            )
            candidate = builder.layout
        self._layout = candidate
        new_count = self.bay_count()
        self._selection = ReceivingSelection(
            set_index=self._selection.set_index,
            bay_index=min(self._selection.bay_index, new_count - 1),
        )

    def set_set_count(self, set_count: int) -> None:
        wanted = int(set_count)
        current = len(self._layout["sets"])
        if wanted < current:
            removed = receiving_destructive_tail_ids(self._layout, set_count=wanted)
            self._confirm_if_required(removed)
            self._persisted_ids.difference_update(removed)
            self._session_dirty_ids.difference_update(removed)
        self._layout = resize_receiving_sets(self._layout, set_count=wanted)
        set_index = min(self._selection.set_index, wanted - 1)
        bay_index = min(
            self._selection.bay_index,
            len(self._layout["sets"][set_index]["bays"]) - 1,
        )
        self._selection = ReceivingSelection(set_index=set_index, bay_index=bay_index)

    def apply_dimensions_to_bays(self, set_index, bay_indices, *, width, height, depth, expected_count):
        """Apply W/H/D to explicitly highlighted real Bays, atomically."""
        from ae_engine.sheetmetal_part_adapters import complete_partition
        index = int(set_index)
        if index < 0 or index >= len(self._layout["sets"]):
            raise IndexError("套不存在")
        for label, value in (("W", width), ("H", height), ("D", depth), ("數量", expected_count)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{label} 必須為正整數")
        selected = tuple(bay_indices)
        bay_count = len(self._layout["sets"][index]["bays"])
        if (len(selected) != expected_count or len(set(selected)) != len(selected)
                or any(type(i) is not int or not 0 <= i < bay_count for i in selected)):
            raise ValueError(f"右側必須高亮剛好 {expected_count} 個箱體")
        # One operator confirmation is one atomic topology transaction. The
        # old loop called update_receiving_bay() for every highlighted Bay;
        # that helper normalizes the *entire* Set/Bay/Joint layout twice on
        # each call, rebuilding even untouched Bays. Keep the same per-Bay
        # door-partition checks but validate the final candidate only once.
        candidate, dirty = self._layout, []
        for bay_index in selected:
            current = candidate["sets"][index]["bays"][bay_index]
            changes = {"width": width, "height": height, "depth": depth}
            if all(float(current[k]) == v for k, v in changes.items()):
                continue
            door = current.get("door_state")
            if door and (float(current["width"]) != width or float(current["height"]) != height):
                columns = door.get("door_layout_columns") or ()
                if door.get("multi_door_enabled") and not columns:
                    raise ValueError(f"第{bay_index + 1}連門分割資料不完整")
                if columns:
                    widths = complete_partition([item[0] for item in columns[:-1]], width)
                    if not widths.valid or len(widths.values) != len(columns):
                        raise ValueError(f"第{bay_index + 1}連 W 不符合門分割")
                    new_cols = []
                    for new_w, (_, heights) in zip(widths.values, columns):
                        sizes = complete_partition(heights[:-1], height)
                        if not sizes.valid or len(sizes.values) != len(heights):
                            raise ValueError(f"第{bay_index + 1}連 H 不符合門分割")
                        new_cols.append([new_w, list(sizes.values)])
                    changes["door_state"] = {**deepcopy(door), "door_layout_columns": new_cols}
            if not dirty:
                candidate = deepcopy(self._layout)
            # Existing update_receiving_bay() casts numeric inputs to float
            # before canonical normalization; preserve that data contract.
            candidate["sets"][index]["bays"][bay_index] = {
                **current, **{axis: float(value) for axis, value in changes.items()
                              if axis in ("width", "height", "depth")},
                **({"door_state": changes["door_state"]} if "door_state" in changes else {}),
            }
            dirty.append(str(current["stable_id"]))
        if not dirty:
            return 0
        # Normalize and check *all* dependencies/Joints once. Any failure
        # leaves both the canonical layout and dirty bookkeeping unchanged.
        validated = normalize_receiving_layout(candidate)
        self._layout = validated
        self._session_dirty_ids.update(dirty)
        return len(dirty)

    def update_current_bay(self, **changes: object) -> bool:
        before = self.current_bay()
        updated = update_receiving_bay(
            self._layout,
            set_index=self._selection.set_index,
            bay_index=self._selection.bay_index,
            **changes,
        )
        after = updated["sets"][self._selection.set_index]["bays"][self._selection.bay_index]
        changed = dict(before) != dict(after)
        self._layout = updated
        if changed:
            self.mark_current_bay_dirty()
        return changed

    def update_setting(self, kind, value):
        from ae_engine.receiving_shared_settings import edit_setting
        self._layout = edit_setting(self._layout, set_index=self.selection.set_index,
                                    bay_index=self.selection.bay_index, kind=kind, value=value)
        self.mark_current_bay_dirty()

    def share_setting(self, kind, bay_indices):
        from ae_engine.receiving_shared_settings import share_setting
        self._layout = share_setting(self._layout, set_index=self.selection.set_index,
                                     source_bay_index=self.selection.bay_index,
                                     bay_indices=bay_indices, kind=kind)
        self.mark_current_bay_dirty()

    def unlink_setting(self, kind):
        from ae_engine.receiving_shared_settings import unlink_setting
        self._layout = unlink_setting(self._layout, set_index=self.selection.set_index,
                                      bay_index=self.selection.bay_index, kind=kind)
        self.mark_current_bay_dirty()

    def set_brand(self, brand):
        from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS
        if brand not in RECEIVING_SWITCH_BRANDS:
            raise ValueError("不支援的開關品牌")
        self._layout["sets"][self.selection.set_index]["switch_brand"] = brand

    def apply_candidate_to_bays(self, role, set_index, bay_indices, features, *, version_id=None):
        """Atomically update ONLY highlighted Bays; preserve other shared refs."""
        from ae_engine.receiving_hole_candidates import role_key
        from ae_engine.receiving_shared_settings import (
            unlink_setting, edit_setting, validate_setting,
        )
        kind = role_key(role) + "_features"
        version_kind = role + "_version_id"
        version_id = validate_setting(version_kind, version_id)
        features = validate_setting(kind, features)
        if type(set_index) is not int or not 0 <= set_index < len(self._layout["sets"]):
            raise ValueError("選取的套不存在")
        indices = tuple(sorted(set(bay_indices)))
        count = len(self._layout["sets"][set_index]["bays"])
        if not indices or any(type(i) is not int or not 0 <= i < count for i in indices):
            raise ValueError("請在簡易圖高亮有效的連")
        candidate = self._layout
        for bay_index in indices:
            candidate = unlink_setting(
                candidate, set_index=set_index, bay_index=bay_index, kind=kind,
            )
            candidate = edit_setting(
                candidate, set_index=set_index, bay_index=bay_index,
                kind=kind, value=features,
            )
            candidate = unlink_setting(
                candidate, set_index=set_index, bay_index=bay_index,
                kind=version_kind,
            )
            candidate = edit_setting(
                candidate, set_index=set_index, bay_index=bay_index,
                kind=version_kind, value=version_id,
            )
        # Commit once after all validation and changes, with no UI reselect.
        self._layout = candidate
        self._session_dirty_ids.update(
            str(self._layout["sets"][set_index]["bays"][i]["stable_id"])
            for i in indices
        )
        return indices

    def apply_quantity_configuration(self, role, library, quantities, assigned, *,
                                     expected_counts=None):
        """Atomically commit complete candidate distribution across every Set."""
        from ae_engine.receiving_hole_candidates import role_key
        from ae_engine.receiving_quantity_allocation import validate_quantity_allocation
        from ae_engine.receiving_shared_settings import unlink_setting, edit_setting
        plan = validate_quantity_allocation(
            self._layout, library, role, quantities, assigned,
            expected_counts=expected_counts,
        )
        kind = role_key(role) + "_features"
        version_kind = role + "_version_id"
        from ae_engine.receiving_shared_settings import validate_setting
        for si, bi, _features in plan:
            validate_setting(version_kind, assigned[(si, bi)])
        candidate = self._layout
        for set_index, bay_index, features in plan:
            candidate = unlink_setting(
                candidate, set_index=set_index, bay_index=bay_index, kind=kind
            )
            candidate = edit_setting(
                candidate, set_index=set_index, bay_index=bay_index,
                kind=kind, value=features
            )
            candidate = unlink_setting(
                candidate, set_index=set_index, bay_index=bay_index,
                kind=version_kind,
            )
            candidate = edit_setting(
                candidate, set_index=set_index, bay_index=bay_index,
                kind=version_kind, value=assigned[(set_index, bay_index)],
            )
        self._layout = candidate
        self._session_dirty_ids.update(
            str(self._layout["sets"][si]["bays"][bi]["stable_id"])
            for si, bi, _ in plan
        )
        return len(plan)

    def apply_inner_door_candidate_to_bays(self, config, set_index, bay_indices, *, version_id=None):
        """Apply one isolated inner-door candidate only to real highlighted Bays."""
        from ae_engine.receiving_inner_door_candidates import validate_door_config
        from ae_engine.receiving_shared_settings import unlink_setting, edit_setting
        source = validate_door_config(config)
        from ae_engine.receiving_shared_settings import validate_setting
        version_id = validate_setting("inner_door_version_id", version_id)
        if type(set_index) is not int or not 0 <= set_index < len(self._layout["sets"]):
            raise ValueError("選取的套不存在")
        selected = tuple(sorted(set(bay_indices)))
        count = len(self._layout["sets"][set_index]["bays"])
        if not selected or any(type(i) is not int or not 0 <= i < count
                               for i in selected):
            raise ValueError("請在簡易圖高亮有效的連")
        # A native Hole Editor CUTTING Feature and a submitted NFBConfig must
        # never both own the same physical inner-door opening.
        if source.get("features") and any(
            self._layout["sets"][set_index]["bays"][bi].get("nfb_config_submitted") is True
            for bi in selected
        ):
            raise ValueError("此連 NFB 已提交；不得將另一份內門開孔覆寫成重複 CUTTING")
        candidate = self._layout
        for bi in selected:
            for kind, value in (
                ("inner_door_layers", source["layers"]),
                ("inner_door_models", source["models"]),
                ("inner_door_features", source.get("features", {})),
                ("inner_door_layer_heights_mm", source.get("layer_heights_mm")),
                ("inner_door_version_id", version_id),
            ):
                candidate = unlink_setting(
                    candidate, set_index=set_index, bay_index=bi, kind=kind,
                )
                candidate = edit_setting(
                    candidate, set_index=set_index, bay_index=bi,
                    kind=kind, value=value,
                )
        self._layout = candidate
        self._session_dirty_ids.update(
            str(candidate["sets"][set_index]["bays"][bi]["stable_id"])
            for bi in selected
        )
        return selected

    def mark_live_version_for_bays(self, role, set_index, bay_indices):
        """Explicit 即時 Apply only labels highlighted Bays, not their geometry."""
        if role not in ("head", "tail", "inner-door"):
            raise ValueError("不支援的版本角色")
        if type(set_index) is not int or not 0 <= set_index < len(self._layout["sets"]):
            raise ValueError("套不存在")
        indices = tuple(sorted(set(bay_indices)))
        count = len(self._layout["sets"][set_index]["bays"])
        if not indices or any(type(bi) is not int or not 0 <= bi < count for bi in indices):
            raise ValueError("請先高亮有效的連")
        from ae_engine.receiving_shared_settings import unlink_setting, edit_setting
        kind = role.replace("-", "_") + "_version_id"
        candidate = self._layout
        for bi in indices:
            candidate = unlink_setting(
                candidate, set_index=set_index, bay_index=bi, kind=kind,
            )
            candidate = edit_setting(
                candidate, set_index=set_index, bay_index=bi,
                kind=kind, value="",
            )
        self._layout = candidate
        self._session_dirty_ids.update(
            str(candidate["sets"][set_index]["bays"][bi]["stable_id"])
            for bi in indices
        )
        return indices

    def apply_inner_door_quantity_configuration(
            self, library, quantities, assigned, *, expected_counts=None):
        """Validate every Set/Bay first, then replace both inner-door settings."""
        from ae_engine.receiving_inner_door_pairing import validate_inner_door_allocation
        from ae_engine.receiving_shared_settings import unlink_setting, edit_setting
        plan = validate_inner_door_allocation(
            self._layout, library, quantities, assigned,
            expected_counts=expected_counts,
        )
        from ae_engine.receiving_shared_settings import validate_setting
        for si, bi, config in plan:
            validate_setting("inner_door_version_id", assigned[(si, bi)])
            if (config.get("features")
                    and self._layout["sets"][si]["bays"][bi].get("nfb_config_submitted") is True):
                raise ValueError("已提交 NFB 與候選內門開孔不得成為雙重 CUTTING owner")
        candidate = self._layout
        for si, bi, config in plan:
            for kind, value in (
                ("inner_door_layers", config["layers"]),
                ("inner_door_models", config["models"]),
                ("inner_door_features", config.get("features", {})),
                ("inner_door_layer_heights_mm", config.get("layer_heights_mm")),
                ("inner_door_version_id", assigned[(si, bi)]),
            ):
                candidate = unlink_setting(
                    candidate, set_index=si, bay_index=bi, kind=kind,
                )
                candidate = edit_setting(
                    candidate, set_index=si, bay_index=bi, kind=kind, value=value,
                )
        self._layout = candidate
        self._session_dirty_ids.update(
            str(candidate["sets"][si]["bays"][bi]["stable_id"])
            for si, bi, _ in plan
        )
        return len(plan)


    def _nfb_apply_outcome(self, outcome):
        """Commit an already validated, atomically prepared NFB transaction."""
        if outcome.changed:
            self._layout = outcome.layout
            self._nfb_undo_receipts.append(outcome.receipt)
            self._session_dirty_ids.update(
                change.stable_id for change in outcome.receipt.changes
            )
        return outcome

    def submit_nfb_to_bays(
        self, *, set_index, bay_indices, version_id, configs, evidence, confirm,
    ):
        from ae_engine.receiving_nfb_transactions import submit_nfb_bays
        return self._nfb_apply_outcome(submit_nfb_bays(
            self._layout, set_index=set_index, bay_indices=bay_indices,
            version_id=version_id, configs=configs, evidence=evidence,
            confirm=confirm,
        ))

    def copy_submitted_nfb_to_bay(
        self, *, set_index, source_bay_index, target_bay_index,
        version_id, target_config, evidence, confirm,
    ):
        from ae_engine.receiving_nfb_transactions import copy_submitted_nfb_bay
        return self._nfb_apply_outcome(copy_submitted_nfb_bay(
            self._layout, set_index=set_index,
            source_bay_index=source_bay_index, target_bay_index=target_bay_index,
            version_id=version_id, target_config=target_config,
            evidence=evidence, confirm=confirm,
        ))

    def restore_nfb_unconfigured(self, *, set_index, bay_indices, confirm):
        from ae_engine.receiving_nfb_transactions import restore_nfb_bays_unconfigured
        return self._nfb_apply_outcome(restore_nfb_bays_unconfigured(
            self._layout, set_index=set_index, bay_indices=bay_indices,
            confirm=confirm,
        ))

    @property
    def nfb_can_undo(self):
        return bool(self._nfb_undo_receipts)

    def undo_last_nfb_transaction(self):
        from ae_engine.receiving_nfb_transactions import undo_nfb_transaction
        if not self._nfb_undo_receipts:
            raise ValueError("沒有可復原的內門 NFB 操作")
        receipt = self._nfb_undo_receipts[-1]
        restored = undo_nfb_transaction(self._layout, receipt)
        self._layout = restored
        self._nfb_undo_receipts.pop()
        self._session_dirty_ids.update(change.stable_id for change in receipt.changes)
        return receipt

    def set_global_brand(self, brand):
        """Update every Set NFB once, keeping active Set/Bay identity intact."""
        from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS
        if brand not in RECEIVING_SWITCH_BRANDS:
            raise ValueError("不支援的開關品牌")
        changed = False
        for set_row in self._layout["sets"]:
            if set_row.get("switch_brand", "士林") != brand:
                set_row["switch_brand"] = brand
                changed = True
        return changed

    def current_joint_editability(self, joint_index: int) -> dict[str, bool]:
        return receiving_joint_alignment_editability(
            self._layout,
            set_index=self._selection.set_index,
            joint_index=int(joint_index),
        )

    def update_joint_alignment(
        self,
        joint_index: int,
        *,
        depth_alignment: object | None = None,
        height_alignment: object | None = None,
    ) -> None:
        self._layout = update_receiving_joint_alignment(
            self._layout,
            set_index=self._selection.set_index,
            joint_index=int(joint_index),
            depth_alignment=depth_alignment,
            height_alignment=height_alignment,
        )
        row = self._layout["sets"][self._selection.set_index]["joints"][int(joint_index)]
        self._session_dirty_ids.add(str(row["stable_id"]))

    def project_current_bay(self, snapshot: Mapping[str, object]) -> dict[str, object]:
        payload = deepcopy(dict(snapshot or {}))
        payload["receiving_layout"] = self.layout
        return project_receiving_bay_legacy_aliases(
            payload,
            set_index=self._selection.set_index,
            bay_index=self._selection.bay_index,
            validate_common=True,
        )
    def project_manufacturing_readiness(
        self,
        failures: Iterable[ReceivingManufacturingFailure] = (),
    ) -> tuple[dict[str, object], ...]:
        """Project READY/BLOCKED diagnostics without becoming validity authority."""
        report = evaluate_receiving_manufacturing_readiness(self._layout, failures)
        return receiving_readiness_projection(report)



class ReceivingSwitchProjectionAdapter:
    """舊套／連 controls facade；唯一資料為 ReceivingSetBayAdapter。"""
    def __init__(self, adapter):
        self.adapter = adapter

    @property
    def layout(self):
        return self.adapter.layout

    @property
    def brand(self):
        selected = self.adapter.layout["sets"][self.adapter.selection.set_index]
        return selected.get("switch_brand", "士林")

    def connection_counts(self):
        return tuple(len(row["bays"]) for row in self.adapter.layout["sets"])

    def connection_count(self, index):
        return self.connection_counts()[index]

    def set_brand(self, brand):
        from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS
        if brand not in RECEIVING_SWITCH_BRANDS:
            raise ValueError("不支援的開關品牌")
        changed = self.brand != brand
        self.adapter.set_brand(brand)
        return changed

    def add_layer(self):
        self.adapter.set_set_count(len(self.adapter.layout["sets"]) + 1)

    def remove_layer(self):
        count = len(self.adapter.layout["sets"])
        if count == 1:
            return False
        self.adapter.set_set_count(count - 1)
        return True

    def resize_connections(self, index, delta):
        current = self.connection_count(index)
        wanted = max(1, current + delta)
        if wanted == current:
            return False
        self.adapter.select_set(index + 1)
        self.adapter.set_bay_count(wanted)
        return True
