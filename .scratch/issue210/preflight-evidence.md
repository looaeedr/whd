# #210 / T6 Preflight Evidence

Parent: #203
Depends on: #209 CLOSED / completed
Base: accepted T5 cleaned head `e5c5d6cea1aae155b7110060e794fa865f7ac2ea`
Branch: `refactor/issue210-project-actions-20260914`

Status: AUTHORITY_REREAD_COMPLETE

READ_SKILL: 驗證板件與DXF
READ_SKILL: monitoring-remote-qa
READ_SKILL: phase6-corner-3d-model-integrity
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md

## T6 authority notes
- `.p6fold` Open/Save/Save As are project-level operations; persistence backend and visible entrypoints must share the same authoritative loader/writer path.
- Save→Reload must restore authoritative project/workspace state and rebuild derived UI/navigation projection; navigation memory, labels, tab/tree indices and view-only hierarchy are not persistence truth.
- Project transaction ownership must preserve committed vs draft isolation. Active Fold Designer draft must not leak into project save unless the canonical commit path has completed.
- No schema, serialization, path ownership, ProjectSession ownership or persistence semantics may be changed merely to make extraction easier. Hidden state dependency => HOLD / separate dependency-contract refactor.
- The T6 wrapper move must not alter manufacturing / Corner / Relief / AssemblyJoint / 3D authority. Certified Registry HIT remains canonical; 3D remains validation/discovery according to registry status. These authorities are reread only because preflight routes the affected persistence seam through full manufacturing-integrity guards.
- Validation is one-way; expected values, fixtures, probes and observed deltas cannot become production persistence/geometry authority.
- Remote QA is actively polled to terminal under exact `run_id + head_sha`; piped fail-significant commands require `pipefail`, and workflow colour alone is not acceptance evidence.
