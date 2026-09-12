# DM7 T2 Checkpoint

- Task: #168 — Resolver / memory deep module
- Parent: #166
- Dependency: #167 CLOSED/completed
- Role: T2 實作者 → 總控審查
- Branch: `feat/dm7-t2-navigation-core-20260913`
- Branch base / accepted predecessor: `4b236826a8629b2ae0088f71cea7b9e3d3f98659`
- Production target remains: `cleanup/2d-3d-sync@e85b10b3bf7957e626abb7c1e1e1f909b1f0ee62`
- Production adapter commit: `be295038c4291e4c20b81efbb3ee95e9a8f03bb6`
- Focused acceptance tested head: `e017cd4db05dfe5807c6d6f3963f429c5d3818c2`
- Patch workflow run: `34709054849` / job `103594331621` — SUCCESS
- Focused acceptance run: `34709093958` / job `103594435063` — SUCCESS
- Owning Issue: https://github.com/looaeedr/whd/issues/168

## Preflight

- First T2 preflight fail-closed because `phase6-corner-3d-model-integrity` and three required references were unread.
- Missing Skill/reference evidence was read from authoritative target.
- Re-run with the final known changed-file set: exit 0; all required Skills/References GREEN.

## Implemented

1. Added pure `phase6_part_navigation.py` as the navigation identity/hierarchy owner.
2. Bridge identity classification / top-level selector / Structure Tree helpers became thin adapters to that owner.
3. Explicit `box_body` stays aggregate; explicit existing child stays exact.
4. Missing explicit child resolves `None`; no remembered/sibling/first-child substitution.
5. Remembered child is consumed only through explicit `RESTORE_CHILD_CONTEXT`; stale same-child memory clears.
6. Compatibility BoxBody selector no longer falls back to `wanted[0]`.
7. Corner Data hierarchy consumes the same hierarchy projection.
8. Resolver/project code does not mutate `Phase6DesignerWorkspace` manufacturing state.

## Focused acceptance evidence

Run `34709093958 @ e017cd4db05dfe5807c6d6f3963f429c5d3818c2`:

- compile `phase6_part_navigation.py` + `fold_designer_bridge.py`: PASS
- navigation source-ownership scan: `NAVIGATION_SOURCE_OWNERSHIP=PASS`
- inherited T1 contracts + #96/#97 regressions: **20 passed / 0 failed / 1.35s**
- `config.ini` before/after exact SHA: `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`
- protected `基準檔/**` manifest before/after: exact PASS

The tested head differs from production adapter commit only by the temporary acceptance workflow used to trigger remote QA.

## Cleanup

- one-shot patch workflow removed at `6c1698b0cbb5c3b0dbea8b24aba84bd1fd51c273`
- one-shot acceptance workflow removed at `ee9b9626fbce076ae6d709eed1a4c654e304a565`
- final QA must verify tested-head → closing-head contains only workflow cleanup + `.scratch` evidence and no production/test drift.

## T2 stop boundary

Do not perform T3 caller migration beyond these adapter seams in #168. T3 owns the wider Menu / Structure Tree / Corner Data caller migration and GUI/Xvfb acceptance.
