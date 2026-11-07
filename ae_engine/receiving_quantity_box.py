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
    except (TypeError, ValueError, OverflowError) as exc:
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
        from .receiving_quantity_versions import QuantityModel, SCHEMA_V3
        model = QuantityModel.from_payload(quantity)
        # Preserve EXACT pre-v3 common-box projection/cache semantics for all
        # existing projects. Only an explicitly version-owned V3 brand may
        # replace the synthetic singleton Set's in-memory NFB parent.
        # Never write that selected brand back into the common physical box.
        if quantity.get("schema") == SCHEMA_V3:
            row["switch_brand"] = model.nfb_parent_brand_for_version(
                model.selected_version_id, legacy_default=box["switch_brand"],
            )
        submitted = model.nfb_config_for_version(model.selected_version_id)
        if submitted:
            # The selected Quantity version is the source; the synthetic Bay
            # is only a 2D/3D projection. Never project a previously
            # CONFIRMED W800 X into a newly W750 common physical box. Reuse
            # the canonical Set/Bay datum checker before rendering, without
            # inventing an X or mutating the caller's saved object.
            from .receiving_nfb_persistence import normalize_nfb_saved_fields
            checked = normalize_nfb_saved_fields({
                **submitted, "width": box["w"],
            })
            if checked != submitted:
                model.set_version_nfb_config(
                    model.selected_version_id, submitted=True,
                    config=checked["nfb_config"],
                )
                result["quantity"] = model.snapshot()
            bay.update(deepcopy(checked))
            result.update(deepcopy(checked))
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
    if not isinstance(snapshot, Mapping) or snapshot.get("active_mode") != "quantity":
        return ()
    from .receiving_quantity_versions import QuantityModel
    from ae_engine.cabinet_types.receiving import is_receiving_snapshot
    from ae_engine.sheetmetal_features import (
        resolve_endcap_finished_face_guide, feature_surface_from_rect,
        feature_is_within_surface,
    )
    box = (
        normalize_common_box(snapshot.get(BOX_KEY))
        if (is_receiving_snapshot(snapshot) or BOX_KEY in snapshot)
        else {axis: positive_dimension(snapshot.get(axis), axis) for axis in ("w", "d")}
    )
    raw_t = snapshot.get("t")
    model = QuantityModel.from_payload(snapshot.get("quantity"))
    # A missing persisted T is not permission to manufacture with a guessed
    # 2.0-mm sheet. Fail closed for versions containing hole features while
    # keeping this diagnostic function non-throwing on legacy snapshots.
    surface = None
    if raw_t is not None:
        try:
            t = positive_dimension(raw_t, "t")
            guide = resolve_endcap_finished_face_guide(box["w"], box["d"], t)
            surface = feature_surface_from_rect(
                "endcap_finished_face", guide.min_point, guide.max_point,
            )
        except (TypeError, ValueError, AttributeError, OverflowError):
            surface = None
    errors = []
    for version in model.snapshot()["versions"]:
        for role in ("head", "tail"):
            for index, feature in enumerate(version[f"{role}_features"], 1):
                if surface is None:
                    valid = False
                else:
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




def commit_operator_quantity_version_action(
    snapshot, quantity_model, *, action, version_id, piece_count=None,
    confirmed=False,
):
    """Commit one Quantity version operation on its Engine-owned live model.

    An isolated copy is validated first. Only one workspace notification is
    allowed, and a failed callback restores the original model without
    issuing another notification.
    """
    from .receiving_quantity_versions import QuantityModel

    if (not isinstance(snapshot, Mapping)
            or snapshot.get("active_mode") != "quantity"
            or not isinstance(quantity_model, QuantityModel)):
        raise ValueError("QUANTITY_VERSION_SOURCE_REQUIRED")
    original = quantity_model.snapshot()
    if snapshot.get("quantity") != original:
        raise ValueError("QUANTITY_VERSION_SOURCE_DRIFT")
    if action not in {"select", "add", "delete", "count"}:
        raise ValueError("QUANTITY_VERSION_ACTION_UNSUPPORTED")
    if not isinstance(version_id, str) or not version_id:
        raise ValueError("QUANTITY_VERSION_ID_REQUIRED")
    if action != "select" and version_id != original["selected_version_id"]:
        raise ValueError("QUANTITY_VERSION_SELECTED_ID_DRIFT")
    if action != "count" and piece_count is not None:
        raise ValueError("QUANTITY_VERSION_UNEXPECTED_COUNT")
    if action != "delete" and confirmed is not False:
        raise ValueError("QUANTITY_VERSION_UNEXPECTED_CONFIRMATION")
    if action == "delete" and type(confirmed) is not bool:
        raise ValueError("QUANTITY_VERSION_INVALID_CONFIRMATION")

    def apply(owner):
        if action == "select":
            return owner.select(version_id)
        if action == "add":
            return owner.add_version()
        if action == "delete":
            return owner.delete_selected(confirmed=confirmed)
        return owner.set_piece_count(piece_count)

    detached = QuantityModel.from_payload(original)
    result = apply(detached)
    expected = detached.snapshot()
    # Navigation must remain available to repair invalid historical holes.
    # Actual manufacturing-source mutations are validated before commit.
    if expected != original and action != "select":
        candidate = deepcopy(dict(snapshot))
        candidate["quantity"] = expected
        require_valid_quantity_features(candidate)
    if quantity_model.snapshot() != original:
        raise ValueError("QUANTITY_VERSION_CHANGED_DURING_VALIDATION")
    if expected == original:
        return result
    try:
        committed = apply(quantity_model)
        if quantity_model.snapshot() != expected:
            raise ValueError("QUANTITY_VERSION_COMMITTED_SOURCE_DRIFT")
    except Exception:
        quantity_model._restore_validated_owner_snapshot(original)
        raise
    return committed


