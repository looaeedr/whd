"""Scratch bounded Receiving LEFT BasePlate marking source; never licenses DXF."""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import re

from .operator_manual_marking import (
    MANUAL_MARK_SOURCE, is_manual_round_mark, require_first_sheet_manual_marking_render,
)
from .physical_sheet_editor_context import resolve_physical_sheet_editor_context
from .receiving_layout import normalize_receiving_layout
from .sheetmetal_feature_core import CircleFeature, ProfileFeature

SCOPED_BASE_PLATE_MARKS = "receiving_base_plate_manual_marks"
_DIGEST = re.compile(r"[0-9a-f]{64}")
_OWNER = re.compile(r"receiving:base_plate:[0-9a-f]{32}:[1-9][0-9]{0,17}")


def normalize_scoped_base_plate_marks(snapshot):
    """Validate saved authored shape; intentionally retain rows for deleted owners."""
    return normalize_scoped_base_plate_mark_ledger(snapshot.get(SCOPED_BASE_PLATE_MARKS, {}))


def normalize_scoped_base_plate_mark_ledger(raw):
    if not isinstance(raw, Mapping):
        raise ValueError("SCOPED_MARK_LEDGER_INVALID")
    result = {}
    for owner, record in raw.items():
        if isinstance(record, Mapping):
            seal = record.get("source_sha256")
            if (set(record) != {"features", "source_sha256"}
                    or not isinstance(seal, str) or not _DIGEST.fullmatch(seal)):
                raise ValueError("SCOPED_MARK_SAVED_SOURCE_INVALID")
            features = record["features"]
        else:
            # The edit-only scratch ledger may pre-date export-source sealing.
            seal, features = None, record
        if not isinstance(owner, str) or not _OWNER.fullmatch(owner):
            raise ValueError("SCOPED_MARK_LEDGER_OWNER_INVALID")
        if not isinstance(features, (tuple, list)):
            raise ValueError("SCOPED_MARK_LEDGER_LINE_OR_CIRCLE_REQUIRED")
        decoded = []
        for mark in features:
            if isinstance(mark, Mapping):
                from .receiving_nfb_committed_final_scene import _physical_feature_from_transport
                mark = _physical_feature_from_transport(mark)
            if not is_scoped_base_plate_mark(mark):
                raise ValueError("SCOPED_MARK_LEDGER_LINE_OR_CIRCLE_REQUIRED")
            decoded.append(deepcopy(mark))
        if decoded:
            result[owner] = ({"features": decoded, "source_sha256": seal} if seal else decoded)
    return result


def _current_owners(snapshot):
    layout = snapshot.get("receiving_layout")
    if not isinstance(layout, Mapping) or snapshot.get("active_mode") == "quantity":
        return {}
    return {
        (si, bi): row.get("base_plate_owner_id")
        for si, selected in enumerate(normalize_receiving_layout(layout)["sets"])
        for bi, row in enumerate(selected["bays"])
    }


def scoped_base_plate_mark_status(snapshot):
    saved = normalize_scoped_base_plate_marks(snapshot)
    if not saved:
        return {}
    active = set(_current_owners(snapshot).values())
    return {owner: "present" if owner in active else "orphaned" for owner in saved}


def require_scoped_base_plate_export_held(snapshot, flags):
    """Only inhibit workflows selecting BasePlate while this ledger isn't consumed."""
    if not isinstance(snapshot, Mapping) or SCOPED_BASE_PLATE_MARKS not in snapshot:
        return
    if not flags.get("base_plate"):
        return
    raw = snapshot[SCOPED_BASE_PLATE_MARKS]
    if not isinstance(raw, Mapping) or raw:
        raise ValueError(
            "SCOPED_MARK_BASE_PLATE_EXPORT_NOT_RELEASED：此專案有已保存的分連底板打標，"
            "目前不可輸出底板 DXF；其他未選底板的板件不受影響"
        )


def require_scoped_base_plate_spec_export_held(snapshot, spec):
    from .contracts import BasePlatePartSpec
    if isinstance(spec, BasePlatePartSpec):
        require_scoped_base_plate_export_held(snapshot, {"base_plate": True})


def _source(context):
    render = context.render_data
    return (
        render.unfolded_topology, tuple(render.scene.primitives), render.material.wkb,
    )


@dataclass(frozen=True)
class ScopedBasePlateEditor:
    owner: str
    location: tuple[int, int]
    context: object
    physical_source: tuple
    saved_marks: tuple
    saved_seal: str | None


def open_scoped_base_plate_editor(snapshot, set_index, bay_index, *, expected_owner=None):
    if type(set_index) is not int or type(bay_index) is not int:
        raise ValueError("SCOPED_MARK_OWNER_REQUIRED")
    location = set_index, bay_index
    owner = _current_owners(snapshot).get(location)
    if owner is None:
        raise ValueError("SCOPED_MARK_OWNER_REQUIRED")
    if expected_owner is not None and owner != expected_owner:
        raise ValueError("SCOPED_MARK_EDITOR_OWNER_STALE")
    render = resolve_scoped_base_plate_render(snapshot, set_index, bay_index)
    require_first_sheet_manual_marking_render("base_plate", render)
    context = resolve_physical_sheet_editor_context("base_plate", render)
    record = normalize_scoped_base_plate_marks(snapshot).get(owner, ())
    if isinstance(record, Mapping):
        marks, seal = tuple(record["features"]), record["source_sha256"]
    else:
        marks, seal = tuple(record), None
    return ScopedBasePlateEditor(owner, location, context, _source(context), marks, seal)


