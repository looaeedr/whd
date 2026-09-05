# 2D Sheet-Metal Geometry Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the end-cap/tail hard-coded CUTTING perimeter with a reusable pure-Python 2D sheet-metal geometry engine that derives relief polygons from bend/flange topology and manufacturing rules.

**Architecture:** Add a focused `sheetmetal_geometry.py` module containing 2D primitives, bend/flange/corner topology, relief configuration, and outline construction. `ae.py` continues to own DXF I/O and flat-size calculations, but delegates CUTTING geometry to the new engine. The first production rule is the confirmed end-cap/tail insertion rule; legacy 16-point output is not a correctness target.

**Tech Stack:** Python 3, dataclasses, math; Shapely when available for polygon boolean operations; ezdxf remains only in `ae.py` for DXF I/O; pytest for tests.

## Global Constraints

- No FreeCAD/OpenCascade runtime dependency.
- Do not hard-code panel-type-specific perimeter point sequences in the new engine.
- `zl1/zr1` must not affect the end-cap top primary relief.
- Top primary relief: X = `abs(left/right fold) + FW`, Y = `ytop1 + FW - T`.
- Top secondary relief: X = `abs(left/right fold) + extra`, default extra `0.5T`; height default `2T`.
- Bottom relief: X = `abs(left/right fold) + extra`, Y = `ybottom1 + extra`, default extra `0.5T`.
- Shared relief defaults must allow independent left/right overrides.
- Existing BEND, holes, CHECK, STOCK and unrelated exporters must remain behaviorally unchanged except where coordinates intentionally follow corrected CUTTING geometry.
- Tests for the pure geometry core must not require ezdxf.
- The previous parity-only implementation and its legacy 16-point coordinates are not a correctness target.

---

## File Structure

- Create `sheetmetal_geometry.py`: pure geometry/topology/relief engine with no ezdxf import.
- Create `test_sheetmetal_geometry.py`: pure pytest coverage for primitives, relief dimensions, and generated outline.
- Modify `ae.py`: configuration migration and end-cap CUTTING integration only.
- Modify `test_endcap_corner_relief.py`: replace legacy-parity assertions with exporter integration checks that can run when ezdxf is installed.
- Add `docs/superpowers/specs/2026-08-10-sheetmetal-geometry-engine-design.md`.
- Add `docs/superpowers/plans/2026-08-10-sheetmetal-geometry-engine.md`.

---

### Task 1: Pure geometry primitives and topology objects

**Files:**
- Create: `sheetmetal_geometry.py`
- Create: `test_sheetmetal_geometry.py`

**Interfaces:**
- Produces: `GeometryError`, `Vec2`, `BendLine`, `Flange`, `Corner`, `line_intersection()`.
- `line_intersection(a: BendLine, b: BendLine, tol: float = 1e-9) -> Vec2`.

- [ ] **Step 1: Write failing primitive tests**

```python
import math
import pytest

from sheetmetal_geometry import BendLine, GeometryError, Vec2, line_intersection


def test_line_intersection_uses_infinite_lines():
    a = BendLine("vertical", Vec2(15, 30), Vec2(15, 40))
    b = BendLine("horizontal", Vec2(0, 20), Vec2(10, 20))
    assert line_intersection(a, b) == Vec2(15, 20)


def test_line_intersection_rejects_parallel_lines():
    a = BendLine("a", Vec2(0, 0), Vec2(10, 0))
    b = BendLine("b", Vec2(0, 5), Vec2(10, 5))
    with pytest.raises(GeometryError, match="parallel"):
        line_intersection(a, b)


def test_vec2_local_arithmetic():
    v = Vec2(3, 4)
    assert math.isclose(v.length(), 5.0)
    assert v + Vec2(1, 2) == Vec2(4, 6)
```

- [ ] **Step 2: Run the primitive tests and verify they fail**

Run:
```bash
python -m pytest test_sheetmetal_geometry.py -k "line_intersection or vec2" -v
```

Expected: FAIL because `sheetmetal_geometry` does not exist.

- [ ] **Step 3: Implement minimal immutable primitives**

