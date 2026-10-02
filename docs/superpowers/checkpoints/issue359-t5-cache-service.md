# Issue #359 T5 — explicit manufacturing cache service + performance parity

## Identity
- Master: #353
- Task: #359 / T5
- Predecessor: #358 accepted cleanup HEAD `9c291563b3c5cc0e925c7c1a6d193e824b2bd63f`
- Fixed semantic baseline / production: `7a8b87f8cbb50a34c5038aa196fa137b301702a4`
- Branch: `refactor/issue359-manufacturing-cache-service-20260919`
- Final tested SHA: `1ba180602cbb3abff6456df3c76f23379cc4f86b`

## RED
Initial T5 RED:
- **7 FAIL / 15 PASS**
- failures were exact missing T5 pieces:
  - cache service module
  - semantic cache key
  - cache-aware adapter resolver
  - performance A/B gate

## Architecture accepted
New `phase6_manufacturing_cache.py` owns:
- `ManufacturingCacheKey`
- `ManufacturingCacheLookup`
- `ManufacturingCacheService`
- explicit `lookup / store / clear`
- explicit `ManufacturingCacheReceipt`

The app may retain a reference to the cache service, but the app-owned legacy fields are no longer cache authority.

Authoritative hit flow:
```text
cheap semantic signature
→ immutable ManufacturingCacheKey
→ ManufacturingCacheService.lookup
→ HIT returns cached ManufacturingResolveResult.geometry
→ full DTO is not built
```

Miss flow:
```text
cheap key miss
→ build immutable ManufacturingResolveRequest
→ resolve ManufacturingResolveResult
→ apply compatibility state/effect
→ recompute post-effect semantic key
→ explicit cache store
```

## Functional acceptance
Proven:
- equal manufacturing input → hit
- manufacturing change → miss
- UI-only `ui_text_size` change → same key
- separate app object identity with same semantic state → same key
- cache hit returns before full request build
- legacy `_phase6_last_resolved_manufacturing_*` fields are not lookup authority
- non-`ManufacturingResolveResult` storage is rejected
- cached stored result remains immutable result envelope

Legacy result/signature attrs remain compatibility mirrors only for existing readers.

## Final expanded parity
RUN `35408261169` / job `105802423996`:
- **77 PASS / 3 SKIP / 0 FAIL**

Suite covers T4 parity set plus T5 cache contracts.

## End-to-end performance A/B
Same final RUN:

```text
phase1_signature_build_ns       = 52,211
phase2_adapter_prescan_ns       = 56,990
key_staging_ns                  = 3,667
freeze_canonicalization_ns      = 87,701
full_dto_build_ns               = 233,121
cache_lookup_ns                 = 2,683
unavoidable_apply_overhead_ns   = 1,541
miss_full_assembly_resolve_ns   = 798,634
phase1_hit_end_to_end_ns        = 52,422
phase2_hit_end_to_end_ns        = 62,125
cache_hit_ratio                 = 1.1851
cache_hit_absolute_delta_ns     = +9,703
```

Performance gate: **PASS**.

The full DTO build (~233 µs) is not on the cache-hit path.

Next: #360 / T6 remove remaining self/app runtime dependency from domain service.