def is_scoped_base_plate_mark(mark):
    return (isinstance(mark, ProfileFeature) and mark.source_type == MANUAL_MARK_SOURCE
            or isinstance(mark, CircleFeature) and is_manual_round_mark(mark))


def commit_scoped_base_plate_marks(snapshot, editor, marks):
    """Return detached ledger after verifying owner, physical source and concurrent edits."""
    from .physical_sheet_editor_context import propose_operator_physical_sheet_hole_features

    if _current_owners(snapshot).get(editor.location) != editor.owner:
        raise ValueError("SCOPED_MARK_EDITOR_OWNER_STALE")
    current = open_scoped_base_plate_editor(snapshot, *editor.location)
    if (current.physical_source != editor.physical_source or current.saved_marks != editor.saved_marks
            or current.saved_seal != editor.saved_seal):
        raise ValueError("SCOPED_MARK_EDITOR_SOURCE_STALE")
    saved = normalize_scoped_base_plate_marks(snapshot)
    checked = normalize_scoped_base_plate_marks({
        SCOPED_BASE_PLATE_MARKS: {editor.owner: marks},
    }).get(editor.owner, [])
    propose_operator_physical_sheet_hole_features("base_plate", current.context, checked)
    if checked:
        saved[editor.owner] = {"features": checked, "source_sha256": _physical_seal(editor.owner, current.context.render_data, snapshot["t"])}
    else:
        saved.pop(editor.owner, None)
    return saved


def resolve_scoped_base_plate_render(snapshot, set_index, bay_index):
    """Rebuild one explicitly selected Bay's original board, not an assembly or role alias."""
    from . import manufacturing_api as api
    from .contracts import ManufacturingContext, ResolvedManufacturingPart
    from .operator_manual_marking import require_first_sheet_manual_marking_spec

    if _current_owners(snapshot).get((set_index, bay_index)) is None:
        raise ValueError("SCOPED_MARK_EDITOR_OWNER_STALE")
    source = api.project_receiving_bay_legacy_aliases(
        snapshot, set_index=set_index, bay_index=bay_index,
    )
    workspace = snapshot.get("workspace") or {}
    for records in (snapshot.get("part_features"), workspace.get("part_features")):
        if isinstance(records, Mapping) and records.get("base_plate"):
            raise ValueError("SCOPED_MARK_LEGACY_ROLE_FEATURES_UNRESOLVED")
    # Never select a second Bay's plate by a shared root alias: require that
    # this Bay itself carries confirmed original NFB source.
    if source.get("nfb_config_submitted") is not True or not isinstance(source.get("nfb_config"), Mapping):
        raise ValueError("SCOPED_MARK_BAY_ORIGINAL_SOURCE_REQUIRED")
    source.pop("receiving_base_plate", None)
    values, policy = api.resolve_fold_designer_base_plate_source(
        "base_plate", source, width=source["w"], height=source["h"], thickness=source["t"],
        frame_width=source["fw"], model_name=source["model"],
    )
    spec = api.build_base_plate_operator_part_spec(values, features=(), corner_policy=policy)
    require_first_sheet_manual_marking_spec(spec)
    original = api.build_part_render_data(spec, ManufacturingContext())
    from .receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles
    from .receiving_nfb_committed_final_scene import apply_committed_csv_v5_to_canonical_parts

    placement = api.resolve_operator_assembly_placement(source, "base_plate")
    profiles = receiving_base_plate_3d_profiles(source)
    parts = apply_committed_csv_v5_to_canonical_parts(source, (
        ResolvedManufacturingPart(
            part_key="base_plate", render_data=original, placement="offset",
            x_profile=tuple(profiles["X"]), y_profile=tuple(profiles["Y"]),
            offset=placement.world_offset,
        ),
    ))
    if (len(parts) != 1 or parts[0].part_key != "base_plate"
            or parts[0].render_data is original):
        raise ValueError("SCOPED_MARK_CONFIRMED_PHYSICAL_CUTTING_REQUIRED")
    return parts[0].render_data


def _physical_seal(owner, render, thickness):
    # Exact locally canonical topology, CUTTING (including current holes),
    # BEND, material and pre-existing ink, WITHOUT persistent UI position or
    # callable identity. This witness is not a manufacturing approval.
    from .manufacturing_equivalence import ManufacturingParameters, manufacturing_equivalence_payload
    topology = render.unfolded_topology
    physical = manufacturing_equivalence_payload(
        render, ManufacturingParameters("SCOPED_MARK_SOURCE_ONLY", thickness, ""),
    )
    return sha256((owner + "\n" + repr(topology) + "\n" + physical).encode("utf-8")).hexdigest()


