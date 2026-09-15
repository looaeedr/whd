# Divider Physical Geometry Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 Divider Family/Fold/FW 的 raw segment identity 收斂在 Divider module 內，對 Manufacturing / Assembly / 2D / 3D / DXF / Save-Reload 暴露穩定的 physical semantics，且不改受電箱既有尺寸、孔位與已驗收 face-flush 幾何。

**Architecture:** `ae_engine/door_dividers.py` 是 Family-specific Fold Contract → Divider Physical Geometry Contract 的唯一解析邊界。Family contract 仍可用 `core_segment_index` / `frame_width_segment_index` 作 module implementation detail，但 `BoxBodyDividerPart.physical_geometry_contract` 會把它們解析成 semantic core segment、FW physical face flat band、placement datum、final-material/relief authority bindings；`manufacturing_api.py` 與 `fold_designer_bridge.py` 只消費 semantic contract，不再自行解讀 raw index。

**Tech Stack:** Python 3.11, dataclasses, existing `FoldProfileSegment`, Shapely/ezdxf manufacturing stack, pytest, GitHub Actions Phase6 Knowledge Preflight.

**Spec:** GitHub Issue #52 `DM2 — 收斂 Divider Family/Fold/FW Physical Geometry Contract`；上游 RED authority 為 Issue #51 與 `tests/test_dm1_divider_physical_contract.py`。

## Global Constraints

- Receiving Divider 包外 Fold Chain 保持 `18 / FW / 106 / 17`；Fresh Default FW=29。
- FW 是獨立 physical dimension Source of Truth；Fold Chain 可引用 FW，但不得重分配後冒充 FW。
- `frame_width_segment_index` / `core_segment_index` 可留在 Divider module implementation 內，但不得要求 sink 解讀。
- 不改產品尺寸、既有孔位、certified relief formulas 或 registry authority。
- 同一 canonical manufacturing geometry 必須持續驅動 2D / single-part 3D / Assembly 3D / DXF / Save-Reload。
- #47 T48-1 已驗收 Divider FW face-flush relation 不得回歸。
- Vault / non-Receiving 行為不得被 Receiving contract 污染。
- 正式 AI Library / Skill authority writeback 延後至 DM5。

---

### Task 1: Divider module 產生 semantic physical contract

**Files:**
- Modify: `ae_engine/door_dividers.py`
- Test: `tests/test_dm1_divider_physical_contract.py`

**Interfaces:**
- Consumes: `cabinet_family_policy.divider_fold_contract(...)` 現有 mapping，內含 `signed_fold_chain`, `material_lengths`, `formed_core_depth`, `core_segment_index`, optional `frame_width_segment_index`。
- Produces: `BoxBodyDividerPart.physical_geometry_contract -> Mapping[str, object]`，固定 keys 至少 `core_physical_segment`, `fw_physical_face`, `placement_datum`, `final_material`, `relief_evidence`。

- [ ] **Step 1: 保留 #51 四顆 RED，不修改 expectation**

Run: `pytest -q tests/test_dm1_divider_physical_contract.py`
Expected before GREEN: four requirement failures because `physical_geometry_contract` is absent.

- [ ] **Step 2: 在 Divider module 內解析 segment geometry**

Implement a private semantic resolver in `door_dividers.py` that walks `material_lengths` once and converts implementation indexes into physical records. The FW record must expose semantic material-space band and outside dimension, for example:

```python
{
    "role": "FW_PHYSICAL_FACE",
    "flat_band": (start, end),
    "material_dimension": material_lengths[fw_index],
    "outside_dimension": abs(signed_fold_chain[fw_index]),
}
```

The core record similarly exposes role, flat band, material dimension, and formed outside depth. No public semantic record may contain `segment_index`.

- [ ] **Step 3: 加入 stable contract property / field**

`BoxBodyDividerPart` must expose the semantic mapping while raw indexes remain internal compatibility fields only. `placement_datum` must identify the semantic datum source (`FW_PHYSICAL_FACE` + inward core orientation) without world-Z/bbox guesses. `final_material` and `relief_evidence` at part stage are authority bindings, not a second Polygon/formula; they identify canonical manufacturing resolve / assembly-relief as the later authority.

- [ ] **Step 4: Run DM1 contract tests**

Run: `pytest -q tests/test_dm1_divider_physical_contract.py`
Expected: `4 passed`.

- [ ] **Step 5: Commit module GREEN**

Commit message: `refactor(dm2): resolve Divider physical semantics in module`

### Task 2: Manufacturing metadata publishes semantic contract, not raw index

**Files:**
- Modify: `ae_engine/manufacturing_api.py`
- Test: `tests/test_dm1_divider_physical_contract.py`
- Test: `tests/test_issue40_divider_6p4_shared_datum.py`

**Interfaces:**
- Consumes: `divider.physical_geometry_contract`.
- Produces: `PartRenderData.metadata["physical_geometry_contract"]` plus existing non-semantic diagnostics/identity; removes sink-facing `frame_width_segment_index` / `core_segment_index` dependency.

- [ ] **Step 1: Add behavior assertion for render metadata**

Extend DM2 tests so `build_box_body_divider_render_data()` publishes `physical_geometry_contract`, and assert metadata does not expose `frame_width_segment_index` or `core_segment_index` as required sink inputs.

