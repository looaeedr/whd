---
whd_doc_role: HISTORICAL
whd_contract: design-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# WHD AI 庫與文件權威整理規格書

**規格代號：** Knowledge & Documentation Consolidation  
**狀態：** Approved  
**目標分支：** `cleanup/2d-3d-sync`  
**規格日期：** 2026-09-14  
**規格版本：** v1.1 — Approved with governance hardening  
**核准補充：** YAML metadata schema、T0 early drift guard、MIRROR pointer-only template

---

## 1. 背景

WHD 專案目前已累積：

- `AGENTS.md`
- `.agents/skills/**`
- `.agents/skills/skill_registry.json`
- `.agents/skills/skill_catalog.json`
- `個人AI檔案庫/**`
- `docs/superpowers/**`
- 各類踩坑庫、SOP、spec、plan、verification、checkpoint
- executable process guard，例如 `tools/continuity_controller.py`

這些資料是在不同階段逐步建立，部分舊文件雖仍有歷史與事故證據價值，但其規則已被新的 canonical authority 取代。

目前已出現以下風險：

1. 同一規則分散在多份文件中。
2. 舊文件仍使用 CURRENT／永久規則語氣。
3. README、Skill navigation 與 machine registry 不同步。
4. 工單期間的 T1/T8、本輪驗收說明混入永久 Authority Map。
5. 文件 marker 被誤認成 executable enforcement。
6. 歷史文件名稱包含 `CURRENT`，但實際已是 HISTORICAL。
7. 後續 AI 可能因讀取順序不同而得到不同規則。

本輪必須把「現行規則」、「參考資料」、「相容入口」、「歷史證據」正式拆開。

---

## 2. 核心目標

### 2.0 結構化文件 metadata（WHD_DOC_META_V1）

為避免 R1-R7 依賴正則表達式或自然語言猜測文件角色，本工單建立統一 YAML Frontmatter schema。凡屬本規格治理範圍、會參與 current routing / preflight / canonical authority / mirror / historical isolation 的 Markdown 文件，最終都必須使用下列 machine-readable metadata：

```yaml
---
whd_doc_role: CURRENT          # CURRENT | REFERENCE | MIRROR | HISTORICAL
whd_contract: continuous-execution-machine
whd_canonical: null            # MIRROR 必填；其他角色預設 null
whd_schema: WHD_DOC_META_V1
---
```

欄位規則：

- `whd_schema`：固定為 `WHD_DOC_META_V1`。
- `whd_doc_role`：只允許 `CURRENT / REFERENCE / MIRROR / HISTORICAL`。
- `whd_contract`：穩定、kebab-case contract id；不得用 T-number、日期或 branch 名稱當 contract。
- `whd_canonical`：`MIRROR` 必須填 repo-relative canonical path；其他角色應為 `null`，除非未來 schema 明確擴充。
- 同一 `whd_contract` 必須恰有一個 `CURRENT`。
- YAML metadata 是結構化治理資料；正文仍可保留人類可讀 banner，但 machine guard 不得再以正文 marker 作主要 authority parser。
- Python、JSON、YAML 等非 Markdown executable/config authority 不強迫加入 Markdown frontmatter；它們由 Authority Map 以 path + contract 直接登記。

本 schema 的 rollout 採兩階段：

1. **Bootstrap mode（T0 起）**：新建或本工單修改到的 governed Markdown 必須立即有合法 metadata；既有未觸碰 legacy 文件先列 inventory debt，不因尚未遷移而全面阻塞。
2. **Strict mode（T6 完成後）**：所有納入 active knowledge inventory 的 governed Markdown 都必須有合法 metadata；缺失、未知角色、MIRROR 缺 canonical pointer 一律 fail closed。

本工單完成後，任何 AI、Agent 或人工維護者都必須能明確回答：

> 這個 contract 現在到底由哪一個檔案負責？

且同一 contract 不得存在兩份可被解讀為 CURRENT 的文件。

最終文件治理固定採四種角色：

### 2.1 CURRENT

唯一現行 authoritative owner。

同一個 contract：

> **只能存在一個 CURRENT。**

所有正式修改首先更新 CURRENT owner。

### 2.2 REFERENCE

只保存：

- 背景
- 解釋
- incident lesson
- 延伸說明
- historical context

不得覆蓋 CURRENT。

