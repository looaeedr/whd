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
    editor and are intentionally independent of total segment count.  When
    ``formed_length`` is present it is the authoritative formed/outside
    occupation of this segment; ``length`` remains the flat/material span.
    """

    length: float
    angle: float | None = None
    core: str | None = None
    phase6_key: str | None = None
    # Optional formed/outside span for 3D folding. Flat material and DXF keep
    # consuming `length`; only the folded geometry map may consume this field.
    formed_length: float | None = None


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
    # Receiving rear-panel manufacturing contract resolved from family state + Door topology.
    # Empty keeps every other cabinet family and legacy multipart path unchanged.
    back_panel_contract: Mapping[str, object] = field(default_factory=dict)
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
class AssemblyGeometryToleranceContract:
    """Single geometry-neutral numerical contract for assembly mating geometry.

    These values are engineering numerical-robustness tolerances for the mm-scale
    assembly model.  They are not product clearances, DXF verifier tolerances,
    renderer tolerances, or pytest expectations.  The named production instance
    below is the only owner consumed by the Joint Placement MARKING contact path.
    """

    coplanar_distance_tolerance: float
    opposed_normal_residual_tolerance: float
    flat_world_mapping_tolerance: float
    boundary_separation_tolerance: float
    polygon_robustness_epsilon: float
    provenance: str = "ASSEMBLY_GEOMETRY_ENGINEERING_V1"
    revision: int = 1

    def __post_init__(self):
        for name in (
            "coplanar_distance_tolerance",
            "opposed_normal_residual_tolerance",
            "flat_world_mapping_tolerance",
            "boundary_separation_tolerance",
            "polygon_robustness_epsilon",
        ):
            value = float(getattr(self, name))
            if value <= 0.0:
                raise ValueError(f"{name} must be > 0")


# Canonical production owner for assembly mating/contact numerical robustness.
# Values are deliberately tiny relative to physical manufacturing dimensions and
# are owned here independently of validation/DXF reconstruction.
PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES = AssemblyGeometryToleranceContract(
    coplanar_distance_tolerance=1.0e-6,
    opposed_normal_residual_tolerance=1.0e-7,
    flat_world_mapping_tolerance=1.0e-7,
    boundary_separation_tolerance=1.0e-7,
    polygon_robustness_epsilon=1.0e-9,
)


@dataclass(frozen=True)
class TrueSolidPenetrationEvidence:
    """Authoritative upstream evidence that physical solids penetrate illegally."""

    detected: bool
    through_thickness: bool = False
    positive_volume: bool = False
    source: str = ""
    evidence: object | None = None


@dataclass(frozen=True)
class ResolvedLegalContact:
    """One legal, policy-selected physical mating contact."""

    locator_part_id: str
    attached_part_id: str
    locator_region: object
    attached_region: object
    contact_plane: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    locator_outward_normal: tuple[float, float, float]
    attached_outward_normal: tuple[float, float, float]
    overlap_world: tuple[tuple[float, float, float], ...]
    locator_flat_mapping: object | None
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LegalContactResult:
    """Fail-closed legal-contact classification result."""

    status: str
    diagnostic_code: str | None = None
    contact: ResolvedLegalContact | None = None
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ContactLocalFrame:
    """Semantic contact-local frame derived from one signed canonical flat basis."""

    frame_version: str
    origin: tuple[float, float, float]
    normal: tuple[float, float, float]
    longitudinal: tuple[float, float, float]
    cross: tuple[float, float, float]
    handedness_parity: int
    basis_part: str
    longitudinal_flat_axis: str
    cross_flat_axis: str


@dataclass(frozen=True)
class ContactLocalFrameResult:
    status: str
    diagnostic_code: str | None = None
    frame: ContactLocalFrame | None = None
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticBoundary:
    role: str
    world_segment: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    signed_cross: float


@dataclass(frozen=True)
class SemanticBoundaryPair:
    negative: SemanticBoundary
    positive: SemanticBoundary


@dataclass(frozen=True)
class SemanticBoundaryPairResult:
    status: str
    diagnostic_code: str | None = None
    pair: SemanticBoundaryPair | None = None
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LocatorBackprojectionResult:
    status: str
    diagnostic_code: str | None = None
    flat_points: tuple[tuple[float, float], ...] = ()
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedPhysicalMatingRegion:
    """Geometry-neutral resolved physical face used by assembly mating logic.

    The physical-part owner supplies the semantic region identity; this contract
    carries only the resolved world-space face and its provenance.  Boundary-wall
    regions such as an Inner Door Frame terminal face are allowed to have no flat
    mapping.  Locator policies may require a mapping in later marking stages.
    """

    part_id: str
    region_id: str
    region_role: str
    physical_face_kind: str
    supporting_plane: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    outward_normal: tuple[float, float, float]
    world_polygon: tuple[tuple[float, float, float], ...]
    flat_mapping: object | None = None
    provenance: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class JointMarkingPolicy:
    """Immutable semantic policy for dormant Joint Placement MARKING foundation."""

    policy_id: str
    revision: int
    enabled: bool
    locator_selector: str
    attached_selector: str
    locator_contact_region: str
    attached_contact_region: str
    footprint_mode: str
    boundary_frame_contract: Mapping[str, object]
    contact_span_contract: str
    allowed_overlap_contract: str

    def __post_init__(self):
        for name in (
            "policy_id",
            "locator_selector",
            "attached_selector",
            "locator_contact_region",
            "attached_contact_region",
            "footprint_mode",
            "contact_span_contract",
            "allowed_overlap_contract",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} must be nonblank")
        if isinstance(self.revision, bool) or int(self.revision) <= 0:
            raise ValueError("revision must be a positive integer")
        if not isinstance(self.boundary_frame_contract, Mapping):
            raise TypeError("boundary_frame_contract must be a mapping")


@dataclass(frozen=True)
class JointMarkingPolicyLookupResult:
    """Registry routing result; ordinary no-policy is intentionally non-diagnostic."""

    status: str
    policy: JointMarkingPolicy | None = None
    diagnostic_code: str | None = None
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ContactSpanValidationResult:
    """Policy-level contact-span/coverage validation result."""

    status: str
    diagnostic_code: str | None = None
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class JointMarkingFailurePolicy:
    """Product-owned export disposition for expected marking failures."""

    disposition: str

    def __post_init__(self):
        value = str(self.disposition or "").strip().upper()
        if value not in {"BLOCK_EXPORT", "ALLOW_EXPORT_WITH_DIAGNOSTIC"}:
            raise ValueError(f"unsupported JointMarkingFailurePolicy disposition: {value!r}")
        object.__setattr__(self, "disposition", value)


@dataclass(frozen=True)
class JointMarkingProductionStatus:
    """Production activation state for Joint Placement MARKING."""

    gate_state: str
    activation_enabled: bool
    export_disposition: str
    production_policy_count: int

    def __post_init__(self):
        state = str(self.gate_state or "").strip()
        disposition = str(self.export_disposition or "").strip().upper()
        count = int(self.production_policy_count)
        if not state:
            raise ValueError("gate_state must be nonblank")
        if disposition not in {"BLOCK_EXPORT", "ALLOW_EXPORT_WITH_DIAGNOSTIC", "UNRESOLVED"}:
            raise ValueError(f"unsupported export disposition: {disposition!r}")
        if count < 0:
            raise ValueError("production_policy_count must be >= 0")
        object.__setattr__(self, "gate_state", state)
        object.__setattr__(self, "activation_enabled", bool(self.activation_enabled))
        object.__setattr__(self, "export_disposition", disposition)
        object.__setattr__(self, "production_policy_count", count)


@dataclass(frozen=True)
class ResolvedJointMarkingResult:
    """Dedicated dormant Joint Placement MARKING result/diagnostic DTO."""

    policy_id: str
    policy_revision: int
    locator_part_id: str
    attached_part_id: str
    status: str
    mark_ids: tuple[str, ...] = ()
    diagnostic_code: str | None = None
    diagnostic_detail: str = ""
    export_disposition: str = "UNRESOLVED"
    evidence: Mapping[str, object] = field(default_factory=dict)



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
