# Issue #355 T1 — immutable manufacturing DTO contracts

## Identity
- Master: #353
- Task: #355 / T1
- Predecessor: #354 accepted HEAD `bebd63e6f15c08b939b3ed4ad031fc7c06d2d8d3`
- Fixed Phase 2 semantic baseline remains `7a8b87f8cbb50a34c5038aa196fa137b301702a4`
- Branch: `refactor/issue355-manufacturing-dto-contracts-20260919`

## RED
Clean RED RUN `35403734322`:
- **4 FAIL / 1 PASS**
- all 4 failures: `ModuleNotFoundError: phase6_manufacturing_contracts`
- resolver-path source guard: PASS
- no unrelated dependency/harness failure remained

## GREEN
RUN `35403804721` / job `105789244084`:
- **5 PASS / 0 FAIL**

## Contracts added
`phase6_manufacturing_contracts.py` introduces:
- `FrozenMapping`
- recursive `freeze_manufacturing_value`
- deterministic canonical JSON
- deterministic SHA-256 fingerprint
- immutable `ManufacturingPartInput`
- immutable `ManufacturingResolveRequest`
- semantic request fingerprint excluding transport/revision metadata

## Invariants proven
- nested dict/list/set inputs are defensively frozen
- mutating original mutable sources after construction cannot mutate DTO state
- arbitrary callbacks are rejected
- Tk-like arbitrary objects are rejected
- mapping insertion order does not change semantic fingerprint
- canonical part-key ordering does not change semantic fingerprint
- manufacturing input change changes fingerprint
- resolver implementation is **not switched** in T1

## Scope
Diff from T0 contains only:
- new DTO contracts module
- focused DTO tests
- temporary branch QA workflow

No `phase6_manufacturing_geometry.py` solver change occurred.

Next: #356 / T2 request builder / Tk-aware adapter.