### 2.3 MIRROR

只提供：

- 舊入口相容
- 導覽
- pointer

必須是 pointer-only。

禁止複製整份 CURRENT prose 後自行演化。

### 2.4 HISTORICAL

保存：

- 舊 architecture
- 已完成工單
- 舊驗收結果
- migration evidence
- design provenance

不得再被 Preflight 或 runtime routing 當成現行規格。

---

## 3. 非目標

本工單不得：

1. 修改 WHD production geometry。
2. 修改 DXF 計算。
3. 修改 UI 功能。
4. 修改 Save/Reload contract。
5. 修改 receiving/divider/corner 等機械規格。
6. 因整理方便而刪除有 provenance 價值的 plan / verification / checkpoint。
7. 因檔名看起來舊就直接刪檔。
8. 大量重新命名中文檔案。
9. 把 AI 庫內容重新全部複製到另一套新文件系統。
10. 建立第二份 Authority Map。

本工單只處理：

> **Knowledge authority、documentation classification、navigation、routing 與 anti-drift guard。**

---

## 4. Authority hierarchy

整理完成後，WHD process / knowledge authority 順序固定如下：

```text
Executable truth / production behavior
        ↓
Canonical CURRENT domain owner
        ↓
AGENTS.md / Skill routing
        ↓
Required Skill
        ↓
Required CURRENT references
        ↓
REFERENCE / pitfall
        ↓
HISTORICAL evidence
```

其中：

```text
文件描述 ≠ executable enforcement
```

只要某條規則存在可執行 guard，其 executable implementation 才是 machine enforcement authority。

例如 continuous execution：

```text
tools/continuity_controller.py
        ↓
executable-continuity-controller/SKILL.md
        ↓
AGENTS / execution / remote-QA / closure bridge
        ↓
pitfall / historical explanation
```

不得再反過來由 Markdown marker 宣稱 machine state 已被鎖定。

---

## 5. Continuous Execution 文件收斂

### 5.1 Current executable authority

continuous-execution machine authority 固定為：

```text
tools/continuity_controller.py
```

操作 contract 固定為：

```text
.agents/skills/engineering/executable-continuity-controller/SKILL.md
```

### 5.2 舊 continuous execution pitfall

目前：

```text
個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md
```

仍包含舊時代文字，例如：

- marker 即 machine guard
- Skill gate 即 executable lock
- WAITING 字樣本身具有過高 authority
- documentation guard 被描述成「鎖定」

整理後此文件必須：

1. 保留原事故歷史。
2. 降級為 `REFERENCE`。
3. 在檔頭加入 supersession 說明。
4. 明確 pointer 到：
   - `tools/continuity_controller.py`
   - `executable-continuity-controller/SKILL.md`
5. 移除或改寫會讓人誤解為 CURRENT machine authority 的文字。
6. 不得再建立第二套 execution state machine。

### 5.3 新 controller pitfall

```text
個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
```

保留為 controller 事故與原則 REFERENCE。

但它不是 machine authority。

Machine authority 仍然只能是：

```text
tools/continuity_controller.py
```

---

## 6. AGENTS.md 收斂

`AGENTS.md` 保持：

```text
contract=agent-startup-process
role=CURRENT
```

但需補上 executable continuity bridge。

至少必須明確指出：

```text
非 terminal workflow
→ 必須使用 executable continuity controller
→ Markdown state 不得取代 checkpoint state
→ finalization 必須經 assert-finalizable
```

AGENTS 不得自己重新實作 controller state machine。

它只負責：

```text
startup
→ preflight
→ routing
→ mandatory bridge
```

---

## 7. Canonical Authority Map 整理

唯一 Authority Map 保持：

```text
個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md
```

其職責必須縮減為：

> 「contract → role → canonical path」

不得繼續累積：

- T1 執行紀錄
- T7/T8 工單文字
- 「本輪」
- 某次 Combined Acceptance 詳細結果
- 已完成 migration 過程
- ticket-specific 說明

這些應存在：

```text
docs/superpowers/plans/
docs/superpowers/verification/
GitHub Issue
Git history
```

Authority Map 只留永久狀態。

---

## 8. Authority Map 新增 process contracts

至少新增以下 contracts：

```text
continuous-execution-machine
continuous-execution-operations
remote-qa-monitoring
issue-closure
skill-routing
skill-classification
knowledge-preflight
pitfall-ledger
```

