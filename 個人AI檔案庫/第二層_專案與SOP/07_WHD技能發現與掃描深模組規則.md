# WHD 技能發現與「掃描深模組」規則

## 目的

避免 AI 因只讀 `skill_registry.json`、README 或少量目錄，就錯誤宣稱某個 WHD Skill 不存在。

## 強制技能發現規則

1. WHD 專案技能的完整存在性判定，以實際掃描 `.agents/skills/**/SKILL.md` 為準。
2. `skill_registry.json` 是 Preflight 路由表，不是完整 Skill 清單；不能因 registry 沒列出某 Skill 就判定不存在。
3. 各分類 README 是導覽入口，不是完整存在性證據；README 漏列時仍必須掃描實際 `SKILL.md`。
4. 使用者明確指定 Skill 名稱時，必須優先用精確名稱查找，禁止以名稱相近或語意相似的 Skill 代替。
5. 若使用者說「一定有」或糾正 AI 的 Skill 判斷，AI 必須改用完整 tree / `.agents/skills/**/SKILL.md` 驗證，而不是重複用相同 registry 或 code search 結論。

## 「掃描深模組」正式位置

- Skill 名稱：`掃描深模組`
- 正式路徑：`.agents/skills/engineering/掃描深模組/SKILL.md`
- 同目錄支援檔：
  - `HTML-REPORT.md`
  - `check_zh_tw_report.py`
  - `agents/openai.yaml`
  - `tests/test_check_zh_tw_report.py`
  - `tests/test_skill_sources_zh_tw.py`

## 觸發規則

當使用者輸入或明確要求下列任一語句時，必須直接載入並執行 `掃描深模組`：

- `掃描深模組`
- `深模組掃描`
- `掃描模組`
- 要求針對 WHD 做深層架構掃描、耦合掃描、模組邊界掃描

不得以以下 Skill 替代：

- `setup-ts-deep-modules`
- `improve-codebase-architecture`
- `codebase-design`
- 其他只因名稱含 `deep modules` 或架構語意相近的技能

這些 Skill 可以依 `掃描深模組/SKILL.md` 的要求被進一步載入，但不能取代使用者點名的主 Skill。

## 2026-09-08 糾偏紀錄

曾發生 AI 先讀 `skill_registry.json` 與部分 README，因未完整掃描 `.agents/skills/**/SKILL.md`，錯誤宣稱「掃描深模組」不存在，之後又誤把 `setup-ts-deep-modules` 當成候選。

根因：把「路由表 / 導覽文件」誤當成「完整技能目錄」。

永久修正：所有 Skill 存在性查詢都以實體 `SKILL.md` tree 為最終證據；使用者指定精確名稱時，禁止用相似 Skill 代答。
