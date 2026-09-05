# -*- coding: utf-8 -*-
"""Stable, GUI-independent request/result contracts for AE manufacturing.

Public ``features`` coordinates are finished-face 1:1 mm coordinates.  The
``legacy_unfolded`` Door feature space exists only as a migration compatibility
path for the current GUI adapter; automatic/CLI callers should use the default
``finished_face`` contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping, Sequence, TypeAlias

from .sheetmetal_features import Feature
from .sheetmetal_part_adapters import DoorFrameEdges
from .sheetmetal_geometry import FourCornerTypePolicy

FeatureLike: TypeAlias = Feature | Mapping[str, object]
DoorFeatureSpace: TypeAlias = Literal["finished_face", "legacy_unfolded"]


@dataclass(frozen=True)
class FoldProfileSegment:
    """One authoritative editable flat-strip segment.

    ``angle`` is the fold after this segment; the final segment therefore owns
    ``None``.  ``core`` / ``phase6_key`` are semantic anchors carried from the
    editor and are intentionally independent of total segment count.
    """

    length: float
    angle: float | None = None
    core: str | None = None
    phase6_key: str | None = None


@dataclass(frozen=True)
class ManufacturingPolicy:
    """Factory-policy defaults exposed through the stable headless boundary."""

    default_thickness: float
    frame_width: float
    door_gap_w: float
    door_gap_h: float
    door_fold_left: float
    door_fold_right: float
    door_fold_top: float
    door_fold_bottom: float
    indicator_box_fold: float
    indicator_small_door_fold: float = 19.0
    indicator_small_door_gap: float = 3.5


@dataclass(frozen=True)
class ManufacturingContext:
    """Execution context owned by the caller, not by the geometry engine.

    ``resource_root`` is the directory that contains ``基準檔/``.  When omitted,
    the wrapped AE module keeps using its own resource lookup policy.
    """

    resource_root: str | Path | None = None
    overwrite: bool = True
    draw_stock: bool = False
    policy: ManufacturingPolicy | None = None


@dataclass(frozen=True)
class DoorPartSpec:
    width: float
    height: float
    thickness: float
    frame_width: float
    model_name: str | None = None
    gap_w: float | None = None
    gap_h: float | None = None
    fold_left: float | None = None
    fold_right: float | None = None
    fold_top: float | None = None
    fold_bottom: float | None = None
    frame_edges: DoorFrameEdges = field(default_factory=DoorFrameEdges)
    features: tuple[FeatureLike, ...] = ()
    feature_space: DoorFeatureSpace = "finished_face"
    indicator_hole: tuple[float, float] | None = None
    door_indicator: tuple[int, ...] | None = None
    door_indicator_offset: tuple[float, float] = (0.0, 0.0)
    use_box_distance: bool = False
    corner_policy: FourCornerTypePolicy | None = None
    # Shared indicator small-door window ownership.  Keep the original design
    # groups instead of reverse-inferring them from the generated W/H.
    indicator_window_groups: tuple[int, ...] | None = None
    # Optional canonical distance from the finished Door top edge to the
    # baseline nameplate-hole pair centerline. Family code may override this
    # parameter without changing Door local origin/axis semantics.
    nameplate_center_datum_top: float | None = None


@dataclass(frozen=True)
class BoxBodyPartSpec:
    width: float
    height: float
    depth: float
    thickness: float
    frame_width: float
    model_name: str | None = None
    zl1: float | None = None
    zl2: float | None = None
    zr1: float | None = None
    zr2: float | None = None
    z_comp: float | None = None
    fold_profile: tuple[FoldProfileSegment, ...] = ()
    features: tuple[FeatureLike, ...] = ()
    face_features: Mapping[str, Sequence[FeatureLike]] = field(default_factory=dict)
    head_corner_policy: FourCornerTypePolicy | None = None
    tail_corner_policy: FourCornerTypePolicy | None = None
    # Phase6 multi-piece box-body structure state. Empty keeps the legacy integral path.
    structure_state: Mapping[str, object] = field(default_factory=dict)
    # Actual EndCap/Tail lower flange values drive multi-piece end relief.
    head_ybottom1: float = 15.0
    tail_ybottom1: float = 15.0


@dataclass(frozen=True)
class EndCapAssemblyReliefRequest:
    box_body: BoxBodyPartSpec
    clearance: float = 0.0
    enabled: bool = True


@dataclass(frozen=True)
class EndCapPartSpec:
    width: float
    depth: float
    thickness: float
    frame_width: float
    height: float | None = None
    model_name: str | None = None
    is_tail: bool = False
    fold_left: float | None = None
    fold_right: float | None = None
    fold_top: float | None = None
    fold_bottom: float | None = None
    box_fold_left: float | None = None
    box_fold_right: float | None = None
    # Formed Box Body FW outside occupation used by EndCap assembly relief.
    box_body_formed_fw_left: float | None = None
    box_body_formed_fw_right: float | None = None
    # Actual Box Body structure geometry used by family-specific AssemblyJoint
    # registry rules (e.g. receiving side/back split WRAP).
    box_body_structure_state: Mapping[str, object] = field(default_factory=dict)
    # Resolved global AssemblyJoint rows relevant to this EndCap.  Relation
    # semantics are owned by ae_engine.assembly_joint; family state must not
    # override these rows at manufacturing time.
    assembly_joints: tuple[Mapping[str, object], ...] = ()
    fold_profile_x: tuple[FoldProfileSegment, ...] = ()
    fold_profile_y: tuple[FoldProfileSegment, ...] = ()
    holes: tuple[FeatureLike, ...] = ()
    corner_policy: FourCornerTypePolicy | None = None
    # Family-specific D material compensation. Vault legacy = 3T; receiving = 2T.
    depth_comp_t: float = 3.0
    # Final 2D cut polygons produced by the verified 3D assembly solver.
    # Empty means use the intrinsic CornerType/factory relief. Coordinates are
    # authoritative unfolded material coordinates and are serialization-safe.
    resolved_assembly_relief_cuts: tuple[tuple[tuple[float, float], ...], ...] = ()
    assembly_relief: EndCapAssemblyReliefRequest | None = None


@dataclass(frozen=True)
class BasePlatePartSpec:
    width: float
    height: float
    thickness: float
    shrink_top: float
    shrink_bottom: float
    shrink_left: float
    shrink_right: float
    bend: float
    features: tuple[FeatureLike, ...] = ()
    corner_policy: FourCornerTypePolicy | None = None
    # Box-body structure is optional; when present, Base Plate cross relief is
    # derived from actual W seam intersections instead of structure-name rules.
    box_body_structure_state: Mapping[str, object] = field(default_factory=dict)
    box_body_fold_profile: tuple[FoldProfileSegment, ...] = ()
    model_name: str | None = None
    seam_positions: tuple[float, ...] = ()


@dataclass(frozen=True)
class IndicatorBoxPartSpec:
    layer_groups: tuple[int, ...]
    thickness: float
    features: tuple[FeatureLike, ...] = ()
    corner_policy: FourCornerTypePolicy | None = None
    model_name: str | None = None


PartSpec: TypeAlias = DoorPartSpec | BoxBodyPartSpec | EndCapPartSpec | BasePlatePartSpec | IndicatorBoxPartSpec


@dataclass(frozen=True)
class PartExportResult:
    part_kind: str
    output_path: str
    exporter_name: str
    used_baseline: bool
    baseline_path: str | None = None
    expected_baseline_path: str | None = None


@dataclass(frozen=True)
class FinalMaterialCollisionPart:
    """GUI-independent neutral final-material contract for collision solving.

    It carries committed physical geometry and diagnostics only; no GUI callback,
    exporter, or manufacturing orchestration handle is allowed here.
    """

    part_id: str
    material: object
    scene: object | None = None
    fold_guides: tuple[object, ...] = ()
    unfolded_topology: object | None = None
    true_thickness: float = 0.0
    piece_transform: object | None = None
    resolved_joints: tuple[object, ...] = ()
    legal_contact_semantics: tuple[object, ...] = ()
    solver_constraints: tuple[object, ...] = ()
    diagnostic_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedManufacturingPart:
    """One canonical, already-resolved physical part consumed by all downstream views."""

    part_key: str
    render_data: object
    x_profile: tuple[Mapping[str, object], ...] = ()
    y_profile: tuple[Mapping[str, object], ...] = ()
    placement: str = "offset"
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class ResolvedReliefRuleTrace:
    """Auditable rule ownership for one canonical corner relief."""

    part_key: str
    corner_name: str
    rule_id: str | None = None
    revision: int | None = None
    trust_level: str = ""
    signature: str = ""
    geometry_inputs: tuple[str, ...] = ()
    geometry_evidence: object | None = None




@dataclass(frozen=True)
class ResolvedJointDiagnostic:
    """Auditable Joint-local solver/shadow diagnostic carried with canonical geometry."""

    joint_id: str
    subject_part: str
    target_part: str
    relation: str
    source: str = ""
    registry_status: str = ""
    rule_id: str | None = None
    revision: int | None = None
    trust_level: str = ""
    preserve_part: str = ""
    relief_part: str = ""
    candidate_status: str = ""
    legal_contact: bool = False
    illegal_penetration: bool = False
    pre_pair_count: int = 0
    post_pair_count: int = 0
    contact_segments: tuple[object, ...] = ()
    penetration_segments: tuple[object, ...] = ()
    preserve_segments: tuple[object, ...] = ()
    relief_segments: tuple[object, ...] = ()
    direction_segment: object | None = None
    evidence: object | None = None


@dataclass(frozen=True)
class ResolvedManufacturingGeometry:
    """Single canonical manufacturing result shared by 2D/3D/export/save.

    This contract intentionally contains resolved geometry, not a solver handle.
    Consumers are readers: assembly relief may be discovered before construction
    of this object, but downstream code must not independently solve it again.
    """

    parts: tuple[ResolvedManufacturingPart, ...]
    joints: tuple[object, ...] = ()
    relief_rules: tuple[ResolvedReliefRuleTrace, ...] = ()
    diagnostics: tuple[object, ...] = ()

    def __post_init__(self):
        seen: set[str] = set()
        for part in tuple(self.parts or ()):
            key = str(part.part_key)
            if key in seen:
                raise ValueError(f"duplicate canonical part: {key}")
            seen.add(key)

    def part(self, part_key: str) -> ResolvedManufacturingPart:
        key = str(part_key)
        for part in tuple(self.parts or ()):
            if str(part.part_key) == key:
                return part
        raise KeyError(key)

    def material(self, part_key: str):
        return getattr(self.part(part_key).render_data, "material", None)

    def relief_rules_for(self, part_key: str) -> tuple[ResolvedReliefRuleTrace, ...]:
        key = str(part_key)
        return tuple(item for item in tuple(self.relief_rules or ()) if str(item.part_key) == key)

    def joints_for(self, part_key: str) -> tuple[object, ...]:
        key = str(part_key)
        return tuple(
            joint for joint in tuple(self.joints or ())
            if str(getattr(joint, "subject_part", "")) == key or str(getattr(joint, "target_part", "")) == key
        )

    def joint_diagnostic(self, joint_id: str) -> ResolvedJointDiagnostic:
        key = str(joint_id)
        for item in tuple(self.diagnostics or ()):
            if str(getattr(item, "joint_id", "")) == key:
                return item
        raise KeyError(key)

    def joint_diagnostics_for(self, part_key: str) -> tuple[ResolvedJointDiagnostic, ...]:
        key = str(part_key)
        return tuple(
            item for item in tuple(self.diagnostics or ())
            if str(getattr(item, "subject_part", "")) == key or str(getattr(item, "target_part", "")) == key
        )
