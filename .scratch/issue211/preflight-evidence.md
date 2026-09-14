# #211 / T7 Preflight Evidence

Parent: #203
Depends on: #210 CLOSED / completed
Accepted parent: `2e354528791eec4307f039c805bed4b743b3c265`
Branch: `refactor/issue211-renderer-dependency-gate-20260914`

Status: AUTHORITY_REREAD_COMPLETE

READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: 驗證板件與DXF
READ_SKILL: monitoring-remote-qa
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md

## T7 authority notes
- 2D / single-part 3D / assembly 3D / DXF / Save→Reload must consume one canonical manufacturing geometry chain; renderer modules may project but must not own or recompute a second manufacturing truth.
- Physical-part identity comes from current workspace / resolved manufacturing output. UI labels, tree/tab indices, aggregate navigation and renderer-only selection memory are not manufacturing identity authority.
- Visibility/render presentation is display state only. It must not change geometry, placement, collision datum, Certified Registry selection, physical existence, or persistence truth.
- Registry HIT is the canonical manufacturing answer. 3D collision/backprojection/render output is shadow validation evidence only and cannot overwrite certified formula/parameters.
- Multipart BoxBody must preserve stable physical identities and per-piece geometry/transforms; aggregate `box_body` cannot replace physical-piece manufacturing validation.
- Validation is one-way: screenshot, rendered numbers, bbox/probe/collision deltas and pytest expected values cannot become production geometry or compensation inputs.
- T7 remains fail-closed: do not introduce `gui_modules/render_2d.py` or `gui_modules/render_3d.py` until renderer dependency audit proves a seam SAFE.
- Remote QA uses the locked `run_id + head_sha` until terminal. Any piped fail-significant command must preserve exit status with `pipefail`; workflow colour alone is not acceptance evidence.
