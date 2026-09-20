# Issue #413 Phase 5 規格 Knowledge Preflight Evidence

- repository: `looaeedr/whd`
- target: `cleanup/2d-3d-sync`
- authoritative parent: `396bfd96524a44a178c29bbefaf1b7c0437c119f`
- work branch: `docs/issue413-phase5-bridge-spec-20260920`
- task: 撰寫新的 WHD Fold Designer Phase 5 規格書；針對 `fold_designer_bridge.py` 做架構掃描與深模組重構規劃。此階段僅規格，不做 implementation。
- machine preflight with planned changed files: PASS / RC=0

## REQUIRED SKILLS — READ

- 掃描深模組
- phase6-corner-3d-model-integrity
- executable-continuity-controller

Supporting Skills also read because required by 掃描深模組：
- 程式碼庫設計
- 深度質詢
- 領域建模
- 程式碼庫設計 / DEEPENING
- 程式碼庫設計 / DESIGN-IT-TWICE
- 掃描深模組 / HTML-REPORT

## REQUIRED REFERENCES — READ

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/07_WHD技能發現與掃描深模組規則.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md

## Source-first readback

- Phase 3 #363 / T8 #372：closed / completed。
- Phase 4 #388 / T8 #397：closed / completed；post-merge acceptance RUN `35479290249` SUCCESS。
- Phase 4 Settings deep owners、Final Scene deep owners、Phase 3 Workspace/Project/Registry/Corner-Data/Lifecycle owners視為已接受成果，本規格不得重包裝為新候選。
- Divider DM1–DM5 與 annotation semantic DM6 evidence 已回讀；製造/語意 owner 為 protected。
- `CONTEXT.md` 已回讀；本規格不新增產品／機械 domain definition。
- current bridge source readback：`fold_designer_bridge.py` blob `7ddbcec24693238772edb9209c271c57cdbe23f3`。

## Deep-module scan result

繁中 HTML scan 已在執行端 OS temp 產生並通過 `check_zh_tw_report.py` 等價交付檢查。

候選責任：
1. pure derived topology / operator projection
2. derived-part synchronization / editor sequencing
3. Settings / Corner presentation
4. Registry presentation
5. Assembly presentation
6. Operator Workspace presentation

Design It Twice 結論：
- 拒絕單一 giant `BridgeSurface` catch-all；
- 拒絕依函式 prefix 做 move-only 搬檔；
- 採 capability deep modules + existing composition root；
- 不為單一 adapter 建 speculative ports。

## Authority / prohibitions

- `SPECIFICATION_REQUIRED`：本規格 accepted 前不得建立 implementation ticket chain、implementation branch、RED/GREEN、production code change 或 production merge。
- pre-spec #416 / PR #417 evidence 不得成為正式 Phase 5 acceptance。
- pre-spec census tooling 可在正式 T0 fresh-validate 後決定保留/修正/移除，但目前不算 T0 accepted。
- manufacturing / Registry / CROSS / DXF / project schema / UI behavior / event ordering 均為 behavior-preserving protected surface。


## Final verification before spec PR

- remote branch readback: PASS
- changed files: exactly 2 (spec + this evidence)
- invalid arbitrary LOC hard target present: NO
- PRE_SPEC_IMPLEMENTATION_ACCEPTED_AS_EVIDENCE=0 marker: PRESENT
- DELETION_TEST_COMPLETE=1 T0 gate: PRESENT
- physical-part / DXF final gate: PRESENT
- implementation Issue creation before spec acceptance: FORBIDDEN
- deep-module Traditional Chinese HTML delivery checker: PASS
- final Phase6 Knowledge Preflight with both changed files + verification evidence: PASS / RC=0
