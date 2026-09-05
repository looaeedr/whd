# PHASE6 Joint Graph / 尺寸 / STANDARD 截角收斂實作規格

狀態：ready-for-agent  
日期：2026-08-31  
依據：`PHASE6 組合、尺寸、標準截角與 AssemblyJoint Graph 整合最高優先規格` 與目前程式盤點  
Skill evidence：phase6-corner-3d-model-integrity、phase6-overlay-relief-basis、to-spec、writing-for-agents

## Problem Statement

PHASE6 已經開始從舊模型遷移到 Joint Graph 與 Certified Relief Registry，但目前仍同時存在三條互相競爭的真值來源：高階 assembly type、Legacy Top CornerType、以及部分 Resolved Manufacturing Geometry。這會讓同一個箱體在 2D、單板 3D、組合 3D、DXF、Save/Reload、blank 報告之間出現漂移。

使用者目前面臨的核心風險是：規格已經明確定義「組合方式只是 preset、AssemblyJoint Graph 才是組裝真值、STANDARD + Semantic Delta 才是截角真值」，但程式仍有部分路徑會從 assembly type 或 CornerType 反推幾何，甚至讓舊測試期待和新 registry 行為互相衝突。

這份規格的目的，是把目前程式收斂到單一可驗證資料鏈：

```text
Canonical Dimension Model
→ Assembly Intent preset
→ Resolved AssemblyJoint Graph
→ STANDARD + Semantic Delta
→ Resolved Manufacturing Geometry
→ 2D / 單板 3D / 組合 3D / DXF / Save-Reload / blank report
```

## Solution

建立一個分階段遷移，先固定外部行為與資料模型，再逐步移除 legacy ownership：

1. 建立全域 Assembly Intent Registry，將每個高階 preset 展開成 TOP / BOTTOM / LEFT / RIGHT 的 default Joint Map。
2. 將使用者 override、Family geometry、legacy migration、solver-confirmed joint 分成不同 source，並保證 redraw / reload 不會用 preset 覆蓋 resolved/user data。
3. 將 Corner resolver 改成讀附近 AssemblyJoint，先取得 STANDARD 母體，再套用 Certified Registry 的 Semantic Delta。
4. 將 Receiving 下方 WRAP 完整歸入全域 Joint relation 與 Certified Registry，不再由 Receiving family 自己擁有 assembly-derived bottom corner policy。
5. 將 blank W×H 改由 material segment chain / physical piece data 取得；corner relief、孔洞、止裂只改 polygon area，不改 blank envelope。
6. 將目前已存在但和新規格衝突的 legacy test expectation 改成 migration/historical fixture，而不是正式 specification。

## User Stories

1. As an operator, I want to choose a familiar assembly preset, so that I can quickly start from a known manufacturing method.
2. As an operator, I want to override one edge without losing the other edges, so that real cabinet exceptions can be represented.
3. As an operator, I want Save/Reload to preserve edge overrides, so that reopened projects do not silently revert to a preset.
4. As an operator, I want Receiving bottom wrap to be shown as a bottom joint choice, so that it is not confused with the entire cabinet assembly type.
5. As an operator, I want OVERLAY to remove nonexistent X folds consistently, so that 2D and 3D show the same physical sheet.
6. As an operator, I want blank size to remain stable after local corner relief, so that purchasing/cutting size is not confused with remaining polygon bbox.
7. As a developer, I want Assembly Intent preset and resolved Joint Graph to be separate, so that UI shortcuts do not overwrite mechanical truth.
8. As a developer, I want every Joint relation to have global semantics, so that Family modules cannot redefine INSERT, OVERLAY, INSERT_OVERLAY, or WRAP.
9. As a developer, I want Family geometry to provide target faces and dimensions only, so that assembly meaning stays in the shared resolver.
10. As a developer, I want Corner resolver to read nearby joints, so that hybrid corners are derived from real edge relations.
11. As a developer, I want STANDARD corner geometry to come from real fold topology, so that each CornerType is no longer a dead formula.
12. As a developer, I want Certified Registry HIT to be canonical, so that production code cannot duplicate a second formula.
13. As a developer, I want Registry MISS to create provisional evidence only, so that solver discoveries are not shipped as certified manufacturing rules.
14. As a developer, I want Head and Tail to be verified independently, so that mirror/orientation bugs cannot hide behind one passing end.
15. As a developer, I want multi-piece Box Body blanks to be reported piece by piece, so that exploded preview envelopes never become manufacturing blanks.
16. As a developer, I want Receiving side/back split dimensions to remain material/outside separated, so that W-2.5T back panel width is not mixed with WRAP semantics.
17. As a developer, I want old `.p6fold` files to migrate once, so that old assembly type data becomes explicit joints without guessing new WRAP relations.
18. As a developer, I want regression matrices to enumerate registered intents and relations, so that future additions automatically require tests.
19. As a release owner, I want packaging gates to require Skill and registry evidence, so that delivery cannot omit the AI/process constraints or manufacturing database.
20. As a QA reviewer, I want diagnostics to show registry HIT/MISS, rule id, revision, relation, owner, pre-solve evidence, and post-solve penetration, so that failures are traceable.

## Implementation Decisions

