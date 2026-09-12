# Issue #163 preflight evidence

Task: #163 structural UI relayout — left pane only part selector + active inputs with scroll reachability at text scales 1.0/1.2/1.4; top only File + Corner Data; move other controls right; preserve #119/#127 lifecycle and stable physical-part identity; no manufacturing geometry rewrite.

## Skills read
- UI設計與去AI味
- phase6-corner-3d-model-integrity
- 驗證板件與DXF
- monitoring-remote-qa

## References read
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md

## Locked boundaries
- Structural UI only; no manufacturing geometry/formula/source-of-truth rewrite.
- Left column owns part selector + selected-part inputs; overflow must be vertically scrollable at 1.0/1.2/1.4 text scale.
- Top command surface owns only File + Corner Data.
- Other controls relocate to right-side control region without changing callbacks/state ownership.
- Corner Data lifecycle and multipart stable physical-part identities remain unchanged.
- Validation/viewport/layout measurements are judge-only and never feed production geometry.
- Remote QA is actively polled to terminal; temporary QA files are removed before acceptance.