def commit_operator_quantity_version_holes(
    snapshot, quantity_model, *, version_id, role, features,
):
    """Validate and commit a captured Quantity Head/Tail version in one Engine call.

    The incoming snapshot is a detached physical-source projection; the live
    QuantityModel is the sole writable owner. Validate every version against
    the canonical finished-face surfaces before a single change notification.
    A stale, deleted or switched editor may not overwrite a different version.
    """
    from .receiving_quantity_versions import QuantityModel

    if (not isinstance(snapshot, Mapping)
            or snapshot.get("active_mode") != "quantity"
            or not isinstance(quantity_model, QuantityModel)):
        raise ValueError("QUANTITY_HOLE_SOURCE_REQUIRED")
    original = quantity_model.snapshot()
    if snapshot.get("quantity") != original:
        raise ValueError("QUANTITY_HOLE_SOURCE_VERSION_DRIFT")

    detached = QuantityModel.from_payload(original)
    detached.set_version_features(version_id, role, features)
    expected = detached.snapshot()
    candidate = deepcopy(dict(snapshot))
    candidate["quantity"] = expected
    require_valid_quantity_features(candidate)
    if quantity_model.snapshot() != original:
        raise ValueError("QUANTITY_HOLE_SOURCE_CHANGED_DURING_VALIDATION")
    if expected == original:
        return False

    try:
        quantity_model.set_version_features(version_id, role, features)
        if quantity_model.snapshot() != expected:
            raise ValueError("QUANTITY_HOLE_COMMITTED_VERSION_DRIFT")
    except Exception:
        # Restore without notifying UI a second time after callback failure.
        quantity_model._restore_validated_owner_snapshot(original)
        raise
    return True


def _require_operator_receiving_quantity_source(snapshot):
    """Return the real Quantity version and box, never a synthetic Bay owner."""
    from .cabinet_types.policy import canonical_family_name
    from .receiving_quantity_versions import QuantityModel

    if (not isinstance(snapshot, Mapping)
            or canonical_family_name(snapshot) != "受電箱"
            or snapshot.get("active_mode") != "quantity"):
        raise ValueError("RECEIVING_SINGLE_QUANTITY_MODE_REQUIRED")
    if BOX_KEY not in snapshot or "quantity" not in snapshot:
        raise ValueError("RECEIVING_SINGLE_QUANTITY_SOURCE_REQUIRED")
    box = normalize_common_box(snapshot[BOX_KEY])
    model = QuantityModel.from_payload(snapshot["quantity"])
    return box, model


def project_operator_receiving_quantity_size_count(snapshot):
    """Read a physical common W/H/D and Quantity version piece counts.

    This is a read-only operator projection, not a new persisted owner.
    """
    box, model = _require_operator_receiving_quantity_source(snapshot)
    return {
        "width": box["w"], "height": box["h"], "depth": box["d"],
        "count": model.selected_piece_count,
        "total_count": model.total_piece_count,
        "version_count": model.version_count,
    }


def apply_operator_receiving_quantity_size_count(
    snapshot, *, width, height, depth, count,
):
    """Detached Engine transaction for Quantity W/H/D and piece count.

    The canonical Engine validates the entire resulting physical box,
    selected version and all head/tail hole features BEFORE any GUI mode
    publish. Never mutate the original project or calculate manufacture
    geometry in the GUI.
    """
    from .receiving_quantity_versions import positive_piece_count

    _, model = _require_operator_receiving_quantity_source(snapshot)
    # Saved material T is a physical source: no fabricated GUI default.
    positive_dimension(snapshot.get("t"), "t")
    selected_count = positive_piece_count(count)
    model.set_piece_count(selected_count)
    projected = update_common_box(
        snapshot, {"w": width, "h": height, "d": depth},
    )
    projected["quantity"] = model.snapshot()
    require_valid_quantity_features(projected)
    return projected
