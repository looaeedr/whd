# T8 Final QA Evidence

phase6-corner-3d-model-integrity
phase6-release-packaging
diagnosing-bugs
tdd
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: release_required_artifacts.json

- Issue: #8 Medium UI Typography / Layout
- Source HEAD: 920521bfe35f5981ca55df0f6e9d76706a649b57
- Fresh headless targeted: 3 skipped (Tk display unavailable by policy).
- Fresh Xvfb targeted: 3 passed, 0 failed.
- Relevant assertions: main GUI left panel rescales under Medium/Large; Fold Designer controls update with text size.
- Production changes in finalization: none.
