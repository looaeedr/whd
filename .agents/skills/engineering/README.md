---
whd_doc_role: REFERENCE
whd_contract: skill-navigation
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Engineering

Engineering skills used for code, design, QA, specs and delivery.

> Navigation only. This README is not Skill existence or active-status authority. Filesystem scanning provides inventory evidence; `.agents/skills/skill_catalog.json` provides WHD classification. Only `canonical` entries are active WHD canonical Skills.

## User-invoked navigation

- **[ask-matt](./ask-matt/SKILL.md)**: Router over engineering/productivity flows.
- **[拷問邊建立文件](./拷問邊建立文件/SKILL.md)**: 深度質詢並同步維護 `CONTEXT.md` / ADR。
- **[triage](./triage/SKILL.md)**: Move issues through triage roles.
- **[掃描深模組](./掃描深模組/SKILL.md)**: WHD 深層架構掃描；使用者點名時讀此 Skill。
- **[驗證板件與DXF](./驗證板件與DXF/SKILL.md)**: 驗 current/resolved physical parts、DXF reopen、multipart、Save→Reload 與 remote QA。
- **[setup-matt-pocock-skills](./setup-matt-pocock-skills/SKILL.md)**: Upstream/reference setup material；classification 由 catalog 決定，不是 WHD governance owner。
- **[寫成規格書](./寫成規格書/SKILL.md)**: 從 grounded conversation/code/AI Library 產生工程規格。
- **[拆解任務工單](./拆解任務工單/SKILL.md)**: Requirement RED-first，經核准後拆 tracer-bullet tickets。
- **[執行開發任務](./執行開發任務/SKILL.md)**: 依核准 spec/ticket 實作，遵守 TDD、checkpoint、派工與 QA gate。
- **[寫技能](./寫技能/SKILL.md)**: 建立、修改、驗證與改善 Skill。
- **[派工](./派工/SKILL.md)**: WHD PM → Implementer → QA、owning Issue、journal/checkpoint、remote QA 狀態機。
- **[工作槽](./工作槽/SKILL.md)**: 固定 `/工作1`、`/工作2`、`/工作3` durable slots；裸指令只查狀態，明確 execution verb 才橋接派工/接手/續跑。
- **[wayfinder](./wayfinder/SKILL.md)**: Plan large multi-session work as decision tickets。

## Model- or user-reachable navigation

- **[prototype](./prototype/SKILL.md)**
- **[monitoring-remote-qa](./monitoring-remote-qa/SKILL.md)**
- **[executable-continuity-controller](./executable-continuity-controller/SKILL.md)**: durable state / resume / finalization controller；本 README 只提供 navigation，權威語意仍由該 Skill 與 executable controller 擁有。
- **[deterministic-repo-migration](./deterministic-repo-migration/SKILL.md)**: authority-driven repository migration；先 inventory，再 deterministic apply、strict validation、idempotence 與 drift audit，validator 不得成為 authority。
- **[long-log-context-safe-execution](./long-log-context-safe-execution/SKILL.md)**: 超長 pytest/Xvfb/remote CI 輸出的落檔、bounded tail、failure slice、cursor 與 Runtime-cut 續接規則。
- **[diagnosing-bugs](./diagnosing-bugs/SKILL.md)**
- **[research](./research/SKILL.md)**
- **[tdd](./tdd/SKILL.md)**
- **[Python測試實務](./Python測試實務/SKILL.md)**
- **[性質導向測試](./性質導向測試/SKILL.md)**
- **[尺寸語意分析](./尺寸語意分析/SKILL.md)**
- **[UI設計與去AI味](./UI設計與去AI味/SKILL.md)**
- **[領域建模](./領域建模/SKILL.md)**
- **[程式碼庫設計](./程式碼庫設計/SKILL.md)**
- **[code-review](./code-review/SKILL.md)**
- **[resolving-merge-conflicts](./resolving-merge-conflicts/SKILL.md)**
- **[wizard](./wizard/SKILL.md)**
- **[截角資料入口收斂](./截角資料入口收斂/SKILL.md)**
- **[issue-closure-gate](./issue-closure-gate/SKILL.md)**
- **[phase6-corner-3d-model-integrity](./phase6-corner-3d-model-integrity/SKILL.md)**
- **[phase6-release-packaging](./phase6-release-packaging/SKILL.md)**
- 其他 internal Phase6 Skills 即使本 navigation 未逐一列出，也不因此消失；以 filesystem inventory + catalog classification 判定。

## Canonical identity rule

中文 Skill 資料夾的 frontmatter `name` 必須與資料夾 basename 完全相同。舊英文 identity 只能作 migration/history；是否 active 仍由 `skill_catalog.json` classification 決定。
