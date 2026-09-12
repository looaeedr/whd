# Issue #173 T1 Knowledge Preflight Evidence

- Issue: https://github.com/looaeedr/whd/issues/173
- Work branch: `docs/knowledge-authority-t1-20260913`
- Production target: `cleanup/2d-3d-sync`
- Baseline SHA: `6a26e7be05a8098c8b9b2bff6f0fd675d3491e45`
- Task: establish a canonical authority map and eliminate dual-current / forked mirror documentation authority.

## Required Skills read

- `Python測試實務` — read in full before T1 test work.
- `monitoring-remote-qa` — read in full before creating the one-shot remote QA workflow.

## Required References read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md

## Planned changed files used for changed-file Preflight

- `tests/knowledge/test_knowledge_authority_contract.py`
- `個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `07_Phase6尺寸語意與標準截角母規則.md`
- `標準基準檔格式.md`
- `.github/workflows/issue173-t1-authority-qa.yml` (one-shot QA only; remove before closure)

## Executed changed-file Preflight

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

Execution note: the exact baseline preflight script (`e9dad181...`) was executed against the exact matched route projections from baseline registry blob `dae1a23e...`; the selected task/changed files match `python-testing-practices` and `remote-qa-monitoring` and no other registry route.

No manufacturing geometry, DXF baseline, `config.ini`, or `基準檔/**` file is in T1 scope.
