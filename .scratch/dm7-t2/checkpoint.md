# DM7 T2 Checkpoint

- Task: #168 — Resolver / memory deep module
- Parent: #166
- Dependency: #167 CLOSED/completed
- Role: T2 實作者
- Branch: `feat/dm7-t2-navigation-core-20260913`
- Branch base / accepted predecessor: `4b236826a8629b2ae0088f71cea7b9e3d3f98659`
- Production target remains: `cleanup/2d-3d-sync@e85b10b3bf7957e626abb7c1e1e1f909b1f0ee62`
- Owning Issue: https://github.com/looaeedr/whd/issues/168

## Preflight

- First T2 preflight: fail-closed because `phase6-corner-3d-model-integrity` and 3 required references were unread.
- Missing Skill/reference evidence was read from authoritative target.
- Second T2 preflight: exit 0; all required Skills/References GREEN.

## Source-first root cause

Current bridge resolver still does:
`target = key if key in children else remembered if remembered in children else children[0]`.

Current compatibility piece selector also falls back to `wanted[0]` when active/memory is unavailable.

These are navigation/view fallbacks, not manufacturing authority. T2 must remove the guessing semantics without touching Fold/Relief/DXF/placement.

## Planned implementation

1. Add pure `phase6_part_navigation.py` as single owner for identity classification, explicit resolution, view-memory validation and hierarchy projection.
2. Keep bridge compatibility helpers as thin adapters only.
3. Missing explicit physical child -> `None`; no remembered/sibling/first-child substitution.
4. Remembered child is consumed only by explicit restore-child-context intent; stale memory clears.
5. Remove compatibility selector `wanted[0]` fallback.
6. Run T1 contracts + #161 regression + source ownership scan remotely.

## Stop boundary

T2 does not migrate all UI callers beyond the adapter seams (T3), and does not touch manufacturing geometry or persistence (T4/T5).
