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
        self._layout = resize_receiving_bays(
            self._layout,
            set_index=self._selection.set_index,
            bay_count=wanted,
        )
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
