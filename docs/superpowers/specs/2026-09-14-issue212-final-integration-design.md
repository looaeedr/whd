---
whd_doc_role: HISTORICAL
whd_contract: design-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue #212 T8 Final Integration Design

## Goal
Integrate the accepted #203 T0-T7 modularization chain into the current `cleanup/2d-3d-sync` lineage without changing production behavior, geometry, DXF semantics, project schema, authoritative state ownership, or current durable execution rules.

## Locked inputs
- Production base: `cleanup/2d-3d-sync @ e0a82f28f4ce3204c9fae56326f34f1a0964851f`.
- Accepted T7 exact target: `254f82f589e684b59e48dabb93ce2a6767d440bc`.
- T7 accepted parent: `f486a61534f02890c9f497422bf99d7a2bec34c3`.
- T6 accepted cleaned head: `2e354528791eec4307f039c805bed4b743b3c265`.
- Integration candidate: `integrate/issue212-final-combined-20260914`.
- Clean T7 source: `integrate/issue212-t7-accepted-20260914`.

## Integration strategy
The candidate starts from the current production head. Bring the exact accepted T7 source into the candidate; do not use the later T7 branch head because it contains QA-trigger scratch residue. Any merge conflict is resolved only on the candidate.

For files modified on both production and the T0-T7 chain, preserve the newer production durable-rule behavior unless the T7 side contains a non-conflicting durable rule that remains required. In particular, `monitoring-remote-qa/SKILL.md` must retain the production `EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE`, no-run/no-wait behavior, active polling, long-log handling, and 30-second reporting rules while retaining compatible T7 additions.

## No-go
- No direct edit, merge, force update, or rollback of `cleanup/2d-3d-sync` before final acceptance.
- No feature work or opportunistic bug fix.
- No production geometry/DXF change to satisfy validation.
- No assertion weakening or golden/baseline rewrite to force GREEN.
- No second authoritative 2D/3D state or renderer-owned geometry source.
- No use of QA trigger/scratch/workflow residue as production input.
- Validation may judge correctness but must not become a production calculation source.

## Candidate cleanup
Remove temporary T0-T7 QA workflows, trigger markers, probes, and `.scratch` evidence that is not designated durable evidence. Preserve permanent regression tests, production modules, approved Skills/AI-library rules, specifications, and acceptance evidence required by repository policy.

## Final acceptance gates
1. Fail-closed knowledge preflight on the exact candidate SHA.
2. Dependency/lineage audit: candidate must contain current production lineage and accepted T7 lineage.
3. Focused modularization suites GREEN.
4. Full Headless regression terminal with exact pass/fail/skip counts.
5. Full Xvfb regression terminal with exact pass/fail/skip counts.
6. L1 Model/State parity GREEN.
7. L2 Geometry parity GREEN.
8. L3 Projection/Render parity GREEN.
9. L4 UI parity GREEN, except a failure may be classified inherited only with exact parent/candidate A/B evidence proving identical nodeid and failure signature.
10. 2D↔3D synchronization, physical-part identity, Save→Reload, and DXF reopen GREEN.
11. `config.ini`, baseline DXF/reference manifest, project schema, and protected reference invariants GREEN.
12. Production geometry drift = 0 outside the approved Move-Only modularization diff.
13. Temporary QA artifacts cleaned and cleanup re-read from remote branch.
14. Re-fetch `cleanup/2d-3d-sync`; if it drifted, stop integration and rebuild/revalidate the candidate against the new production head.
15. Only after all gates are terminal GREEN, perform non-force integration to `cleanup/2d-3d-sync` and run exact-production post-integration verification.

## Remote-QA execution rule
No RUN identity means `RUN_NOT_CREATED`, not a waiting state. Fix/execute the prerequisite that creates the RUN. Poll only after a concrete `run_id + head_sha` exists, and keep the same run locked until terminal or an explicitly diagnosed replacement is created.

## Closure
Close #212 and then #203 only after exact-production post-integration verification is terminal GREEN and final cleanup/drift audit is GREEN.