建議 canonical ownership：

```text
continuous-execution-machine
CURRENT
tools/continuity_controller.py

continuous-execution-operations
CURRENT
.agents/skills/engineering/executable-continuity-controller/SKILL.md

remote-qa-monitoring
CURRENT
.agents/skills/engineering/monitoring-remote-qa/SKILL.md

issue-closure
CURRENT
.agents/skills/engineering/issue-closure-gate/SKILL.md

skill-routing
CURRENT
.agents/skills/skill_registry.json

skill-classification
CURRENT
.agents/skills/skill_catalog.json

knowledge-preflight
CURRENT
AGENTS.md
```

不得因 README 或 pitfall 描述而建立平行 CURRENT。

---

## 9. 個人 AI 檔案庫 README 重整

目前 README 已兼具：

- 目錄
- current rule
- historical product notes
- platform guide
- release notes
- UI state
- architecture notes

責任過多。

整理後 `個人AI檔案庫/README.md` 只能負責：

### A. AI 庫用途

說明 AI Library 是什麼。

### B. 目錄導航

反映實際目錄：

```text
第一層_核心檔案
第二層_專案與SOP
踩坑庫
```

並列出目前實際存在的主要 canonical SOP。

### C. Authority 規則

明確指向：

```text
09_WHD_Canonical_Authority_Map.md
```

### D. 使用方式

說明：

```text
先找 Authority Map
→ 再讀 CURRENT owner
→ REFERENCE 僅補充
```

README 不再保存大量產品規格副本。

例如：

- UI 某日版面
- EndCap 當時 positioning
- 某日最新固化
- 舊 Assembly layout
- 舊 release 細節

若仍具價值，應由真正 domain CURRENT 或 HISTORICAL 文件保存。

---

## 10. 修正 README 的過時說法

以下過時摘要必須修正：

```text
Pre-Edit 備份
```

不得再讓人理解成「每次修改先建立 BACKUP」。

Current rule 應為：

```text
一般原始碼／文件修改：
Git branch / commit 為主要 rollback authority。

只有：
- 使用者明確要求
- Git 無法保存的外部資產
- 高風險 binary

才建立額外實體備份。
```

---

## 11. 第一層核心 AI 規則整理

`04_全域AI協作規則.md` 保持 REFERENCE，而不是 process CURRENT。

其角色：

```text
跨任務 AI 協作原則
```

不擁有：

- executable state
- domain geometry SSOT
- Skill routing
- remote QA machine state
- closure machine gate

所有這類段落必須 pointer 到 CURRENT owner。

---

## 12. Skill navigation 同步

目前 Skill filesystem / registry / README 必須保持一致。

當：

```text
skill_registry.json
```

已要求：

```text
executable-continuity-controller
```

則：

```text
.agents/skills/engineering/README.md
```

也必須列出此 Skill。

新增導航：

```text
executable-continuity-controller
```

說明至少包含：

> executable checkpoint / resume / finalization authority。

README 只是 navigation。

不得使 README 成為 Skill existence authority。

---

## 13. Skill registry 與 catalog 分工

兩者角色固定：

### skill_registry.json

負責：

```text
task / changed-file
→ required skill
→ required reference
```

### skill_catalog.json

負責：

```text
filesystem skill
→ canonical/reference/retired/tool-specific...
```

不得互相取代。

不得讓 README 成為 machine classification authority。

---

## 14. 歷史文件處理

以下類型原則上不得刪除：

```text
docs/superpowers/plans/**
docs/superpowers/verification/**
docs/superpowers/checkpoints/**
historical architecture snapshots
old acceptance evidence
```

因為仍有 provenance 價值。

但必須避免被誤讀為 CURRENT。

---

## 15. `CURRENT_*` 歷史文件問題

例如：

```text
docs/superpowers/CURRENT_API_INVENTORY_20260818.md
```

雖名稱含 CURRENT，但 Authority Map 已將其視為 HISTORICAL。

禁止為整理方便直接 rename，除非已確認所有 caller/reference。

最低要求：在檔首加入：

```text
[HISTORICAL / SUPERSEDED]

此文件中的 CURRENT 指 2026-08-18 snapshot，
不是目前 production authority。

Current authority 請讀：
<canonical pointer>
```

並加 machine guard，禁止它重新進入 CURRENT routing。

