# Issue #359 T5 — explicit manufacturing cache service

- Predecessor: #358 accepted HEAD `9c291563b3c5cc0e925c7c1a6d193e824b2bd63f`
- Fixed semantic baseline remains `7a8b87f8cbb50a34c5038aa196fa137b301702a4`
- GREEN RUN `35408192899` / job `105802220775`: SUCCESS
- contracts: **22 PASS / 0 FAIL**
- cache performance A/B: PASS
- cache_hit_ratio: **1.2004**
- cache_hit_absolute_delta_ns: **10283**
- `PASS CACHE_HIT_END_TO_END_PERFORMANCE=1`

Accepted architecture:
- explicit `ManufacturingCacheService`
- explicit `ManufacturingCacheKey`
- cache hit/miss authority no longer comes from app-owned last-result fields
- Phase 1 cheap semantic signature is retained as pre-scan key source
- cache hit occurs before full DTO construction
- legacy last-result fields remain compatibility mirrors only
- key excludes app/Tk/callback/object identity
- cache service stores `ManufacturingResolveResult` only

Next: #360 / T6 pure manufacturing orchestration.
