# DM2 Journal — Issue #52

- Task: DM2 — 收斂 Divider Family/Fold/FW Physical Geometry Contract
- Owning issue: #52
- Work branch: `work/dm2-divider-physical-contract`
- Base: `154a4e5098b340dc80d73cae1f9d2aa895b9bdc1`
- Current role: `[轉移至：總控審查]` / `[當前角色：總控審查]`
- Status: COMPLETE

## Completed

- Divider module now exposes sink-facing semantic `physical_geometry_contract`.
- Receiving `18 / 29 / 106 / 17` remains authoritative; FW outside dimension stays 29 by default and tracks custom FW dynamically.
- `manufacturing_api.py` no longer publishes raw `frame_width_segment_index` / `core_segment_index` as sink contract.
- `fold_designer_bridge.py` consumes semantic FW/core physical bands rather than raw segment indexes.
- Topology-mutation guard proves family fold topology/index changes do not alter the sink-facing interface.
- T48-1 FW face-flush, Divider Ø6.4 datum, assembly collision, Receiving/Vault family guards all pass.

## Key commits

- `7de0ea94174980e5343d58d2ee939275fec40087` — `refactor(dm2): resolve Divider physical semantics`
- `e10602db4f3493007542d22f5b4c684e5a5a8b6a` — `fix(dm2): resolve Divider core start from physical semantics`
- Final QA evidence head: `97c28ebb40eb3af598c5d5c981eb778a3111e561`

## Remote QA evidence

### INVALID_HARNESS
- Run `34226720981` @ `ceac3ff90180d94a5a5ce5b8b441c57e93ed7a24`
- DM2 contract: 5 PASS
- Assembly collision: 47 PASS
- Family auto-discovery was too broad and collected 89 files; runner lacked `matplotlib`, causing 21 collection errors.
- Classified as harness invalid, not production failure.

### Real regression found
- Run `34226911570` @ `3cfdeefae047357e38932c8aa18bb2bebbe7865c`
- DM2 contract: PASS
- Assembly collision: PASS
- T48-1: 5 PASS / 1 FAIL / 1 SKIP
- Root cause: `_phase6_divider_relief_core_start()` still fell back to sink metadata `core_segment_index` after DM2 intentionally removed raw index propagation.

### Regression fix verification
- Run `34227017269` @ `65a449d7327db08b7277ed5bbfe3352f60ecff6f`
- Job `102063502317`
- DM2 semantic contract: PASS
- T48-1 face-flush gate: PASS
- Assembly collision: PASS
- Verified fix committed as `e10602db4f3493007542d22f5b4c684e5a5a8b6a`.

### Final branch-head acceptance
- Final QA run `34227116798` @ `97c28ebb40eb3af598c5d5c981eb778a3111e561`
- Job `102063831133`
- Result: terminal SUCCESS
- DM2 physical contract: 5 PASS
- Assembly collision: 47 PASS / 2 warnings
- T48-1 FW face flush: 6 PASS / 1 SKIP
- Divider Ø6.4 shared datum: 4 PASS
- Receiving/Vault family guards: 14 PASS / 12 SKIP
- Total executed assertions: 76 PASS / 13 SKIP / 0 FAIL / 0 ERROR
- `RAW_INDEX_LEAK_SCAN=PASS`
- `DM2_DRIFT_AUDIT=PASS`
- `CONFIG_INVARIANT=PASS`
- `CLEAN_TREE=PASS`
- `config.ini` before/after SHA256: `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`

### Final knowledge gate
- Preflight run `34227116813` @ `97c28ebb40eb3af598c5d5c981eb778a3111e561`
- Result: terminal SUCCESS

## Cleanup evidence

- Removed temporary workflows:
  - `.github/workflows/dm2-core-semantic-fix.yml`
  - `.github/workflows/dm2-targeted.yml`
  - `.github/workflows/dm2-preflight.yml`
- Remote cleanup head was `28c86e305bbaab5bb3fe98866ab9b683415a9966` before final journal/checkpoint updates.
- Compare `97c28ebb... → 28c86e30...`: only the three workflow deletions plus `.scratch/dm2/journal.md` and `.scratch/dm2/checkpoint.md`; no production-code drift.

## Next owner

#53 DM3 — Divider canonical relief、final material 與 placement datum 單源化.