- Add an Assembly Intent Registry as the single source for high-level preset definitions. Each preset stores display name, stable id, revision, and default Joint Map for TOP, BOTTOM, LEFT, and RIGHT.
- Represent `INSERT`, `OVERLAY`, and `INSERT_OVERLAY` as high-level preset ids only when used as operator shortcuts. `WRAP` remains a Joint relation and must not appear as a standalone EndCap assembly selector.
- Add the 「包覆貼外」 preset as a global Assembly Intent preset whose default Joint Map is TOP OVERLAY, LEFT INSERT, RIGHT INSERT, BOTTOM WRAP.
- Preserve the legacy `assembly_type` field as a UI/compatibility mirror during migration. It must not be the canonical source after a Joint Graph exists.
- Keep AssemblyJoint relation semantics global. Family modules may provide part existence, face positions, formed dimensions, and effective mating dimensions, but may not redefine relation meaning.
- Extend Joint records to carry edge, direction, contact mode, preserve side, clearance intent, relief intent, solver constraints, source, and revision. Existing fields can be migrated into this richer shape incrementally.
- Change intent application into two separate operations: apply preset defaults and resolve actual graph. Applying a preset may replace only intent-derived joints; it must preserve user-added and solver-confirmed joints.
- Change legacy migration so old assembly type creates explicit default joints once. Old explicit corner settings and user data must win over inferred preset defaults.
- Keep Top CornerType as a legacy projection for compatibility, but do not allow it to overwrite resolved Joint Graph data.
- Change top-corner resolution from `assembly_type → CornerType formula` to `nearby joints → STANDARD + Semantic Delta`.
- Keep Certified Relief Registry as the runtime source for known relief formulas. Registry metadata must include standard reference, affected zone, dimension space, target semantics, adjustment type, adjustment amount, topology level, evidence, and revision.
- Treat currently hardcoded values such as INSERT 1T and INSERT_OVERLAY 0.5T/2T as historical implementation or confirmed fixture unless a Certified Rule declares them as semantic defaults.
- Keep Receiving bottom WRAP as a global Joint relation with family-provided target geometry and registry-provided formula. Receiving may expose defaults/reserves, but may not own a custom relation meaning.
- Move blank reporting to resolved piece geometry. Blank width/height comes from material segment chain and physical piece split; final polygon bbox remains useful for area and diagnostics only.
- Keep 2D, single-part 3D, assembly 3D, DXF, NC, solver, and Save/Reload reading from Resolved Manufacturing Geometry once it exists.
- Keep committed relief state as replay cache with signatures. Any mismatch in rule revision, fold profile, formed FW, family structure, or joint graph invalidates replay and rebuilds from registry/solver.
- Make diagnostics first-class output from resolved geometry, not a UI-only side effect.

## Testing Decisions

- Use behavior tests at the highest seam: Assembly Intent to Resolved Joint Graph, Resolved Manufacturing Geometry, registry lookup, Save/Reload, and export/blank reporting.
- Keep tests focused on externally visible contracts: persisted graph, final material equality, blank dimensions, fold topology, registry evidence, and zero illegal penetration.
- Add a matrix that enumerates every registered Assembly Intent preset. Adding a new preset must automatically add acceptance cases.
- Add a matrix that enumerates every registered Joint relation. Adding a new relation must require semantics, ownership, serialization, diagnostics, and regression coverage.
- Add Head/Tail matrix coverage for each intent and mixed Head/Tail combinations.
- Add edge override cases: RIGHT WRAP, LEFT/RIGHT asymmetric relation, BOTTOM WRAP, and TOP OVERLAY + SIDE INSERT hybrid.
- Add Family matrix coverage for 金庫型 and 受電箱, with future families automatically included when registered.
- Add migration tests for old snapshots with only assembly type, old snapshots with explicit corner state, and snapshots with user-added joints.
- Add Receiving regression tests that assert bottom corner policy is STANDARD unless WRAP registry applies a bottom joint relief.
- Add blank tests that prove local corner relief changes area but not blank W×H.
- Add OVERLAY tests that prove flat-X topology removes X BEND in 2D, single-part 3D, assembly 3D, fold editor, and DXF.
- Add registry tests that reject Certified Rules missing standard metadata or evidence.
- Add replay-cache tests that stale old committed relief when signatures change.
- Keep GUI tests only where operator state is the behavior under test; put geometry logic under headless tests.

## Out of Scope

- Rewriting every part adapter in one pass.
- Changing existing DXF layer names or CAD output conventions unrelated to Joint Graph migration.
- Introducing CAM-only details such as kerf compensation, over-cut holes, bend machine compensation, or NC post-processing.
- Certifying new manufacturing numeric defaults that are explicitly marked open in the integrated spec.
- Removing legacy fields immediately from project files. Legacy fields remain as migration mirrors until the new graph is stable.
- Building a full UI for arbitrary edge editing in this spec’s first implementation pass, beyond preserving and resolving edge data.

## Further Notes

Current code already contains partial infrastructure: global Joint relation enum, Joint serialization, resolved manufacturing geometry, registry runtime lookup, Receiving bottom WRAP registry, true-thickness mesh, and Save/Reload relief state. The implementation should not restart from scratch.

The highest-risk gaps are:

1. Intent currently expands mostly to side joints, not a full TOP/BOTTOM/LEFT/RIGHT graph.
2. Some paths still let assembly type or Top CornerType drive geometry.
3. Some tests still encode old Receiving bottom `INSERT_OVERLAY` expectations.
4. Blank reporting still depends on final material bbox instead of segment-chain blank.

First implementation ticket should be a tracer bullet: introduce the Assembly Intent Registry and prove `INSERT_OVERLAY` and 「包覆貼外」 can resolve into explicit four-edge Joint Graphs without changing final geometry yet. Once that seam is stable, migrate corner resolution and blank reporting behind the same resolved model.