def plan_scoped_base_plate_normal_output(snapshot, flags, group_mode):
    if not flags.get("base_plate"):
        return {}
    saved = normalize_scoped_base_plate_marks(snapshot)
    if not saved:
        return {}
    from .manufacturing_export_selection import normalize_operator_selected_export_flags
    flags = normalize_operator_selected_export_flags(flags)
    if not flags.get("base_plate"):
        return {}
    owners = _current_owners(snapshot)
    if (group_mode is not None or not owners
            or snapshot.get("active_mode", "set_bay") != "set_bay"
            or any(value for key, value in flags.items() if key != "base_plate")):
        require_scoped_base_plate_export_held(snapshot, flags)
    active = {owner: location for location, owner in owners.items() if owner is not None}
    if set(saved) - set(active):
        raise ValueError("SCOPED_MARK_SAVED_OWNER_ORPHANED")
    if any(not isinstance(row, Mapping) for row in saved.values()):
        raise ValueError("SCOPED_MARK_SAVED_SOURCE_UNVERIFIED")
    return {active[owner]: (owner, row) for owner, row in saved.items()}


def apply_scoped_base_plate_output(snapshot, location, owner_row, render):
    from .physical_sheet_features import with_physical_sheet_features
    from .operator_manual_marking import verify_manual_marking_output

    owner, row = owner_row
    if _current_owners(snapshot).get(location) != owner:
        raise ValueError("SCOPED_MARK_SAVED_OWNER_STALE")
    require_first_sheet_manual_marking_render("base_plate", render)
    if _physical_seal(owner, render, snapshot["t"]) != row["source_sha256"]:
        raise ValueError("SCOPED_MARK_SAVED_PHYSICAL_SOURCE_CHANGED")
    marked = with_physical_sheet_features("base_plate", render, row["features"])
    before = tuple(render.scene.primitives)
    after = tuple(marked.scene.primitives)
    if (after[:len(before)] != before
            or any(item.layer != "MARKING" for item in after[len(before):])
            or not marked.material.equals(render.material)
            or marked.unfolded_topology != render.unfolded_topology):
        raise ValueError("SCOPED_MARK_CHANGED_PHYSICAL_SHEET")
    verify_manual_marking_output(marked)
    return marked


def verify_scoped_base_plate_dxf(render, target):
    """Independently reopen every MARKING entity, including physical DASH segments."""
    import ezdxf
    from .sheetmetal_drawing import CirclePrimitive, DrawingScene, LinePrimitive, PolylinePrimitive
    from .dxf_acceptance import verify_reopened_marking

    def coords(a, b):
        return tuple(sorted((tuple(round(float(v), 8) for v in a),
                             tuple(round(float(v), 8) for v in b))))

    expected = []
    circles = []
    for item in render.scene.primitives:
        if item.layer != "MARKING":
            continue
        if isinstance(item, CirclePrimitive) and is_manual_round_mark(item):
            circles.append(item)
        elif isinstance(item, LinePrimitive):
            expected.append(coords((item.p1.x, item.p1.y), (item.p2.x, item.p2.y)))
        elif isinstance(item, PolylinePrimitive) and not item.closed and len(item.points) == 2:
            a, b = item.points
            expected.append(coords((a.x, a.y), (b.x, b.y)))
        else:
            raise ValueError("SCOPED_MARK_DXF_UNSUPPORTED_PRIMITIVE")
    doc = ezdxf.readfile(target)
    if doc.layers.get("MARKING").dxf.linetype.upper() != "CONTINUOUS":
        raise ValueError("SCOPED_MARK_DXF_LINETYPE_CHANGED")
    actual = []
    round_count = 0
    for entity in doc.modelspace():
        if entity.dxf.layer.upper() != "MARKING":
            continue
        if entity.dxf.linetype.upper() not in {"BYLAYER", "CONTINUOUS"}:
            raise ValueError("SCOPED_MARK_DXF_LINETYPE_CHANGED")
        if entity.dxftype() == "CIRCLE":
            round_count += 1
        elif entity.dxftype() == "LINE":
            a, b = entity.dxf.start, entity.dxf.end
            actual.append(coords((a.x, a.y), (b.x, b.y)))
        elif entity.dxftype() == "LWPOLYLINE" and not entity.closed:
            points = entity.get_points("xyb")
            if len(points) != 2 or any(p[2] != 0 for p in points):
                raise ValueError("SCOPED_MARK_DXF_UNSUPPORTED_PRIMITIVE")
            actual.append(coords(points[0][:2], points[1][:2]))
        else:
            raise ValueError("SCOPED_MARK_DXF_UNSUPPORTED_PRIMITIVE")
    if round_count != len(circles) or (circles and verify_reopened_marking(DrawingScene(circles), doc, 1e-6)):
        raise ValueError("SCOPED_MARK_DXF_ROUND_CHANGED")
    if sorted(actual) != sorted(expected):
        raise ValueError("SCOPED_MARK_DXF_POINTS_CHANGED")