```python
from dataclasses import dataclass, field
import math


class GeometryError(ValueError):
    pass


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float

    def __add__(self, other):
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Vec2(self.x * scalar, self.y * scalar)

    def length(self):
        return math.hypot(self.x, self.y)


@dataclass(frozen=True)
class BendLine:
    name: str
    p1: Vec2
    p2: Vec2


@dataclass
class Flange:
    name: str
    bend: BendLine
    length: float
    parent: "Flange | None" = None
    child_bends: list[BendLine] = field(default_factory=list)
    role: str | None = None


@dataclass(frozen=True)
class Corner:
    name: str
    point: Vec2
    u: Vec2
    v: Vec2
    bends: tuple[BendLine, BendLine]


def line_intersection(a: BendLine, b: BendLine, tol: float = 1e-9) -> Vec2:
    p = a.p1
    r = a.p2 - a.p1
    q = b.p1
    s = b.p2 - b.p1
    cross = r.x * s.y - r.y * s.x
    if abs(cross) <= tol:
        raise GeometryError("bend lines are parallel or degenerate")
    qp = q - p
    t = (qp.x * s.y - qp.y * s.x) / cross
    return Vec2(p.x + t * r.x, p.y + t * r.y)
```

- [ ] **Step 4: Run primitive tests**

Run:
```bash
python -m pytest test_sheetmetal_geometry.py -k "line_intersection or vec2" -v
```

Expected: PASS.

---

### Task 2: Relief configuration and confirmed end-cap relief dimensions

**Files:**
- Modify: `sheetmetal_geometry.py`
- Modify: `test_sheetmetal_geometry.py`

**Interfaces:**
- Produces: `ReliefConfig`, `EndCapGeometry`, `EndCapReliefDimensions`, `calculate_endcap_relief_dimensions()`.
- `calculate_endcap_relief_dimensions(g: EndCapGeometry, cfg: ReliefConfig) -> EndCapReliefDimensions`.

- [ ] **Step 1: Add failing formula tests**

```python
from sheetmetal_geometry import (
    EndCapGeometry,
    ReliefConfig,
    calculate_endcap_relief_dimensions,
)


def test_confirmed_endcap_relief_dimensions_t2():
    g = EndCapGeometry(
        total_width=422.0,
        total_depth=300.0,
        thickness=2.0,
        fw=25.0,
        left_fold=15.0,
        right_fold=15.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    d = calculate_endcap_relief_dimensions(g, ReliefConfig())
    assert d.top_primary_left == 40.0
    assert d.top_primary_right == 40.0
    assert d.top_primary_height == 39.0
    assert d.top_secondary_left == 16.0
    assert d.top_secondary_right == 16.0
    assert d.top_secondary_depth_left == 4.0
    assert d.top_secondary_depth_right == 4.0
    assert d.bottom_left == 16.0
    assert d.bottom_right == 16.0
    assert d.bottom_height == 16.0


def test_clearances_scale_with_t15():
    g = EndCapGeometry(
        total_width=424.0,
        total_depth=300.0,
        thickness=1.5,
        fw=25.0,
        left_fold=15.0,
        right_fold=20.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    d = calculate_endcap_relief_dimensions(g, ReliefConfig())
    assert d.top_secondary_left == 15.75
    assert d.top_secondary_right == 20.75
    assert d.top_secondary_depth_left == 3.0
    assert d.bottom_left == 15.75
    assert d.bottom_right == 20.75
    assert d.bottom_height == 15.75


def test_side_overrides_are_independent():
    cfg = ReliefConfig(
        top_secondary_x_factor=0.5,
        top_secondary_depth_factor=2.0,
        bottom_x_factor=0.5,
        bottom_y_factor=0.5,
        top_secondary_x_left=0.8,
        top_secondary_x_right=1.2,
        top_secondary_depth_left=3.0,
        top_secondary_depth_right=5.0,
        bottom_x_left=0.4,
        bottom_x_right=1.4,
    )
    g = EndCapGeometry(
        total_width=422.0,
        total_depth=300.0,
        thickness=2.0,
        fw=25.0,
        left_fold=15.0,
        right_fold=18.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    d = calculate_endcap_relief_dimensions(g, cfg)
    assert d.top_secondary_left == 15.8
    assert d.top_secondary_right == 19.2
    assert d.top_secondary_depth_left == 3.0
    assert d.top_secondary_depth_right == 5.0
    assert d.bottom_left == 15.4
    assert d.bottom_right == 19.4
```

