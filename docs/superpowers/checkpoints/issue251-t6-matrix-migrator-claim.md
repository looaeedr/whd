# Issue #251 T6-A claim

- Parent: #233
- Depends on: #250 (accepted and integrated)
- Parent T6 head at claim: `d1d1796e3ba2db30d629194ac053fa46e56aec8e`
- Work branch: `feat/issue251-t6-matrix-migrator-20260914`
- T1 authority: `docs/superpowers/verification/knowledge_authority_classification_v1.json`
- T1 authority blob SHA: `d1afe3013d74010ee23660659cd4692fade4a815`
- Execution contract: `.agents/skills/engineering/deterministic-repo-migration/SKILL.md`

## Hard gates

1. The T1 matrix is the sole role/mapping authority for this migration. No filename/prose/validator heuristic may invent roles.
2. Enumerate current governed Markdown and current metadata debt before mutation.
3. Any debt path missing from the matrix, mapped to `UNRESOLVED`, or carrying an unresolved blocker fails closed before migration.
4. Migration must be deterministic and later prove second-run zero diff.
5. Validation only judges correctness; it cannot become migration or production calculation authority.
6. No geometry, DXF, UI, manufacturing source, `config.ini`, or protected baseline mutation is permitted.
7. Temporary QA/census artifacts are not production authority and must be cleaned before acceptance.