---

## 16. Pitfall Library 治理

踩坑庫角色固定為：

```text
REFERENCE / incident knowledge
```

踩坑庫可回答：

- 曾經錯過什麼？
- 為什麼會錯？
- 如何避免再犯？

踩坑庫不得回答：

> production 現在一定怎麼算。

若 pitfall 含 normative rule，必須 pointer 到真正 canonical owner。

---

## 17. 巨型 `06_踩坑記錄與防錯經驗庫.md`

此文件保持：

```text
REFERENCE
incident ledger
```

不得再新增完整 domain CURRENT 規格。

新增事故時：

```text
事件摘要
→ 根因
→ canonical rule pointer
→ regression pointer
```

即可。

完整規則必須寫入 focused owner。

---

## 18. Active / History 分離

每份被掃描到的 knowledge 文件都必須能歸入：

```text
CURRENT
REFERENCE
MIRROR
HISTORICAL
```

不得出現：

```text
UNKNOWN_ACTIVE
```

若檔案確實無法判定，整理工單必須先分析 caller / routing /內容後再分類，不能猜。

---

## 19. 禁止刪除規則

任何刪檔前必須證明：

```text
1. 不再被 registry 引用
2. 不再被 AGENTS 引用
3. 不再被 canonical owner 引用
4. 不再被 permanent test 引用
5. 不具有唯一 provenance
6. 已有正式 replacement
```

缺任一項：

> 不得刪除。

可改成 HISTORICAL / pointer。

---

## 20. Anti-duplication machine guard

必須新增永久 regression，至少驗：

### R1 — single CURRENT

同一 contract：

```text
CURRENT count == 1
```

### R2 — MIRROR pointer-only

所有 MIRROR 必須：

```text
canonical=<path>
```

且不得複製 canonical 大段 normative prose。

### R3 — historical cannot route

HISTORICAL 文件不得被：

```text
skill_registry required_references
AGENTS mandatory CURRENT route
canonical authority
```

直接當作 current requirement。

特殊 history/evidence 任務除外，但必須明確以 historical intent route。

### R4 — README cannot own contract

AI Library README、engineering README 只能 navigation。

不得宣告成 domain CURRENT。

### R5 — executable authority

continuous execution machine authority 必須唯一指向：

```text
tools/continuity_controller.py
```

不得退化回 Markdown marker-only enforcement。

### R6 — registry/navigation coherence

registry 使用的 canonical Skill 必須：

- filesystem 存在
- catalog classification = canonical
- navigation 可找到

### R7 — obsolete wording scan

至少掃描：

```text
本輪
目前 T1
目前 T8
CURRENT_API
舊版最高權威
BACKUP 必須
marker 即 machine guard
```

不是見字就 fail。

測試必須確認其所在角色與語境：

- HISTORICAL 可存在；
- CURRENT normative 區不得存在過時語意。

---

## 21. Preflight 行為要求

整理後 Knowledge Preflight 必須：

1. 先經 registry 判定 Skill。
2. required reference 優先為 CURRENT owner。
3. pitfall 只作 REFERENCE。
4. 不因歷史文檔名稱含 `CURRENT` 就載入。
5. 不因 README 提到某規則就把 README 視為 SSOT。
6. continuous execution 任務必須 route 到 executable continuity Skill。
7. issue closure 必須要求 executable continuity gate。

---

## 22. T0 Early Drift Guard（併行開發防禦）

T0 Inventory Freeze 完成後，不得等到 T7 才第一次啟用治理防線。必須先建立 **bootstrap CI guard**，防止整理期間其他分支／PR 再引入新的無角色文件。

Bootstrap guard 至少檢查：

1. 新增的 governed Markdown 必須有合法 `WHD_DOC_META_V1` YAML frontmatter。
2. 本工單修改到的 governed Markdown 必須補齊合法 metadata。
3. `whd_doc_role=MIRROR` 必須有 `whd_canonical`，且 canonical path 存在。
4. 新增 `CURRENT` 時不得造成同 contract 第二個 CURRENT。
5. Bootstrap mode **不得因尚未遷移的 untouched legacy 文件而全庫 fail**；legacy debt 由 T0 inventory 明確列出並在 T6 前收斂。
6. T6 完成後切換 strict mode，從此任何 governed Markdown 缺 metadata 都 fail closed。