- [ ] **Step 2: Run formula tests and verify failure**

Run:
```bash
python -m pytest test_sheetmetal_geometry.py -k "relief_dimensions or clearances or overrides" -v
```

Expected: FAIL because the new data classes/functions are absent.

- [ ] **Step 3: Implement the relief data model and formula function**

Use absolute millimeter overrides when provided; otherwise multiply common factor by thickness.

```python
@dataclass(frozen=True)
class ReliefConfig:
    top_secondary_x_factor: float = 0.5
    top_secondary_depth_factor: float = 2.0
    bottom_x_factor: float = 0.5
    bottom_y_factor: float = 0.5
    top_secondary_x_left: float | None = None
    top_secondary_x_right: float | None = None
    top_secondary_depth_left: float | None = None
    top_secondary_depth_right: float | None = None
    bottom_x_left: float | None = None
    bottom_x_right: float | None = None


@dataclass(frozen=True)
class EndCapGeometry:
    total_width: float
    total_depth: float
    thickness: float
    fw: float
    left_fold: float
    right_fold: float
    top_first_fold: float
    bottom_fold: float


@dataclass(frozen=True)
class EndCapReliefDimensions:
    top_primary_left: float
    top_primary_right: float
    top_primary_height: float
    top_secondary_left: float
    top_secondary_right: float
    top_secondary_depth_left: float
    top_secondary_depth_right: float
    bottom_left: float
    bottom_right: float
    bottom_height: float
```

Validate `T > 0`, non-negative normalized fold lengths, and positive blank dimensions before calculating.

- [ ] **Step 4: Run formula tests**

Run:
```bash
python -m pytest test_sheetmetal_geometry.py -k "relief_dimensions or clearances or overrides" -v
```

Expected: PASS.

---

### Task 3: Build topology from bend lines and resolve theoretical corners

**Files:**
- Modify: `sheetmetal_geometry.py`
- Modify: `test_sheetmetal_geometry.py`

**Interfaces:**
- Produces: `EndCapTopology`, `build_endcap_topology(g: EndCapGeometry) -> EndCapTopology`.

- [ ] **Step 1: Add failing topology tests**

```python
def test_endcap_topology_resolves_bend_intersections():
    g = EndCapGeometry(
        total_width=422.0,
        total_depth=300.0,
        thickness=2.0,
        fw=25.0,
        left_fold=15.0,
        right_fold=15.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    topo = build_endcap_topology(g)
    assert topo.bottom_left.point == Vec2(15.0, 15.0)
    assert topo.bottom_right.point == Vec2(407.0, 15.0)
    assert topo.top_chain_left_1.point.x == 15.0
    assert topo.top_chain_left_2.point.x == 15.0
    assert topo.top_chain_right_1.point.x == 407.0
    assert topo.top_chain_right_2.point.x == 407.0
```

- [ ] **Step 2: Run and verify failure**

Run:
```bash
python -m pytest test_sheetmetal_geometry.py -k topology -v
```

Expected: FAIL because topology builder is absent.

- [ ] **Step 3: Implement bend/topology construction**

Use:
- left bend X = `abs(left_fold)`
- right bend X = `total_width - abs(right_fold)`
- bottom bend Y = `bottom_fold`
- top-chain first bend Y = `bottom_fold + (finished_depth - 3T)` where the caller supplies flat total depth; derive this equivalent from `total_depth - top_first_fold - fw`
- top-chain second bend Y = `total_depth - top_first_fold`

Resolve every corner via `line_intersection()` rather than direct coordinate assignment.

- [ ] **Step 4: Run topology tests**

Run:
```bash
python -m pytest test_sheetmetal_geometry.py -k topology -v
```

Expected: PASS.

---

