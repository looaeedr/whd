"""Receiving quantity common inputs projected through the existing Family adapter.

The singleton layout is an in-memory adapter for existing physical-sheet
consumers. It is never the persisted authority of quantity mode.
"""
from copy import deepcopy
from collections.abc import Mapping
import math

BOX_KEY = "receiving_quantity_box"


def positive_dimension(value, axis):
    if isinstance(value, bool):
        raise ValueError(f"{axis.upper()} 必須為有限正數")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{axis.upper()} 必須為有限正數") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{axis.upper()} 必須為有限正數")
    return number


def normalize_common_box(value):
    from ae_engine.receiving_shared_settings import validate_setting
    from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS
    if not isinstance(value, Mapping):
        raise ValueError("受電箱數量模式缺少明確初始化的共用箱體")
    allowed = {"w", "h", "d", "back_panel_mode", "inner_door_layers",
               "switch_brand", "door_state"}
    if set(value) - allowed:
        raise ValueError("共用箱體不能保存 Set/Bay、Joint 或孔型版本資料")
    result = {axis: positive_dimension(value.get(axis), axis) for axis in ("w", "h", "d")}
    for kind in ("back_panel_mode", "inner_door_layers"):
        result[kind] = validate_setting(kind, value.get(kind, "FULL" if kind == "back_panel_mode" else 1))
    brand = value.get("switch_brand", RECEIVING_SWITCH_BRANDS[0])
    if brand not in RECEIVING_SWITCH_BRANDS:
        raise ValueError("不支援的開關品牌")
    result["switch_brand"] = brand
    if "door_state" in value:
        from ae_engine.receiving_layout import RECEIVING_DOOR_STATE_KEYS
        door = value["door_state"]
        if not isinstance(door, Mapping) or set(door) - set(RECEIVING_DOOR_STATE_KEYS):
            raise ValueError("不合法的共用門分割設定")
        result["door_state"] = deepcopy(dict(door))
    return result


def project_common_box(snapshot):
    """Replace any old layout with the one explicitly initialized common box."""
    from ae_engine.receiving_layout import new_receiving_layout
    from ae_engine.receiving_shared_settings import normalize_set_settings
    result = deepcopy(dict(snapshot))
    box = normalize_common_box(result.get(BOX_KEY))
    result[BOX_KEY] = box
    result.update({axis: box[axis] for axis in ("w", "h", "d")})
    if "door_state" in box:
        result.update(deepcopy(box["door_state"]))
    layout = new_receiving_layout(width=box["w"], height=box["h"], depth=box["d"],
                                  back_panel_mode=box["back_panel_mode"])
    row = layout["sets"][0]
    row["switch_brand"] = box["switch_brand"]
    bay = row["bays"][0]
    bay["inner_door_layers"] = box["inner_door_layers"]
    if "door_state" in box:
        bay["door_state"] = deepcopy(box["door_state"])
    row["settings"] = normalize_set_settings(None, row["bays"])
    result["receiving_layout"] = layout
    result["receiving_inner_door_layers"] = box["inner_door_layers"]
    result.pop("receiving_switch_layout", None)
    return result


def update_common_box(snapshot, changes):
    """Validate a detached common edit before any workspace commit."""
    from ae_engine.receiving_layout import RECEIVING_DOOR_STATE_KEYS, _validate_common_receiving_state
    from ae_engine.sheetmetal_part_adapters import complete_partition
    result = deepcopy(dict(snapshot))
    current = normalize_common_box(result.get(BOX_KEY))
    box = normalize_common_box({**current, **deepcopy(dict(changes))})
    if "door_state" not in changes and (box["w"], box["h"]) != (current["w"], current["h"]):
        door = deepcopy(box.get("door_state", {}))
        old_columns = door.get("door_layout_columns", [])
        widths = complete_partition([row[0] for row in old_columns[:-1]], box["w"])
        if not old_columns or not widths.valid or len(widths.values) != len(old_columns):
            raise ValueError("W 不符合目前門分割；請調整共同門分割")
        columns = []
        for width, (_, heights) in zip(widths.values, old_columns):
            partition = complete_partition(heights[:-1], box["h"])
            if not partition.valid or len(partition.values) != len(heights):
                raise ValueError("H 不符合目前門分割；請調整共同門分割")
            columns.append([width, list(partition.values)])
        door["door_layout_columns"] = columns
        box["door_state"] = door
    result[BOX_KEY] = box
    result = project_common_box(result)
    _validate_common_receiving_state(result)
    return result


def quantity_feature_errors(snapshot):
    """Re-resolve every version against the existing finished-face authority."""
    if snapshot.get("active_mode") != "quantity" or snapshot.get("model") != "受電箱":
        return ()
    from phase6_quantity_model import QuantityModel
    from ae_engine.sheetmetal_features import (
        resolve_endcap_finished_face_guide, feature_surface_from_rect,
        feature_is_within_surface,
    )
    box = normalize_common_box(snapshot.get(BOX_KEY))
    model = QuantityModel.from_payload(snapshot.get("quantity"))
    guide = resolve_endcap_finished_face_guide(box["w"], box["d"], float(snapshot.get("t", 2)))
    surface = feature_surface_from_rect("endcap_finished_face", guide.min_point, guide.max_point)
    errors = []
    for version in model.snapshot()["versions"]:
        for role in ("head", "tail"):
            for index, feature in enumerate(version[f"{role}_features"], 1):
                try:
                    valid = feature_is_within_surface(surface, feature, box["w"], box["d"])
                except (AttributeError, TypeError, ValueError, KeyError, OverflowError):
                    valid = False
                if not valid:
                    errors.append(f'{version["version_id"]}／{"封頭" if role == "head" else "封尾"}／特徵 {index} 越界或失效')
    return tuple(errors)


def require_valid_quantity_features(snapshot):
    errors = quantity_feature_errors(snapshot)
    if errors:
        raise ValueError("不能輸出 DXF：" + "；".join(errors))