這個 early guard 的目的不是提前宣告整理完成，而是建立「**migration 期間只能減少 drift，不能新增 drift**」的單向門。

---

## 23. MIRROR 標準範本

MIRROR 只允許 pointer-only。YAML frontmatter 不計入正文行數，正文建議限制 **3～5 行**，禁止複製 canonical 規格段落。

標準範本：

```markdown
---
whd_doc_role: MIRROR
whd_contract: phase6-dimension-semantics
whd_canonical: 個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md
whd_schema: WHD_DOC_META_V1
---
# Phase6 尺寸語意（Mirror）
> Canonical: `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`
> 本檔僅為相容入口；不得新增或複製 normative 規則。
```

永久限制：

- MIRROR 正文不得重新敘述 CURRENT requirement。
- MIRROR 不得出現「最高權威」「目前正式規格」等自我宣告。
- 修改規則只能修改 canonical owner；MIRROR 只在 canonical path 變更時更新 pointer。
- Machine guard 應驗 metadata + pointer-only size/structure，不以語意相似度猜測為主要判定。

---

## 24. 建議整理順序

實作順序固定：

```text
T0 Inventory Freeze + Bootstrap CI Guard
↓
T1 Authority Classification
↓
T2 Continuous Execution Consolidation
↓
T3 AGENTS / Skill Routing Alignment
↓
T4 AI Library README / Core Rules Cleanup
↓
T5 Authority Map Normalization
↓
T6 Historical / Mirror Labelling + Strict Metadata Mode
↓
T7 Permanent Machine Guards
↓
T8 Combined Acceptance
↓
T9 Production Integration
```

不得一開始就大批刪文件。

---

## 25. T0 — Inventory Freeze

建立完整 inventory：

至少涵蓋：

```text
AGENTS.md
README.md
AI_HANDOFF.md
個人AI檔案庫/**
.agents/skills/**
docs/superpowers/**
handoff/**
```

記錄：

```text
path
role
contract
metadata status
canonical owner
incoming references
machine routing
replacement
action
```

T0 同票必須交付 bootstrap metadata/authority CI guard；從此新建或本輪修改的 governed Markdown 不得再以 `UNKNOWN_ACTIVE` / 無 `WHD_DOC_META_V1` 狀態進入 branch。

Action 只能為：

```text
KEEP
UPDATE
REFERENCE
MIRROR
HISTORICAL
DELETE_CANDIDATE
```

---

## 26. T1 — Authority Classification

所有 active knowledge contract 必須分類。

重點 audit：

```text
continuous execution
remote QA
issue closure
skill routing
skill authoring
knowledge preflight
manufacturing architecture
dimension semantics
navigation
UI
DXF
project persistence
```

若同 contract 出現兩個 CURRENT：

> Gate RED。

先解 authority，再做內容整理。

---

## 27. T2 — Continuous Execution Consolidation

完成：

- controller 唯一 executable authority
- legacy pitfall 降 REFERENCE
- stale marker authority 移除
- bridge 修正
- finalization machine gate pointer

不得重新設計 controller。

---

## 28. T3 — AGENTS / Skill Routing Alignment

同步：

```text
AGENTS.md
skill_registry.json
skill_catalog.json
engineering/README.md
```

要求 machine route 與人工 navigation 一致。

---

## 29. T4 — AI Library Cleanup

重整：

```text
個人AI檔案庫/README.md
第一層_核心檔案/04_全域AI協作規則.md
第二層 SOP navigation
踩坑庫 role
```

重點是去除重複 CURRENT prose。

---

## 30. T5 — Authority Map Normalization

Authority Map 移除 ticket-era narrative。

保留：

```text
contract
role
path
canonical
short purpose
```

過去 T1/T8 acceptance 移至 history/provenance，不再混入 map 的 normative body。

---

## 31. T6 — Historical / Mirror Labelling

對容易誤讀文件加：

```text
WHD_DOC_ROLE
```

或等價 machine-readable metadata。

至少覆蓋：

```text
CURRENT_API_INVENTORY_20260818.md
舊 handoff architecture
舊 current/history snapshots
duplicate mirrors
```

T6 完成時必須把 governed Markdown 從 bootstrap mode 切到 strict metadata mode；所有 MIRROR 必須符合本規格第 23 節 pointer-only 範本，所有 active inventory 文件不得再留無角色 metadata debt。

