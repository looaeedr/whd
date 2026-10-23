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
    # Unconfigured quantity projects use the Receiving Family default.
    # Do not open an initialization dialog or silently copy Set/Bay values.
    # An explicitly supplied but malformed box still fails closed.
    if value is None:
        from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS
        value = {axis: int(BOX_BODY_DEFAULTS[axis]) for axis in ("w", "h", "d")}
    elif not isinstance(value, Mapping):
        raise ValueError("共用箱體資料格式錯誤")
    allowed = {"w", "h", "d", "back_panel_mode", "inner_door_layers",
               "inner_door_models", "inner_door_layer_heights_mm",
               "receiving_base_plate", "switch_brand", "door_state"}
    if set(value) - allowed:
        raise ValueError("共用箱體不能保存 Set/Bay、Joint 或孔型版本資料")
    result = {axis: positive_dimension(value.get(axis), axis) for axis in ("w", "h", "d")}
    for kind in ("back_panel_mode", "inner_door_layers"):
        result[kind] = validate_setting(kind, value.get(kind, "FULL" if kind == "back_panel_mode" else 1))
    brand = value.get("switch_brand", RECEIVING_SWITCH_BRANDS[0])
    if brand not in RECEIVING_SWITCH_BRANDS:
        raise ValueError("不支援的開關品牌")
    result["switch_brand"] = brand
    # In quantity mode this common physical box owns its NFB row settings.
    # Root aliases and its synthetic one-Bay projection get rebuilt on every
    # refresh. Persisting only the aliases loses the operator's layer count,
    # CSV model choice and Y after the Hole Editor Confirm All.
    for kind in ("inner_door_models", "inner_door_layer_heights_mm"):
        if kind in value:
            result[kind] = validate_setting(kind, value[kind])
    if value.get("receiving_base_plate") is not None:
        plate = value["receiving_base_plate"]
        if not isinstance(plate, Mapping):
            raise ValueError("單只底板來源須為實體型式設定")
        result["receiving_base_plate"] = deepcopy(dict(plate))
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
    if "door_state" not in box:
        # Older quantity files saved the common dimensions but omitted its Door
        # authority. Cached Fold profiles and Set/Bay aliases are not authority:
        # initialize the same Family topology as a fresh quantity cabinet.
        from ae_engine.cabinet_types import receiving
        from ae_engine.receiving_layout import RECEIVING_DOOR_STATE_KEYS
        from ae_engine.sheetmetal_part_adapters import complete_partition

        defaults = receiving.apply_family_defaults({"t": result.get("t", 2.0)})
        result.setdefault("t", defaults["t"])
        family_columns = receiving.default_door_layout_columns()
        widths = complete_partition([row[0] for row in family_columns[:-1]], box["w"])
        if not widths.valid or len(widths.values) != len(family_columns):
            raise ValueError("W 不符合 Family 門分割")
        columns = []
        for width, (_, heights) in zip(widths.values, family_columns):
            partition = complete_partition(heights[:-1], box["h"])
            if not partition.valid or len(partition.values) != len(heights):
                raise ValueError("H 不符合 Family 門分割")
            columns.append([width, list(partition.values)])
        defaults["door_layout_columns"] = columns
        box["door_state"] = {
            key: deepcopy(defaults[key])
            for key in RECEIVING_DOOR_STATE_KEYS if key in defaults
        }
    result[BOX_KEY] = box
    # The quantity common box owns its one physical Base Plate variant.
    # Root receiving_base_plate is only the current assembly projection.
    if "receiving_base_plate" in box:
        result["receiving_base_plate"] = deepcopy(box["receiving_base_plate"])
    else:
        result.pop("receiving_base_plate", None)
    result.update({axis: box[axis] for axis in ("w", "h", "d")})
    if "door_state" in box:
        result.update(deepcopy(box["door_state"]))
    layout = new_receiving_layout(width=box["w"], height=box["h"], depth=box["d"],
                                  back_panel_mode=box["back_panel_mode"])
    row = layout["sets"][0]
    row["switch_brand"] = box["switch_brand"]
    bay = row["bays"][0]
    bay["inner_door_layers"] = box["inner_door_layers"]
    for kind in ("inner_door_models", "inner_door_layer_heights_mm"):
        if kind in box:
            bay[kind] = deepcopy(box[kind])
            result["receiving_" + kind] = deepcopy(box[kind])
    if "door_state" in box:
        bay["door_state"] = deepcopy(box["door_state"])
    # This singleton Bay exists solely to project the selected quantity
    # version into the SAME assembly solver as regular Set/Bay mode.
    # Keep NFB submission owned by QuantityModel, never the synthetic Bay.
    result.pop("nfb_config_submitted", None)
    result.pop("nfb_config", None)
    quantity = result.get("quantity")
    if isinstance(quantity, Mapping):
        from phase6_quantity_model import QuantityModel
        model = QuantityModel.from_payload(quantity)
        submitted = model.nfb_config_for_version(model.selected_version_id)
        if submitted:
            bay.update(deepcopy(submitted))
            result.update(deepcopy(submitted))
    row["settings"] = normalize_set_settings(None, row["bays"])
    result["receiving_layout"] = layout
    # Quantity mode has just replaced the entire Set/Bay identity graph.
    # A previous Set/Bay runtime selector (even with index 0) is NOT the
    # identity of this new synthetic singleton. Remove that ephemeral pointer;
    # consumers needing a selector must project this actual layout afresh.
    # Do not weaken the strict EAR_Z_SET_IDENTITY_DRIFT manufacturer guard.
    from .receiving_layout import RECEIVING_RUNTIME_SELECTION_KEY
    result.pop(RECEIVING_RUNTIME_SELECTION_KEY, None)
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
        # Older/default Quantity workspaces can omit their own Door authority
        # even though the Family topology exists. Resolve that existing
        # canonical Family partition BEFORE resizing; never guess a new split.
        # An explicitly supplied but invalid Door authority remains an error.
        if "door_state" not in current:
            family = project_common_box({**result, BOX_KEY: current})
            door = deepcopy(family[BOX_KEY]["door_state"])
        else:
            door = deepcopy(current["door_state"])
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
    if snapshot.get("active_mode") != "quantity":
        return ()
    from phase6_quantity_model import QuantityModel
    from ae_engine.sheetmetal_features import (
        resolve_endcap_finished_face_guide, feature_surface_from_rect,
        feature_is_within_surface,
    )
    box = normalize_common_box(snapshot.get(BOX_KEY)) if snapshot.get("model") == "受電箱" else {axis: positive_dimension(snapshot.get(axis), axis) for axis in ("w", "d")}
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
