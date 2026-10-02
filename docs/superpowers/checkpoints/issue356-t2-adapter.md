# Issue #356 T2 — manufacturing request builder / Tk-aware adapter

## Identity
- Master: #353
- Task: #356 / T2
- Predecessor: #355 accepted HEAD `31120252965d0c4a26af9aff907713c095fd402c`
- Fixed semantic baseline: `7a8b87f8cbb50a34c5038aa196fa137b301702a4`
- Branch: `refactor/issue356-manufacturing-adapter-20260919`

## RED
RUN `35403934739`:
- **3 FAIL / 1 PASS**
- failures are exactly missing `phase6_manufacturing_adapter.py`
- canonical resolver unchanged guard: PASS

## GREEN
RUN `35404007404` / job `105789858749`:
- **4 PASS / 0 FAIL**

## Adapter contract
`phase6_manufacturing_adapter.py` now:
- reads app/workspace state
- filters physical BoxBody child identities from canonical aggregate part inventory
- builds per-part immutable scene/profile/dimension/feature inputs
- captures box-body structure state
- captures assembly joint input snapshot
- extracts assembly intent / 3D fallback / relief clearance / cabinet model
- constructs immutable `ManufacturingResolveRequest`
- records semantic source fingerprint using the request contract

The adapter does **not**:
- import `fold_designer_bridge`
- own collision/joint/relief solver loops
- call `_phase6_resolve_explicit_joint_reliefs`
- call world backprojection solver
- switch the canonical manufacturing resolver

## Scope
Diff from T1 contains only:
- new adapter
- adapter tests
- temporary QA workflow

No `phase6_manufacturing_geometry.py` change occurred.

Next: #357 / T3 explicit diagnostics / mutation / effects result contracts.