- [ ] **Step 2: Run focused test and confirm RED**

Run the exact new nodeid. Expected: current metadata still exposes raw index and lacks semantic contract.

- [ ] **Step 3: Migrate metadata**

Copy only serializable semantic values into metadata. Do not serialize Shapely Polygon objects as part of the contract and do not add a second final-material geometry. Keep `signed_fold_chain` / `material_lengths` only where needed to render actual fold geometry; their presence must not be required to identify FW physical face.

- [ ] **Step 4: Run focused metadata + Ø6.4 shared datum tests**

Run: `pytest -q tests/test_dm1_divider_physical_contract.py tests/test_issue40_divider_6p4_shared_datum.py`
Expected: GREEN.

- [ ] **Step 5: Commit manufacturing adapter migration**

Commit message: `refactor(dm2): publish semantic Divider render contract`

### Task 3: Face-flush bridge consumes semantic FW band

**Files:**
- Modify: `fold_designer_bridge.py`
- Test: `tests/test_dm1_divider_physical_contract.py`
- Test: `tests/test_assembly_collision_integration.py`

**Interfaces:**
- Consumes: `divider.render_data.metadata["physical_geometry_contract"]["fw_physical_face"]["flat_band"]`.
- Produces: existing `DIVIDER_FW_FACE_FLUSH_V1` evidence with unchanged physical-skin comparison semantics.

- [ ] **Step 1: Add/adjust regression so raw FW index is absent yet placement evidence remains valid**

The test must exercise the real `_phase6_divider_fw_placement_evidence` path or existing T48-1 equivalent, not source-string inspection.

- [ ] **Step 2: Run regression and confirm RED**

Expected: bridge currently asks metadata for `frame_width_segment_index` and therefore cannot certify without it.

- [ ] **Step 3: Replace raw-index lookup**

Change only Divider band selection: read semantic `flat_band` from the physical contract. Keep BoxBody `fw_left/fw_right` semantic phase6-key lookup and actual mapped skin-plane comparison. Do not replace face-flush with numeric FW equality, bbox, or world-Z constants.

- [ ] **Step 4: Run assembly/collision and contract regression**

Run: `pytest -q tests/test_dm1_divider_physical_contract.py tests/test_assembly_collision_integration.py`
Expected: GREEN; face-flush evidence remains a real physical-plane certificate.

- [ ] **Step 5: Commit bridge migration**

Commit message: `refactor(dm2): consume Divider FW physical face contract`

### Task 4: Family/topology and no-regression matrix

**Files:**
- Test: `tests/test_dm1_divider_physical_contract.py`
- Test: `tests/test_issue40_divider_6p4_shared_datum.py`
- Test: `tests/test_assembly_collision_integration.py`

**Interfaces:**
- Consumes: final semantic Divider contract and existing canonical manufacturing/assembly paths.
- Produces: durable evidence for Issue #52 acceptance.

- [ ] **Step 1: Run Receiving default and live-FW guards**

Verify `18 / 29 / 106 / 17`, then FW `29 → 37`, with unchanged contract interface and no magic-29 behavior.

- [ ] **Step 2: Run topology mutation guard**

Verify the existing #51 monkeypatch from 4 segments/FW index 1 to 5 segments/FW index 2 still passes with the same sink-facing keys.

- [ ] **Step 3: Run Vault / non-Receiving targeted guards**

Use existing family tests discovered in the current suite; do not invent Receiving policy as global fallback.

- [ ] **Step 4: Run #47/T48-1 face-flush equivalent and assembly collision targeted nodes**

Evidence must use exact pytest summary and remote run SHA.

- [ ] **Step 5: Audit `config.ini` and production drift**

Confirm `config.ini` hash unchanged and only Issue #52 scoped production/tests/workflow/evidence files differ from DM2 base.

### Task 5: Remote QA provenance and handoff

**Files:**
- Create/Modify: `.scratch/dm2/journal.md`
- Create/Modify: `.scratch/dm2/checkpoint.md`
- Modify: GitHub Issue #52 comments/state

**Interfaces:**
- Consumes: terminal GitHub Actions jobs with exact `run_id + head_sha + job_id`.
- Produces: auditable DM2 acceptance or explicit unresolved blocker; no false completion.

- [ ] **Step 1: Record Preflight provenance**

Record failed knowledge-gate run `34223996019@811ba565...` as pre-production gate failure, not requirement/production RED, and successful gate `34224130050@e663bf63...` as valid authorization.

- [ ] **Step 2: Run remote targeted workflow on final code head**

Only a terminal pytest summary with failed=0/errors=0 can satisfy GREEN.

- [ ] **Step 3: Write journal/checkpoint**

Include exact head SHAs, run/job IDs, test counts, invalid/revoked runs if any, `config.ini` invariant, and next legal phase.

- [ ] **Step 4: Total-control QA re-read**

Re-read Issue #52, final diff, tests, workflow logs, journal, and checkpoint. Any missing acceptance item keeps #52 open.

- [ ] **Step 5: Close #52 only if all acceptance checks pass**

If accepted, comment `[總控審查：ACCEPT DM2 / #52]`, close completed, then proceed to the next work order without modifying DM5 AI authority early.
