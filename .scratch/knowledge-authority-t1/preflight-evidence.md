# Issue #173 T1 Knowledge Preflight Evidence

- Issue: https://github.com/looaeedr/whd/issues/173
- Work branch: `docs/knowledge-authority-t1-20260913`
- Production target: `cleanup/2d-3d-sync`
- Baseline SHA: `6a26e7be05a8098c8b9b2bff6f0fd675d3491e45`
- Task: establish a canonical authority map and eliminate dual-current / forked mirror documentation authority.

## Required Skills read

- `Python測試實務` — read in full before T1 contract-test work.
- `monitoring-remote-qa` — read in full before creating and monitoring the one-shot remote QA workflow.
- `尺寸語意分析` — reread in full because T1 changes the compatibility entry for the Phase6 dimension-semantics authority; this Skill remains validation-only and does not create manufacturing formulas.

## Required References read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md

## Actual changed-file set for final work-branch Preflight

- `tests/knowledge/test_knowledge_authority_contract.py`
- `個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `07_Phase6尺寸語意與標準截角母規則.md`
- `標準基準檔格式.md`
- `.github/workflows/issue173-t1-authority-qa.yml` (one-shot QA only; remove before closure)
- `.scratch/knowledge-authority-t1/preflight-evidence.md` (execution evidence only; exclude from production durable integration)
- `.scratch/knowledge-authority-t1/state.md` (execution checkpoint only; exclude from production durable integration)
- `.scratch/knowledge-authority-t1/journal.md` (execution journal only; exclude from production durable integration)

## Preflight history

Initial contract-test scope:

- REQUIRED SKILLS: `Python測試實務` ✓
- REQUIRED REFERENCES: `06_踩坑記錄與防錯經驗庫.md` ✓
- REQUIRED REFERENCES: `08_WHD技能建立與修改規則.md` ✓
- exit code: `0` (GREEN)

Expanded remote-QA scope:

- REQUIRED SKILLS: `Python測試實務` ✓
- REQUIRED SKILLS: `monitoring-remote-qa` ✓
- REQUIRED REFERENCES: `06_踩坑記錄與防錯經驗庫.md` ✓
- REQUIRED REFERENCES: `08_WHD技能建立與修改規則.md` ✓
- exit code: `0` (GREEN)

Final closing gate is executed by `.github/workflows/issue173-t1-authority-qa.yml` against the actual changed-file set above. The canonical AI-library dimension spec was also reread explicitly so the MIRROR conversion cannot silently redefine its engineering content.

No manufacturing geometry, DXF baseline, `config.ini`, or `基準檔/**` file is in T1 durable scope.