---

## 32. T7 — Permanent Machine Guards

新增永久 knowledge regression。

不得只做：

```python
assert "某字串" in file
```

必須實際解析：

```text
contract
role
canonical
route
classification
```

並驗：

```text
yaml-metadata-schema
single-current
no-current-from-history
mirror-pointer-only
registry/catalog coherence
controller authority
bootstrap-to-strict-mode
```

---

## 33. T8 — Combined Acceptance

同一 tested HEAD 至少驗：

```text
authority contracts
skill registry
skill catalog
preflight
continuous execution controller
issue closure
history/current isolation
AI Library navigation
config invariant
protected baseline invariant
```

要求：

```text
0 FAIL
0 authority ambiguity
0 dual CURRENT
0 orphan canonical Skill
0 unintended production behavior change
```

---

## 34. T9 — Integration

完成所有驗收後：

1. 刪除 temporary QA workflow。
2. tested → cleaned drift audit。
3. production refetch。
4. 確認 production 無 concurrent drift。
5. non-force integration。
6. exact-production post-integration verification。
7. remote cleanup。
8. final authority inventory。
9. 關 Master。

禁止 force update production。

---

## 35. Branch 規則

所有修改必須從當下：

```text
cleanup/2d-3d-sync
```

建立 fresh work-order branch。

禁止直接修改 production。

若拆多張工單：

```text
production
→ work-order branch
   → T1
   → T2
   → ...
   → Combined
→ production
```

後續 ticket 必須沿 accepted work-order lineage。

---

## 36. 測試不可成為規格來源

Knowledge tests 只能驗：

```text
authority 是否符合規格
```

不得反過來：

```text
因測試目前寫 A
→ 所以 A 就是 canonical rule
```

validation 不得成為 production / documentation truth source。

---

## 37. 驗收標準

本工單只有在以下全部成立才可 ACCEPT：

- [ ] 所有 active contract 都有唯一 CURRENT owner。
- [ ] `09_WHD_Canonical_Authority_Map.md` 不再包含工單期「本輪/T1/T8」current narrative。
- [ ] continuous execution machine authority 唯一為 `tools/continuity_controller.py`。
- [ ] legacy continuous execution pitfall 已降 REFERENCE。
- [ ] `AGENTS.md` 已 bridge executable controller。
- [ ] AI Library README 已反映實際結構。
- [ ] README 不再宣稱一般修改要 Pre-Edit BACKUP。
- [ ] engineering README 可找到 executable continuity Skill。
- [ ] registry / catalog / filesystem / navigation 一致。
- [ ] HISTORICAL 文件無法被當 current routing owner。
- [ ] `CURRENT_API_INVENTORY_20260818.md` 已有 HISTORICAL 防誤讀標記。
- [ ] pitfall library 明確為 REFERENCE。
- [ ] 所有 governed Markdown 已符合 `WHD_DOC_META_V1`；無 metadata debt。
- [ ] T0 bootstrap CI guard 已生效，且 T6 後已切 strict mode。
- [ ] 所有 MIRROR 符合 pointer-only 3～5 行正文範本。
- [ ] 無 dual CURRENT。
- [ ] 無 orphan CURRENT。
- [ ] permanent anti-drift tests GREEN。
- [ ] `config.ini` 前後 SHA256 完全相同。
- [ ] `基準檔/**` protected manifest 完全相同。
- [ ] 沒有 temporary QA workflow 留在 production。
- [ ] exact-production post-integration verification GREEN。

---

## 38. 最終預期狀態

整理完成後，一個新的 AI 進入 WHD 專案時，不應再需要：

> 「把全部 Markdown 都讀一遍，自己猜哪一份比較新。」

而應該變成：

```text
AGENTS
  ↓
Preflight
  ↓
Authority Map / Registry
  ↓
唯一 CURRENT
  ↓
必要 REFERENCE
```

文件數量可以多。

**權威只能有一個。**

歷史可以完整保存。

**歷史不能偽裝成 CURRENT。**

踩坑可以一直累積。

**踩坑不能變成第二份規格。**

README 可以方便閱讀。

**README 不能成為 Source of Truth。**

Skill 可以描述操作方式。

**真正 machine enforcement 必須由 executable guard 負責。**

這就是本次 AI 庫與文件整理的完成定義。
