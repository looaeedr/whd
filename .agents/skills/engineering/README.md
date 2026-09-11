# Engineering

Engineering skills used for code, design, QA, specs and delivery.

## User-invoked

Reachable when explicitly selected/invoked. Runtime-specific invocation controls may differ; the filesystem `SKILL.md` tree is the existence authority.

- **[ask-matt](./ask-matt/SKILL.md)**: Router over the engineering/productivity flows.
- **[拷問邊建立文件](./拷問邊建立文件/SKILL.md)**: 深度質詢並同步維護 `CONTEXT.md` / ADR。
- **[triage](./triage/SKILL.md)**: Move issues through triage roles.
- **[掃描深模組](./掃描深模組/SKILL.md)**: WHD 深層架構掃描；使用者點名時必須讀此 Skill，不用相似英文 Skill 取代。
- **[驗證板件與DXF](./驗證板件與DXF/SKILL.md)**: 驗 current/resolved physical parts、DXF reopen、multipart、Save→Reload 與 remote QA。
- **[setup-matt-pocock-skills](./setup-matt-pocock-skills/SKILL.md)**: Configure tracker/labels/domain-doc layout when applicable.
- **[寫成規格書](./寫成規格書/SKILL.md)**: 從 grounded conversation/code/AI Library 產生工程規格。
- **[拆解任務工單](./拆解任務工單/SKILL.md)**: Requirement RED-first，經使用者核准後拆 tracer-bullet tickets。
- **[執行開發任務](./執行開發任務/SKILL.md)**: 依核准 spec/ticket 實作，遵守 TDD、checkpoint、派工與 QA gate。
- **[寫技能](./寫技能/SKILL.md)**: 建立、修改、驗證與改善 Skill。
- **[派工](./派工/SKILL.md)**: WHD PM → Implementer → QA、owning Issue、journal/checkpoint、remote QA 狀態機。
- **[wayfinder](./wayfinder/SKILL.md)**: Plan very large multi-session work as decision tickets.

## Model- or user-reachable

- **[prototype](./prototype/SKILL.md)**: Build a throwaway prototype to answer a design question.
- **[monitoring-remote-qa](./monitoring-remote-qa/SKILL.md)**: 監控 GitHub Actions/remote QA 到 terminal，處理 cleanup/drift audit。
- **[diagnosing-bugs](./diagnosing-bugs/SKILL.md)**: Build a tight RED loop, minimise, hypothesise, instrument, fix and regress.
- **[research](./research/SKILL.md)**: Research against high-trust sources when its runtime requirements are available.
- **[tdd](./tdd/SKILL.md)**: RED → GREEN development at agreed seams.
- **[Python測試實務](./Python測試實務/SKILL.md)**: pytest fixture、isolation、parameterization、mock/monkeypatch、async、property-based、markers 與 CI 測試工程實務；不取代 tdd/diagnosing-bugs。
- **[性質導向測試](./性質導向測試/SKILL.md)**: 設計 property/invariant、generator strategy、shrinking/counterexample 分類；不取代 Python測試實務、tdd 或 debugging authority。
- **[尺寸語意分析](./尺寸語意分析/SKILL.md)**: 追蹤 WHD 料尺寸、包外、flat/formed、FW、T、datum 與 collision-envelope 的 semantic dimensions；只做分析/驗證，不建立 production 公式。
- **[UI設計與去AI味](./UI設計與去AI味/SKILL.md)**: UI visual design、資訊層級、existing-UI 去 AI 味 audit 與安全 rewrite；保留功能與 engineering semantics，不取代 domain/product authority。
- **[領域建模](./領域建模/SKILL.md)**: 定義/修正 domain terminology，維護 `CONTEXT.md` / ADR。
- **[程式碼庫設計](./程式碼庫設計/SKILL.md)**: Deep-module vocabulary：module/interface/depth/seam/adapter/leverage/locality。
- **[code-review](./code-review/SKILL.md)**: Review diff against standards and originating spec.
- **[resolving-merge-conflicts](./resolving-merge-conflicts/SKILL.md)**: Resolve merge/rebase conflicts by intent.
- **[wizard](./wizard/SKILL.md)**: Generate guided human-only operational steps when appropriate.

## Canonical identity rule

對任何**中文命名的 Skill 資料夾**，frontmatter `name` 必須與該資料夾 basename 完全相同。README 連結也必須指向實際中文路徑；舊英文 identity 只能做 legacy/history 說明，不能當 canonical routing target。