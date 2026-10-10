"""Feature-only quantity versions; shared shape belongs to the existing workspace.

The model owns IDs, selection, piece counts and head/tail features. It neither
copies cabinet dimensions nor writes project files. Receiving mode initialization
belongs to the Receiving mode controller.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Mapping

SCHEMA = "phase6-quantity-v1"
QUANTITY_MODE = "quantity"
SET_BAY_MODE = "set_bay"
_VERSION_KEYS = {"version_id", "piece_count", "head_features", "tail_features"}
_PAYLOAD_KEYS = {"schema", "versions", "selected_version_id", "next_version_number"}
_SESSION_KEYS = ("_mode_buffers", "_quantity_session", "_set_bay_session", "_quantitySession", "_setBaySession")
_ID_PATTERN = re.compile(r"quantity-v([1-9][0-9]*)\Z")


def positive_piece_count(value) -> int:
    """Accept integral UI text or an integer, never booleans/floats."""
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        number = int(value.strip())
        if number > 0:
            return number
    raise ValueError("件數必須為正整數")


def _features(values):
    if not isinstance(values, (list, tuple)):
        raise ValueError("封頭／封尾 Features 必須為清單")
    return deepcopy(list(values))


class QuantityModel:
    """One working-state owner with copy boundaries at every public projection."""

    def __init__(self, *, head_features=(), tail_features=(), on_change=None):
        self._versions = [{
            "version_id": "quantity-v1", "piece_count": 1,
            "head_features": _features(head_features),
            "tail_features": _features(tail_features),
        }]
        self._selected = "quantity-v1"
        self._next_number = 2
        self._on_change = on_change

    @classmethod
    def from_payload(cls, payload: Mapping, *, on_change=None):
        if not isinstance(payload, Mapping) or set(payload) != _PAYLOAD_KEYS:
            raise ValueError("不合法的孔型版本資料")
        if payload["schema"] != SCHEMA:
            raise ValueError("不支援的孔型版本格式")
        rows = payload["versions"]
        if not isinstance(rows, (list, tuple)) or not rows:
            raise ValueError("至少保留一個孔型版本")
        validated = []
        numbers = set()
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != _VERSION_KEYS:
                raise ValueError("孔型版本只能保存封頭／封尾 Features 和件數，不能保存獨立外形")
            match = _ID_PATTERN.fullmatch(str(row["version_id"]))
            if not match or int(match[1]) in numbers:
                raise ValueError("孔型版本 ID 不合法或重複")
            numbers.add(int(match[1]))
            validated.append({
                "version_id": row["version_id"],
                "piece_count": positive_piece_count(row["piece_count"]),
                "head_features": _features(row["head_features"]),
                "tail_features": _features(row["tail_features"]),
            })
        selected = payload["selected_version_id"]
        if selected not in {row["version_id"] for row in validated}:
            raise ValueError("目前選取的孔型版本不存在")
        next_number = payload["next_version_number"]
        if type(next_number) is not int or next_number <= max(numbers):
            raise ValueError("孔型版本 ID 產生器不得復用既有 ID")
        result = cls(on_change=on_change)
        result._versions = validated
        result._selected = selected
        result._next_number = next_number
        return result

    def _selected_row(self):
        return next(row for row in self._versions if row["version_id"] == self._selected)

    def _changed(self):
        if self._on_change is not None:
            self._on_change()

    @property
    def selected_version_id(self):
        return self._selected

    @property
    def selected_piece_count(self):
        return self._selected_row()["piece_count"]

    @property
    def version_count(self):
        return len(self._versions)

    @property
    def total_piece_count(self):
        return sum(row["piece_count"] for row in self._versions)

    def select(self, version_id):
        if version_id not in {row["version_id"] for row in self._versions}:
            raise ValueError(f"孔型版本不存在: {version_id}")
        if self._selected != version_id:
            self._selected = version_id
            self._changed()

    def add_version(self):
        source = self._selected_row()
        new_row = deepcopy(source)
        new_row["version_id"] = f"quantity-v{self._next_number}"
        new_row["piece_count"] = 1
        index = self._versions.index(source)
        self._versions.insert(index + 1, new_row)
        self._next_number += 1
        self._selected = new_row["version_id"]
        self._changed()
        return self._selected

    def delete_selected(self, *, confirmed: bool):
        if confirmed is not True or len(self._versions) == 1:
            return False
        index = self._versions.index(self._selected_row())
        del self._versions[index]
        self._selected = self._versions[min(index, len(self._versions) - 1)]["version_id"]
        self._changed()
        return True

    def set_piece_count(self, value):
        count = positive_piece_count(value)
        row = self._selected_row()
        if row["piece_count"] != count:
            row["piece_count"] = count
            self._changed()

    def features_for_version(self, version_id, part):
        if part not in {"head", "tail"}:
            raise ValueError("孔型版本只覆寫封頭／封尾 Features")
        row = next((row for row in self._versions if row["version_id"] == version_id), None)
        if row is None:
            raise ValueError(f"孔型版本不存在: {version_id}")
        return deepcopy(row[f"{part}_features"])

    def set_version_features(self, version_id, part, features):
        self.features_for_version(version_id, part)
        copied = _features(features)
        row = next(row for row in self._versions if row["version_id"] == version_id)
        if row[f"{part}_features"] != copied:
            row[f"{part}_features"] = copied
            self._changed()

    def features_for(self, part):
        if part not in {"head", "tail"}:
            raise ValueError("孔型版本只覆寫封頭／封尾 Features")
        return deepcopy(self._selected_row()[f"{part}_features"])

    def set_features(self, part, features):
        if part not in {"head", "tail"}:
            raise ValueError("孔型版本只覆寫封頭／封尾 Features")
        copied = _features(features)
        row = self._selected_row()
        if row[f"{part}_features"] != copied:
            row[f"{part}_features"] = copied
            self._changed()

    def snapshot(self):
        return {
            "schema": SCHEMA, "versions": deepcopy(self._versions),
            "selected_version_id": self._selected,
            "next_version_number": self._next_number,
        }


def normalize_quantity_snapshot(snapshot, *, for_save=False):
    """Migrate legacy projects and strip transient/inactive mode data on Save.

    Selected head/tail aliases are a runtime projection only. The persisted
    quantity model is the sole owner of per-version features.
    """
    result = deepcopy(dict(snapshot or {}))
    from ae_engine.cabinet_types.receiving import is_receiving_snapshot
    receiving = is_receiving_snapshot(result)
    mode = result.get("active_mode", SET_BAY_MODE if receiving else QUANTITY_MODE)
    if mode not in {QUANTITY_MODE, SET_BAY_MODE} or (not receiving and mode != QUANTITY_MODE):
        raise ValueError("不合法的箱體操作模式")
    result["active_mode"] = mode
    if for_save:
        for key in _SESSION_KEYS:
            result.pop(key, None)
    if for_save and isinstance(result.get("workspace"), Mapping):
        workspace = deepcopy(dict(result["workspace"]))
        for key in _SESSION_KEYS:
            workspace.pop(key, None)
        workspace.pop("receiving_layout", None)
        workspace.pop("receiving_quantity_box", None)
        workspace.pop("quantity", None)
        if mode == SET_BAY_MODE:
            workspace.pop("receiving_quantity_box", None)
            workspace.pop("quantity", None)
        result["workspace"] = workspace
    if mode == SET_BAY_MODE:
        result.pop("quantity", None)
        result.pop("receiving_quantity_box", None)
        return result
    payload = result.get("quantity")
    if payload is None:
        if receiving:
            raise ValueError("受電箱數量模式必須由明確初始化的共用箱體與孔型版本建立")
        workspace = dict(result.get("workspace") or {})
        part_features = dict(result.get("part_features") or workspace.get("part_features") or {})
        model = QuantityModel(head_features=part_features.get("head", ()),
                              tail_features=part_features.get("tail", ()))
    else:
        model = QuantityModel.from_payload(payload)
    result["quantity"] = model.snapshot()
    if receiving:
        from ae_engine.receiving_quantity_box import BOX_KEY, normalize_common_box
        result[BOX_KEY] = normalize_common_box(result.get(BOX_KEY))
        if for_save:
            result.pop("receiving_layout", None)
            result.pop("receiving_switch_layout", None)
            result.pop("_receiving_runtime_selection", None)
            for role in ("head", "tail"):
                result.pop(f"{role}_holes", None)
            surface = deepcopy(dict(result.get("surface_features") or {}))
            for role in ("head", "tail"):
                surface.pop(role, None)
            result["surface_features"] = surface
    part_features = deepcopy(dict(result.get("part_features") or {}))
    for part in ("head", "tail"):
        if for_save:
            part_features.pop(part, None)
        else:
            part_features[part] = model.features_for(part)
    result["part_features"] = part_features
    # Older snapshots duplicate features inside workspace; remove that alias
    # too on persistence so stale selected-version values cannot win on Reload.
    if isinstance(result.get("workspace"), Mapping):
        workspace = deepcopy(dict(result["workspace"]))
        if "part_features" in workspace:
            features = deepcopy(dict(workspace["part_features"]))
            for part in ("head", "tail"):
                if for_save:
                    features.pop(part, None)
                else:
                    features[part] = model.features_for(part)
            workspace["part_features"] = features
        result["workspace"] = workspace
    return result


def quantity_only_change(previous, current):
    """Prove all shared cabinet inputs unchanged for a quantity UI transaction."""
    if not isinstance(previous, Mapping) or not isinstance(current, Mapping):
        return False
    old, new = deepcopy(dict(previous)), deepcopy(dict(current))
    changed = False
    for payload in (old, new):
        workspace = payload.get("workspace") or {}
        if payload.get("active_mode", workspace.get("active_mode")) != QUANTITY_MODE:
            return False
        try:
            QuantityModel.from_payload(payload.get("quantity") or workspace.get("quantity"))
        except (TypeError, ValueError):
            return False
    for before, after in ((old, new), (old.get("workspace") or {}, new.get("workspace") or {})):
        changed = changed or before.get("quantity") != after.get("quantity")
        for block in (before, after):
            block.pop("quantity", None)
            for name in ("part_features", "surface_features"):
                mapping = block.get(name)
                if isinstance(mapping, Mapping):
                    for role in ("head", "tail"):
                        mapping.pop(role, None)
            for role in ("head", "tail"):
                block.pop(f"{role}_holes", None)
    for block in (old, new):
        for key in ("origin", "revision", "fingerprint", "transaction_id", "delta"):
            block.pop(key, None)
    return changed and old == new