### Task 4: Generate relief polygons and final outline without a hard-coded perimeter

**Files:**
- Modify: `sheetmetal_geometry.py`
- Modify: `test_sheetmetal_geometry.py`

**Interfaces:**
- Produces: `ReliefPolygon`, `build_endcap_reliefs()`, `build_endcap_outline()`.
- `build_endcap_outline(g: EndCapGeometry, cfg: ReliefConfig = ReliefConfig()) -> list[Vec2]`.

- [ ] **Step 1: Add failing outline tests**

```python
def test_endcap_outline_matches_confirmed_step_geometry():
    g = EndCapGeometry(
        total_width=422.0,
        total_depth=300.0,
        thickness=2.0,
        fw=25.0,
        left_fold=15.0,
        right_fold=15.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    pts = build_endcap_outline(g)
    assert pts[0] == pts[-1]

    coords = {(round(p.x, 6), round(p.y, 6)) for p in pts}
    # bottom relief = 15 + 1 = 16
    assert (16.0, 0.0) in coords
    assert (0.0, 16.0) in coords
    # primary top relief = 15 + 25 = 40, height = 16 + 25 - 2 = 39
    assert (40.0, 300.0) in coords
    assert (40.0, 261.0) in coords
    # secondary width = 15 + 1 = 16, depth = 4
    assert (16.0, 261.0) in coords
    assert (16.0, 257.0) in coords


def test_top_primary_does_not_depend_on_z_fold_values():
    g = EndCapGeometry(
        total_width=422.0,
        total_depth=300.0,
        thickness=2.0,
        fw=25.0,
        left_fold=14.0,
        right_fold=19.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    d = calculate_endcap_relief_dimensions(g, ReliefConfig())
    assert d.top_primary_left == 39.0
    assert d.top_primary_right == 44.0


def test_outline_supports_asymmetric_overrides():
    g = EndCapGeometry(
        total_width=430.0,
        total_depth=310.0,
        thickness=2.0,
        fw=25.0,
        left_fold=14.0,
        right_fold=19.0,
        top_first_fold=18.0,
        bottom_fold=17.0,
    )
    cfg = ReliefConfig(
        top_secondary_x_left=1.5,
        top_secondary_x_right=0.5,
        top_secondary_depth_left=3.0,
        top_secondary_depth_right=5.0,
        bottom_x_left=0.25,
        bottom_x_right=1.25,
    )
    pts = build_endcap_outline(g, cfg)
    assert pts[0] == pts[-1]
    assert len(pts) >= 16
```

- [ ] **Step 2: Run and verify failure**

Run:
```bash
python -m pytest test_sheetmetal_geometry.py -k "outline or primary" -v
```

Expected: FAIL because polygon generation is absent.

- [ ] **Step 3: Implement relief rectangles plus boolean subtraction**

Preferred implementation:
- Build the unnotched blank rectangle.
- Build six rectangular relief polygons: bottom-left, bottom-right, top-primary-left/right, top-secondary-left/right.
- Use Shapely `Polygon`, `box`, `unary_union`, and `difference` when Shapely is importable.
- Provide a pure orthogonal fallback that stitches the relief boundaries into an outline from calculated relief rectangles, but keep that fallback inside `OutlineBuilder`; callers never assemble perimeter points.
- Validate output is one closed simple exterior and positive area.
- Return a normalized clockwise/counter-clockwise exterior list starting at the bottom-left surviving edge for deterministic DXF/test output.

- [ ] **Step 4: Run outline tests**

Run:
```bash
python -m pytest test_sheetmetal_geometry.py -k "outline or primary" -v
```

Expected: PASS.

---

### Task 5: Migrate relief configuration without silently changing legacy units

**Files:**
- Modify: `config.ini`
- Modify: `ae.py`
- Modify: `test_sheetmetal_geometry.py`

**Interfaces:**
- `ae.py` produces `RELIEF_CONFIG: ReliefConfig`.

- [ ] **Step 1: Add a config parsing unit helper to `ae.py`**

Add defaults:

```ini
[RELIEF]
top_secondary_x_factor = 0.5
top_secondary_depth_factor = 2.0
bottom_x_factor = 0.5
bottom_y_factor = 0.5
```

