# Issue #361 T7 — bridge one-line manufacturing compatibility facade

## Identity
- Master: #353
- Task: #361 / T7
- Predecessor: #360 accepted HEAD `9b445fc30a58aa03ecc2bf65f855d3802de4ea05`
- Fixed semantic baseline / production: `7a8b87f8cbb50a34c5038aa196fa137b301702a4`
- Expanded parity RUN: `35415982602` / job `105824620877`

## Accepted architecture
Bridge entry is now compatibility-only:

```python
def _phase6_resolve_manufacturing_geometry(self):
    return resolve_for_app(self)
```

Adapter now owns:
- scene payload construction from app/workspace state
- finished-dimension adapter
- render-data provider wiring
- PartSpec provider wiring
- explicit publish-effect wiring
- request → service → apply flow

The bridge scene-payload and finished-dimension helpers remain only as compatibility wrappers around adapter-owned canonical functions.

`read_standard_part_profiles` reverse mapping was also canonicalized in the adapter; bridge keeps only a wrapper, avoiding duplicate implementation.

## Legacy compatibility
- `Phase6FoldDesignerApp._phase6_resolve_manufacturing_geometry` entry is explicitly wired
- bridge import/re-export path remains
- resolved manufacturing bridge tests remain GREEN
- pure service ownership remains unchanged

## RED
Initial T7 RUN `35415683335`:
- **5 FAIL / 28 PASS**
- exact missing one-line facade / adapter ownership / legacy-entry gaps

After implementation, one stale T4 assertion was evolved to the T7 architecture contract.

## Focused GREEN
RUN `35415932950`:
- **33 PASS / 0 FAIL**
- cache performance PASS

## Expanded parity GREEN
RUN `35415982602` / job `105824620877`:
- **88 PASS / 3 SKIP / 0 FAIL**
- cache performance PASS
- phase1 hit: **35,359 ns**
- phase2 adapter pre-scan: **38,509 ns**
- phase1 hit end-to-end: **35,952 ns**
- phase2 hit end-to-end: **41,481 ns**
- hit ratio: **1.1538x**
- absolute delta: **5,529 ns**

## Scope
No solver loop, joint/relief algorithm, geometry policy, persistence schema, config, DXF or protected reference file changed.
Production remains untouched.

Next: #362 / T8 final Phase 2 A/B acceptance and production integration.
