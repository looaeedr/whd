# Box Body EndCap Collision Relief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Box Body <-> EndCap/Tail collision-driven relief solver while preserving `PartRenderData` as the only resolved manufacturing geometry output.

**Architecture:** Add a focused `ae_engine.assembly_collision` Module that works only inside the manufacturing boundary. It consumes resolved `PartRenderData` and fold profiles, computes simplified 2.5D collision footprints, applies `Box Body = RETAIN / EndCap-Tail = CUT`, returns an EndCap 2D relief polygon, then lets `manufacturing_api` rebuild final `PartRenderData`.

**Tech Stack:** Python dataclasses, Shapely `Polygon` / `box` / `unary_union`, existing `PartRenderData`, `FoldProfileSegment`, `DrawingScene`, `PolylinePrimitive`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-27-boxbody-endcap-collision-relief-design.md`

## Global Constraints

- 全部對話、日誌、文件與 CLI 檔案讀寫使用 UTF-8 與繁體中文。
- 修改任何既有檔案前先備份到 `BACKUP/[YYYYMMDD]-[HHMMSS]-[原始檔名]`。
- 修改完成後追加 `修改日誌/[YYYYMMDD].md`。
- 第一階段範圍只包含 `Box Body <-> EndCap / Tail`。
- Ownership 固定為 `Box Body = RETAIN`、`EndCap / Tail = CUT`。
- `phase6_final_scene_view.py` 只能消費 `PartRenderData`，不得變成 solver。
- GUI、Fold Designer Bridge、DXF exporter 不得重新解析 CornerType 或重建 CUTTING。
- 最終 2D、3D、DXF 仍必須消費同一份 `PartRenderData`。
- 第一版不引入完整 CAD kernel；使用 Shapely 與簡化 2.5D footprint。

---

## File Structure

- Create `ae_engine/assembly_collision.py`
  - Owns collision solver dataclasses, ownership policy, 2.5D footprint extraction, relief projection, verification helpers.
  - Must not import `tkinter`, `ezdxf`, `gui`, `fold_designer_bridge`, or `phase6_final_scene_view`.
- Modify `ae_engine/manufacturing_api.py`
  - Adds opt-in EndCap assembly relief entry point.
  - Keeps `build_part_render_data(spec, context)` default behavior unchanged until caller explicitly requests the solver.
- Modify `ae_engine/contracts.py`
  - Adds narrow optional request contract for EndCap assembly relief. Existing `PartSpec` constructors remain source-compatible.
- Test `tests/test_assembly_collision.py`
  - Tests the new Module in isolation.
- Test `tests/test_assembly_collision_integration.py`
  - Tests opt-in `manufacturing_api` flow and confirms Box Body retain / EndCap cut.
- Modify `tests/test_phase6_final_scene_view_ownership.py`
  - Adds a source-guard test that the renderer does not import or call `assembly_collision`.

---

### Task 1: Assembly Collision Contracts

**Files:**
- Create: `ae_engine/assembly_collision.py`
- Test: `tests/test_assembly_collision.py`

**Interfaces:**
- Consumes: Shapely geometry objects and existing `PartRenderData`-like objects with `.material`.
- Produces:
  - `AssemblyRole(value: "box_body" | "endcap")`
  - `OwnershipAction(value: "retain" | "cut")`
  - `AssemblyOwnershipPolicy(box_body: OwnershipAction, endcap: OwnershipAction)`
  - `CollisionRegion(region: object, source_role: AssemblyRole, target_role: AssemblyRole)`
  - `ReliefCandidate(cut_polygon_2d: object, clearance: float, source_collision_area: float)`
  - `default_boxbody_endcap_ownership() -> AssemblyOwnershipPolicy`
  - `detect_planar_collision(box_body_material, endcap_material) -> CollisionRegion | None`

- [ ] **Step 1: Write the failing contract tests**

Add `tests/test_assembly_collision.py`:

```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from shapely.geometry import box

from ae_engine.assembly_collision import (
    AssemblyRole,
    OwnershipAction,
    default_boxbody_endcap_ownership,
    detect_planar_collision,
)