Keep `[NOTCH]` readable but do not reinterpret `bottom_gap=0.5` as `0.5T`.

- [ ] **Step 2: Import the engine and construct config**

```python
from sheetmetal_geometry import EndCapGeometry, ReliefConfig, build_endcap_outline
```

Build a module-level `RELIEF_CONFIG` from `[RELIEF]` with the stated defaults.

- [ ] **Step 3: Run pure geometry tests**

Run:
```bash
python -m pytest test_sheetmetal_geometry.py -v
```

Expected: PASS without importing ezdxf.

---

### Task 6: Integrate the geometry engine into `export_end_cap_dxf()`

**Files:**
- Modify: `ae.py`
- Modify: `test_endcap_corner_relief.py`

**Interfaces:**
- `export_end_cap_dxf()` delegates CUTTING exterior generation to `build_endcap_outline()`.

- [ ] **Step 1: Replace the inline 16-point CUTTING literal**

After `total_width`/`total_depth` resolution:

```python
geometry = EndCapGeometry(
    total_width=total_width,
    total_depth=total_depth,
    thickness=t,
    fw=fw,
    left_fold=yl1,
    right_fold=yr1,
    top_first_fold=ytop1,
    bottom_fold=ybottom1,
)
cutting_points = [(p.x, p.y) for p in build_endcap_outline(geometry, RELIEF_CONFIG)]
msp.add_lwpolyline(cutting_points, dxfattribs={'layer': 'CUTTING'})
```

Remove the top CUTTING formulas that depend on `zl1/zr1`. Keep `zl1/zr1` in the public signature temporarily for compatibility.

- [ ] **Step 2: Derive BEND clipping coordinates from corrected relief dimensions**

Use the engine-calculated relief dimensions for line start/end clipping only where existing BEND lines terminate at CUTTING. Preserve all five BEND lines and their physical bend locations.

- [ ] **Step 3: Update CHECK text to report factor-based relief values**

Do not change unrelated CHECK text.

- [ ] **Step 4: Replace parity tests with corrected integration expectations**

`test_endcap_corner_relief.py` should:
- skip the module with `pytest.importorskip("ezdxf")` if ezdxf is unavailable;
- export a symmetric `T=2` case and assert CUTTING includes corrected points `(40, top)`, secondary `(16, ...)`, bottom `(16, 0)`;
- verify `zl1/zr1` changes do not alter CUTTING;
- verify exactly five BEND lines remain.

- [ ] **Step 5: Run integration tests where ezdxf is installed**

Run:
```bash
python -m pytest test_endcap_corner_relief.py -v
```

Expected: PASS. In environments without ezdxf, tests SKIP rather than preventing pure geometry tests.

---

### Task 7: Verification and packaging

**Files:**
- All modified files.

**Interfaces:**
- Final artifact: modified repo-ready project.

- [ ] **Step 1: Compile pure Python modules**

Run:
```bash
python -m py_compile sheetmetal_geometry.py ae.py gui.py
```

Expected: PASS when ezdxf is available for import-independent compilation.

- [ ] **Step 2: Run pure geometry suite**

Run:
```bash
python -m pytest test_sheetmetal_geometry.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full pytest suite**

Run:
```bash
python -m pytest -v
```

Expected: pure geometry PASS; ezdxf integration PASS when dependency exists or cleanly SKIP when absent.

- [ ] **Step 4: Search for forbidden legacy end-cap perimeter assembly**

Run:
```bash
python - <<'PY'
from pathlib import Path
text = Path("ae.py").read_text(encoding="utf-8")
assert "notch_tl_x = abs(zl1) + fw + t" not in text
assert "sub_tl_x = abs(yl1) - notch_sub_x_half * t" not in text
print("legacy wrong formulas removed")
PY
```

Expected: prints `legacy wrong formulas removed`.

- [ ] **Step 5: Package the working tree**

Create:
```text
whd-corner-new-engine-implemented.zip
```

Include source, tests, docs, baseline DXF assets, and config; exclude `__pycache__`.

