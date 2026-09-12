# #160 dispatch journal / #162 preflight evidence

## Durable dispatch state

- Master: #160
- Production target: `cleanup/2d-3d-sync @ fa6cffbb310d39048c770c96fa258758e97db16a`
- Dispatch order: #161 -> #162 -> #163 -> #164
- Runtime model: no independent background subagent is claimed; the same execution context performs PM -> Implementer -> QA role transitions.

## T1 checkpoint — ACCEPTED

- Issue: #161
- Role transition: PM -> T1 Implementer -> QA
- Work branch: `fix/receiving-boxbody-unfold-restore-20260912`
- Accepted cleaned HEAD: `0c3932dfee117f5980e7d3717341ef184090afc3`
- Implementation commit: `46d05db8a9aa136eec37a69a1f6c4dd49fb231d8`
- RED: Receiving aggregate `box_body` resolved to remembered `box_body:back`
- GREEN: run `34696623825`, job `103561103692`, 13 PASS / 0 FAIL; `config.ini` unchanged
- Durable diff: `fold_designer_bridge.py` plus Receiving-specific regression test; temporary apply workflow removed
- Status: #161 CLOSED / ACCEPTED

## T2 checkpoint — RUNNING

- Issue: #162
- Current role: T2 Implementer
- Branch: `fix/issue162-unfold-viewport-20260912`
- Branch base: `0c3932dfee117f5980e7d3717341ef184090afc3`
- Current scope: unfold viewport presentation only — black background, larger initial fit/readability, mouse-wheel zoom
- Forbidden scope in T2: #163 layout relocation; manufacturing geometry changes; zoom/fit feeding production geometry
- Preflight run `34697127276 @ 7867c3290c275c7d09d2e289f2385740b4703b72` failed closed because evidence was not yet supplied; this is a process/evidence failure, not a product failure.
- Pending: rerun task + changed-file preflight with this evidence; then establish T2 RED, implement minimal presentation change, run remote QA/invariants, QA review.
- Resume command: `python tools/phase6_skill_preflight.py --task "#162 unfold viewport presentation: black canvas, larger initial fit, mouse-wheel zoom; presentation only, no manufacturing geometry feedback" --changed-file gui.py --changed-file tests/test_issue162_unfold_viewport.py --evidence docs/superpowers/verification/2026-09-12-issue160-dispatch-issue162-preflight.md`

## Read Skills

- phase6-corner-3d-model-integrity

## Read References

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md

## Authority conclusions for #162

1. Viewport background/fit/zoom are presentation state only. They must not alter authoritative material, Fold, Relief, DXF, placement, or physical-part identity.
2. Receiving aggregate `box_body` remains the logical/assembly owner; manufacturable children remain stable `box_body:<role>` identities. T2 must not reintroduce a selector/resolver fork.
3. Validation values, screenshots, fit ratios, or zoom factors are acceptance evidence only; none may become production manufacturing inputs.
4. `config.ini` and protected baselines must remain unchanged unless explicitly required by the user; #162 does not require such changes.