def test_default_ownership_retains_box_body_and_cuts_endcap():
    policy = default_boxbody_endcap_ownership()

    assert policy.box_body is OwnershipAction.RETAIN
    assert policy.endcap is OwnershipAction.CUT


def test_detect_planar_collision_returns_overlap_region():
    collision = detect_planar_collision(
        box_body_material=box(0, 0, 100, 50),
        endcap_material=box(90, 10, 140, 40),
    )

    assert collision is not None
    assert collision.source_role is AssemblyRole.BOX_BODY
    assert collision.target_role is AssemblyRole.ENDCAP
    assert collision.region.area == pytest.approx(300.0)


def test_detect_planar_collision_returns_none_for_disjoint_parts():
    collision = detect_planar_collision(
        box_body_material=box(0, 0, 100, 50),
        endcap_material=box(120, 10, 140, 40),
    )

    assert collision is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_assembly_collision.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'ae_engine.assembly_collision'`.

- [ ] **Step 3: Implement the minimal contracts**

Create `ae_engine/assembly_collision.py`:

```python
# -*- coding: utf-8 -*-
"""Box Body / EndCap assembly collision relief solver.

This Module stays inside the manufacturing boundary. It consumes resolved
geometry and returns candidate 2D cuts; it does not know about GUI, DXF, or
renderer state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AssemblyRole(str, Enum):
    BOX_BODY = "box_body"
    ENDCAP = "endcap"


class OwnershipAction(str, Enum):
    RETAIN = "retain"
    CUT = "cut"


@dataclass(frozen=True)
class AssemblyOwnershipPolicy:
    box_body: OwnershipAction
    endcap: OwnershipAction


@dataclass(frozen=True)
class CollisionRegion:
    region: object
    source_role: AssemblyRole
    target_role: AssemblyRole


@dataclass(frozen=True)
class ReliefCandidate:
    cut_polygon_2d: object
    clearance: float
    source_collision_area: float


def default_boxbody_endcap_ownership() -> AssemblyOwnershipPolicy:
    return AssemblyOwnershipPolicy(
        box_body=OwnershipAction.RETAIN,
        endcap=OwnershipAction.CUT,
    )


def detect_planar_collision(*, box_body_material, endcap_material) -> CollisionRegion | None:
    overlap = box_body_material.intersection(endcap_material)
    if overlap.is_empty or float(overlap.area) <= 1e-9:
        return None
    return CollisionRegion(
        region=overlap,
        source_role=AssemblyRole.BOX_BODY,
        target_role=AssemblyRole.ENDCAP,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_assembly_collision.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ae_engine/assembly_collision.py tests/test_assembly_collision.py
git commit -m "feat: add assembly collision contracts"
```

---

### Task 2: Relief Candidate Projection

**Files:**
- Modify: `ae_engine/assembly_collision.py`
- Test: `tests/test_assembly_collision.py`

**Interfaces:**
- Consumes:
  - `CollisionRegion`
  - `AssemblyOwnershipPolicy`
- Produces:
  - `project_collision_to_endcap_relief(collision: CollisionRegion, policy: AssemblyOwnershipPolicy, clearance: float = 0.0, min_area: float = 1e-6) -> ReliefCandidate | None`

- [ ] **Step 1: Write the failing projection tests**

Append to `tests/test_assembly_collision.py`:

```python
from ae_engine.assembly_collision import (
    project_collision_to_endcap_relief,
)


def test_project_collision_to_endcap_relief_expands_by_clearance():
    collision = detect_planar_collision(
        box_body_material=box(0, 0, 100, 50),
        endcap_material=box(90, 10, 140, 40),
    )

    candidate = project_collision_to_endcap_relief(
        collision,
        default_boxbody_endcap_ownership(),
        clearance=2.0,
    )

    assert candidate is not None
    assert candidate.source_collision_area == pytest.approx(300.0)
    assert candidate.clearance == pytest.approx(2.0)
    assert candidate.cut_polygon_2d.bounds == pytest.approx((88.0, 8.0, 102.0, 42.0))


def test_project_collision_returns_none_when_endcap_is_not_cut_owner():
    collision = detect_planar_collision(
        box_body_material=box(0, 0, 100, 50),
        endcap_material=box(90, 10, 140, 40),
    )
    policy = default_boxbody_endcap_ownership()
    inverted = type(policy)(
        box_body=OwnershipAction.CUT,
        endcap=OwnershipAction.RETAIN,
    )

    candidate = project_collision_to_endcap_relief(collision, inverted)

    assert candidate is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_assembly_collision.py::test_project_collision_to_endcap_relief_expands_by_clearance tests/test_assembly_collision.py::test_project_collision_returns_none_when_endcap_is_not_cut_owner`

Expected: FAIL with import error for `project_collision_to_endcap_relief`.

- [ ] **Step 3: Implement projection**

Modify `ae_engine/assembly_collision.py`:

```python
def project_collision_to_endcap_relief(
    collision: CollisionRegion,
    policy: AssemblyOwnershipPolicy,
    *,
    clearance: float = 0.0,
    min_area: float = 1e-6,
) -> ReliefCandidate | None:
    if collision.target_role is not AssemblyRole.ENDCAP:
        return None
    if policy.endcap is not OwnershipAction.CUT:
        return None
    if policy.box_body is not OwnershipAction.RETAIN:
        return None

    region = collision.region
    if region.is_empty or float(region.area) <= float(min_area):
        return None

    clearance_value = max(0.0, float(clearance))
    cut = region.buffer(clearance_value, join_style=2) if clearance_value else region
    if cut.is_empty or float(cut.area) <= float(min_area):
        return None

    return ReliefCandidate(
        cut_polygon_2d=cut,
        clearance=clearance_value,
        source_collision_area=float(region.area),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_assembly_collision.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ae_engine/assembly_collision.py tests/test_assembly_collision.py
git commit -m "feat: project endcap collision relief"
```

---

### Task 3: Apply Relief To EndCap PartRenderData

**Files:**
- Modify: `ae_engine/assembly_collision.py`
- Test: `tests/test_assembly_collision.py`

**Interfaces:**
- Consumes:
  - `PartRenderData` with `.scene`, `.material`, `.fold_guides`
  - `ReliefCandidate`
- Produces:
  - `apply_endcap_relief_candidate(endcap_render_data, candidate: ReliefCandidate)`
  - Return object must have `.scene`, `.material`, `.fold_guides`, same shape as existing `PartRenderData`.

- [ ] **Step 1: Write the failing material-application test**

Append to `tests/test_assembly_collision.py`:

```python
from ae_engine.manufacturing_api import PartRenderData
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.assembly_collision import apply_endcap_relief_candidate


def _rect_scene(width, height):
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        points=(
            Vec2(0, 0),
            Vec2(width, 0),
            Vec2(width, height),
            Vec2(0, height),
        ),
        layer="CUTTING",
        closed=True,
    ))
    return scene


def test_apply_endcap_relief_candidate_reduces_material_and_preserves_fold_guides():
    scene = _rect_scene(100, 50)
    render = PartRenderData(
        scene=scene,
        material=box(0, 0, 100, 50),
        fold_guides=("fold-guide-sentinel",),
    )
    candidate = project_collision_to_endcap_relief(
        detect_planar_collision(
            box_body_material=box(90, 10, 120, 40),
            endcap_material=render.material,
        ),
        default_boxbody_endcap_ownership(),
        clearance=0.0,
    )

    solved = apply_endcap_relief_candidate(render, candidate)

    assert solved.material.area == pytest.approx(4100.0)
    assert solved.fold_guides == ("fold-guide-sentinel",)
    cutting = [
        primitive for primitive in solved.scene.primitives
        if isinstance(primitive, PolylinePrimitive)
        and primitive.layer == "CUTTING"
        and primitive.closed
    ]
    assert len(cutting) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_assembly_collision.py::test_apply_endcap_relief_candidate_reduces_material_and_preserves_fold_guides`

Expected: FAIL with import error for `apply_endcap_relief_candidate`.

- [ ] **Step 3: Implement material update and scene rebuild**

Modify `ae_engine/assembly_collision.py`:

```python
def _vec2_points_from_polygon_exterior(polygon):
    from .sheetmetal_geometry import Vec2

    coords = list(polygon.exterior.coords)
    if coords and coords[0] == coords[-1]:
        coords = coords[:-1]
    return tuple(Vec2(float(x), float(y)) for x, y in coords)


def _scene_with_replaced_primary_cutting(scene, material):
    from .sheetmetal_drawing import (
        DrawingScene,
        PolylinePrimitive,
    )

    out = DrawingScene()
    replaced = False
    for primitive in getattr(scene, "primitives", ()):
        if (
            not replaced
            and isinstance(primitive, PolylinePrimitive)
            and str(getattr(primitive, "layer", "")).upper() == "CUTTING"
            and bool(getattr(primitive, "closed", False))
        ):
            polygon = material
            if polygon.geom_type != "Polygon":
                polygon = max(polygon.geoms, key=lambda geom: float(geom.area))
            out.add(PolylinePrimitive(
                points=_vec2_points_from_polygon_exterior(polygon),
                layer=primitive.layer,
                closed=True,
                color=primitive.color,
            ))
            replaced = True
            continue
        out.add(primitive)
    if not replaced:
        raise ValueError("EndCap scene has no primary CUTTING outline to replace")
    return out


def apply_endcap_relief_candidate(endcap_render_data, candidate: ReliefCandidate):
    from .manufacturing_api import PartRenderData, material_polygon_from_final_scene

    if candidate is None:
        return endcap_render_data

    material = endcap_render_data.material.difference(candidate.cut_polygon_2d)
    if not material.is_valid:
        material = material.buffer(0)
    if material.is_empty or float(material.area) <= 1e-9:
        raise ValueError("EndCap relief removes all material")
    if material.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(f"EndCap relief produced unsupported material: {material.geom_type}")

    scene = _scene_with_replaced_primary_cutting(endcap_render_data.scene, material)
    resolved_material = material_polygon_from_final_scene(scene)
    return PartRenderData(
        scene=scene,
        material=resolved_material,
        fold_guides=endcap_render_data.fold_guides,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_assembly_collision.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ae_engine/assembly_collision.py tests/test_assembly_collision.py
git commit -m "feat: apply endcap collision relief"
```

---

### Task 4: End-To-End Solver And Verification

**Files:**
- Modify: `ae_engine/assembly_collision.py`
- Test: `tests/test_assembly_collision.py`

**Interfaces:**
- Consumes:
  - `box_body_render_data`
  - `endcap_render_data`
  - optional `AssemblyOwnershipPolicy`
- Produces:
  - `EndCapReliefSolution(original_collision: CollisionRegion | None, candidate: ReliefCandidate | None, solved_render_data: object, verified: bool)`
  - `solve_boxbody_endcap_relief(box_body_render_data, endcap_render_data, ownership: AssemblyOwnershipPolicy | None = None, clearance: float = 0.0) -> EndCapReliefSolution`

- [ ] **Step 1: Write the failing solver tests**

Append to `tests/test_assembly_collision.py`:

```python
from ae_engine.assembly_collision import solve_boxbody_endcap_relief


def test_solve_boxbody_endcap_relief_cuts_endcap_and_verifies_clear():
    endcap = PartRenderData(
        scene=_rect_scene(100, 50),
        material=box(0, 0, 100, 50),
        fold_guides=(),
    )
    box_body = PartRenderData(
        scene=_rect_scene(30, 30),
        material=box(90, 10, 120, 40),
        fold_guides=(),
    )

    solution = solve_boxbody_endcap_relief(
        box_body_render_data=box_body,
        endcap_render_data=endcap,
        clearance=0.0,
    )

    assert solution.original_collision is not None
    assert solution.candidate is not None
    assert solution.verified is True
    assert solution.solved_render_data.material.area == pytest.approx(4100.0)
    assert box_body.material.bounds == pytest.approx((90.0, 10.0, 120.0, 40.0))


def test_solve_boxbody_endcap_relief_returns_original_when_no_collision():
    endcap = PartRenderData(
        scene=_rect_scene(100, 50),
        material=box(0, 0, 100, 50),
        fold_guides=(),
    )
    box_body = PartRenderData(
        scene=_rect_scene(20, 20),
        material=box(120, 10, 140, 30),
        fold_guides=(),
    )

    solution = solve_boxbody_endcap_relief(
        box_body_render_data=box_body,
        endcap_render_data=endcap,
    )

    assert solution.original_collision is None
    assert solution.candidate is None
    assert solution.verified is True
    assert solution.solved_render_data is endcap
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_assembly_collision.py::test_solve_boxbody_endcap_relief_cuts_endcap_and_verifies_clear tests/test_assembly_collision.py::test_solve_boxbody_endcap_relief_returns_original_when_no_collision`

Expected: FAIL with import error for `solve_boxbody_endcap_relief`.

- [ ] **Step 3: Implement solver**

Modify `ae_engine/assembly_collision.py`:

```python
@dataclass(frozen=True)
class EndCapReliefSolution:
    original_collision: CollisionRegion | None
    candidate: ReliefCandidate | None
    solved_render_data: object
    verified: bool


def solve_boxbody_endcap_relief(
    *,
    box_body_render_data,
    endcap_render_data,
    ownership: AssemblyOwnershipPolicy | None = None,
    clearance: float = 0.0,
) -> EndCapReliefSolution:
    policy = ownership or default_boxbody_endcap_ownership()
    collision = detect_planar_collision(
        box_body_material=box_body_render_data.material,
        endcap_material=endcap_render_data.material,
    )
    if collision is None:
        return EndCapReliefSolution(
            original_collision=None,
            candidate=None,
            solved_render_data=endcap_render_data,
            verified=True,
        )

    candidate = project_collision_to_endcap_relief(
        collision,
        policy,
        clearance=clearance,
    )
    if candidate is None:
        return EndCapReliefSolution(
            original_collision=collision,
            candidate=None,
            solved_render_data=endcap_render_data,
            verified=False,
        )

    solved = apply_endcap_relief_candidate(endcap_render_data, candidate)
    remaining = detect_planar_collision(
        box_body_material=box_body_render_data.material,
        endcap_material=solved.material,
    )
    return EndCapReliefSolution(
        original_collision=collision,
        candidate=candidate,
        solved_render_data=solved,
        verified=remaining is None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_assembly_collision.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ae_engine/assembly_collision.py tests/test_assembly_collision.py
git commit -m "feat: solve boxbody endcap relief"
```

---

### Task 5: Manufacturing API Opt-In Integration

**Files:**
- Modify: `ae_engine/contracts.py`
- Modify: `ae_engine/manufacturing_api.py`
- Test: `tests/test_assembly_collision_integration.py`

**Interfaces:**
- Produces in `contracts.py`:
  - `EndCapAssemblyReliefRequest(box_body: BoxBodyPartSpec, clearance: float = 0.0, enabled: bool = True)`
  - Add field to `EndCapPartSpec`: `assembly_relief: EndCapAssemblyReliefRequest | None = None`
- Produces in `manufacturing_api.py`:
  - `build_part_render_data(spec, context)` applies solver only when `EndCapPartSpec.assembly_relief.enabled is True`.
  - On solver `verified is False`, raise `ValueError("EndCap assembly collision relief failed verification")`.

- [ ] **Step 1: Write the failing integration tests**

Add `tests/test_assembly_collision_integration.py`:

```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from shapely.geometry import box

from ae_engine import manufacturing_api
from ae_engine.contracts import (
    BoxBodyPartSpec,
    EndCapAssemblyReliefRequest,
    EndCapPartSpec,
    ManufacturingContext,
)
from ae_engine.manufacturing_api import PartRenderData
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
from ae_engine.sheetmetal_geometry import Vec2


def _scene(width, height):
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        points=(Vec2(0, 0), Vec2(width, 0), Vec2(width, height), Vec2(0, height)),
        layer="CUTTING",
        closed=True,
    ))
    return scene


def _render(width, height, material):
    return PartRenderData(scene=_scene(width, height), material=material, fold_guides=())


def test_endcap_assembly_relief_request_is_opt_in(monkeypatch):
    box_spec = BoxBodyPartSpec(width=500, height=600, depth=200, thickness=2, frame_width=25)
    endcap_spec = EndCapPartSpec(
        width=500,
        depth=200,
        thickness=2,
        frame_width=25,
        assembly_relief=EndCapAssemblyReliefRequest(box_body=box_spec, clearance=0.0),
    )

    calls = []

    def fake_scene(spec, context=None):
        return _scene(100, 50)

    def fake_material(scene):
        calls.append("material")
        return box(0, 0, 100, 50)

    def fake_box_render(spec, context=None):
        return _render(30, 30, box(90, 10, 120, 40))

    monkeypatch.setattr(manufacturing_api, "build_part_scene", fake_scene)
    monkeypatch.setattr(manufacturing_api, "material_polygon_from_final_scene", fake_material)
    monkeypatch.setattr(manufacturing_api, "fold_guides_from_final_scene", lambda scene: ())
    monkeypatch.setattr(manufacturing_api, "_build_box_body_render_for_endcap_relief", fake_box_render)

    render = manufacturing_api.build_part_render_data(
        endcap_spec,
        ManufacturingContext(draw_stock=False),
    )

    assert render.material.area == pytest.approx(4100.0)
    assert calls


def test_endcap_without_assembly_relief_keeps_existing_build_path(monkeypatch):
    endcap_spec = EndCapPartSpec(width=500, depth=200, thickness=2, frame_width=25)

    monkeypatch.setattr(manufacturing_api, "build_part_scene", lambda spec, context=None: _scene(100, 50))
    monkeypatch.setattr(manufacturing_api, "material_polygon_from_final_scene", lambda scene: box(0, 0, 100, 50))
    monkeypatch.setattr(manufacturing_api, "fold_guides_from_final_scene", lambda scene: ())

    render = manufacturing_api.build_part_render_data(
        endcap_spec,
        ManufacturingContext(draw_stock=False),
    )

    assert render.material.area == pytest.approx(5000.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_assembly_collision_integration.py`

Expected: FAIL with import error for `EndCapAssemblyReliefRequest`.

- [ ] **Step 3: Add the contract**

Modify `ae_engine/contracts.py`:

```python
@dataclass(frozen=True)
class EndCapAssemblyReliefRequest:
    box_body: BoxBodyPartSpec
    clearance: float = 0.0
    enabled: bool = True
```

Then add to `EndCapPartSpec`:

```python
    assembly_relief: EndCapAssemblyReliefRequest | None = None
```

Because `from __future__ import annotations` is already enabled, this forward reference is valid after `BoxBodyPartSpec` is defined.

- [ ] **Step 4: Integrate in `build_part_render_data()`**

Modify `ae_engine/manufacturing_api.py`:

```python
def _build_box_body_render_for_endcap_relief(
    spec: BoxBodyPartSpec,
    context: ManufacturingContext | None = None,
) -> PartRenderData:
    return build_part_render_data(spec, context)
```

Then replace `build_part_render_data()` with:

```python
def build_part_render_data(
    spec: PartSpec, context: ManufacturingContext | None = None
) -> PartRenderData:
    """Return final manufacturing material + scene for pure renderers."""
    scene = build_part_scene(spec, context)
    render_data = PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
    )
    if isinstance(spec, EndCapPartSpec):
        request = spec.assembly_relief
        if request is not None and bool(request.enabled):
            from .assembly_collision import solve_boxbody_endcap_relief

            box_render = _build_box_body_render_for_endcap_relief(request.box_body, context)
            solution = solve_boxbody_endcap_relief(
                box_body_render_data=box_render,
                endcap_render_data=render_data,
                clearance=float(request.clearance),
            )
            if not solution.verified:
                raise ValueError("EndCap assembly collision relief failed verification")
            render_data = solution.solved_render_data
    return render_data
```

- [ ] **Step 5: Run integration tests**

Run: `python -m pytest -q tests/test_assembly_collision.py tests/test_assembly_collision_integration.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ae_engine/contracts.py ae_engine/manufacturing_api.py tests/test_assembly_collision_integration.py
git commit -m "feat: integrate endcap assembly relief"
```

---

### Task 6: Renderer Ownership Guard

**Files:**
- Modify: `tests/test_phase6_final_scene_view_ownership.py`

**Interfaces:**
- Consumes: source text of `phase6_final_scene_view.py`.
- Produces: test guarantee that renderer stays a consumer.

- [ ] **Step 1: Add the source guard test**

Append to `tests/test_phase6_final_scene_view_ownership.py`:

```python
from pathlib import Path


def test_final_scene_view_does_not_call_assembly_collision_solver():
    source = Path("phase6_final_scene_view.py").read_text(encoding="utf-8")

    assert "assembly_collision" not in source
    assert "solve_boxbody_endcap_relief" not in source
    assert "detect_planar_collision" not in source
```

- [ ] **Step 2: Run guard test**

Run: `python -m pytest -q tests/test_phase6_final_scene_view_ownership.py::test_final_scene_view_does_not_call_assembly_collision_solver`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_phase6_final_scene_view_ownership.py
git commit -m "test: guard final scene renderer ownership"
```

---

### Task 7: Verification And Documentation

**Files:**
- Modify: `修改日誌/[YYYYMMDD].md`
- Optional Modify: `docs/superpowers/verification/[YYYY-MM-DD]-boxbody-endcap-collision-relief-verification.md`

**Interfaces:**
- Consumes: completed Tasks 1-6.
- Produces: verification evidence and project log.

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m pytest -q tests/test_assembly_collision.py tests/test_assembly_collision_integration.py tests/test_phase6_final_scene_view_ownership.py tests/test_endcap_resolved_geometry_ownership.py
```

Expected: PASS.

- [ ] **Step 2: Run py_compile**

Run:

```bash
python -m py_compile ae_engine/assembly_collision.py ae_engine/contracts.py ae_engine/manufacturing_api.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run broader regression slice**

Run:

```bash
python -m pytest -q tests/test_phase6_baseline_operation_alignment.py tests/test_phase6_linked_fold_chain_and_parts.py tests/test_corner_semantics.py tests/test_manufacturing_api.py
```

Expected: PASS.

- [ ] **Step 4: Record verification**

Create `docs/superpowers/verification/[YYYY-MM-DD]-boxbody-endcap-collision-relief-verification.md`:

```markdown
# Box Body / EndCap Collision Relief Verification

## Commands

- `python -m pytest -q tests/test_assembly_collision.py tests/test_assembly_collision_integration.py tests/test_phase6_final_scene_view_ownership.py tests/test_endcap_resolved_geometry_ownership.py`
- `python -m py_compile ae_engine/assembly_collision.py ae_engine/contracts.py ae_engine/manufacturing_api.py`
- `python -m pytest -q tests/test_phase6_baseline_operation_alignment.py tests/test_phase6_linked_fold_chain_and_parts.py tests/test_corner_semantics.py tests/test_manufacturing_api.py`

## Result

All listed commands passed on the implementation checkout.

## Scope

The solver is opt-in and limited to Box Body retaining material while EndCap/Tail receives collision-driven CUTTING relief.
```

- [ ] **Step 5: Append project modification log**

Append to `修改日誌/[YYYYMMDD].md` using the project template, listing production files, tests, backups, and verification result.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/verification 修改日誌 ae_engine tests
git commit -m "docs: verify boxbody endcap collision relief"
```

---

## Self-Review

**Spec coverage:** Covered Box Body <-> EndCap/Tail only, Box Body retain / EndCap cut, solver inside `ae_engine`, opt-in `manufacturing_api` integration, renderer ownership guard, verification failure behavior, and no GUI / renderer solver migration.

**Placeholder scan:** This plan contains no unresolved placeholder instructions or unspecified implementation steps. Each task defines concrete files, signatures, tests, commands, and expected results.

**Type consistency:** The produced names are consistent across tasks: `AssemblyOwnershipPolicy`, `CollisionRegion`, `ReliefCandidate`, `EndCapReliefSolution`, `solve_boxbody_endcap_relief`, `apply_endcap_relief_candidate`, and `EndCapAssemblyReliefRequest`.
