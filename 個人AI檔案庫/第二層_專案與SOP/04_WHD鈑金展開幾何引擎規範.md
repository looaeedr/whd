---
whd_doc_role: CURRENT
whd_contract: manufacturing-architecture
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# 🔩 04. WHD 鈑金展開幾何引擎規範（ae_engine）

> 本文件的 CURRENT 區只描述 **現行 ae_engine 製造架構、公開 API 與 authority boundary**。實際 Corner/Relief 製造公式仍由 Certified Registry 與其 canonical references 擁有；本文件不得複製一套第二公式來源。

## [CURRENT] Joint Placement MARKING ownership contract

Joint Placement MARKING 的 production authority 必須沿 physical mating-region/contact ownership 傳遞，不得由 renderer、UI、fixture 或量測差值反推。Inner Door Frame 的接合端由 authoritative `LOWER_TERMINAL_FACE` 提供 mating-region；Receiving 的 shared horizontal Divider 以 `CORE_PHYSICAL_SEGMENT` 的 physical skin 作接觸面。合法接觸使用 contact-local boundary frame 與 locator-only backprojection；工程 coplanar tolerance 屬幾何判定 authority，不得為了讓 fixture 通過而放寬。

Joint marking policy/diagnostics 由 engine registry/orchestration 擁有；production activation 的已核准 disposition 是 `ALLOW_EXPORT_WITH_DIAGNOSTIC`。Gate A 可保留 dormant foundation，但 Receiving Gate B 只有在 product disposition 已解決後才能啟用。2D、3D、DXF 與 Save→Reload 必須消費同一份 enriched manufacturing geometry/result，不得各自建立第二套 marking 幾何或 placement 規則。

Validation 維持單向：contact probe、collision、fixture expected、pytest tolerance、rendered result 與 QA artifact 只能驗證上述 authority，不得成為 production formula、offset、placement 或 marking policy 的來源。

## [CURRENT] ae_engine Manufacturing / Certified Registry Contract

<!-- WHD_AUTHORITY_ROLE: CURRENT -->

### 1. Current scope 與 Source of Truth 邊界

現行 repository-relative engine path 是：

`ae_engine/`

本文件不再用任何本機磁碟路徑當 current architecture locator。正式 source 一律以 repository path、current production code、Certified Registry 與 canonical AI Library / Registry references 為準。

現行 authority 分工：

1. 使用者已核准的產品／機械需求：最高 requirement authority。
2. `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`：尺寸語意、STANDARD 與 assembly semantic delta 的 CURRENT domain authority。
3. `基準檔/截角資料庫/certified_relief_rules.json` + `README_母規則說明.md`：已認證 Corner/Relief runtime formula、revision、precondition、dimension-space 與 certification metadata authority。
4. `ae_engine/`：把 Cabinet Family、Topology、canonical parameters、Registry result 與 final manufacturing geometry 串成 production data flow。
5. tests / fixture / probe / collision shadow / rendered result：只做 validation，不建立新的製造 Source of Truth。

因此 04 的責任是回答「engine 現在怎麼分層、公開哪些 API、各 authority 怎麼接起來」，不是把 Registry JSON 內容重新抄一份。

### 2. Current manufacturing data flow

```text
operator / project canonical state
        ↓
Cabinet Family + physical-part Topology
        ↓
canonical parameters / Fold / Assembly Intent
        ↓
ManufacturingPolicy + ManufacturingContext / PartSpec
        ↓
Certified Registry lookup / family policy resolution
        ↓
resolved canonical manufacturing answer
        ↓
Final Material + BEND + features + stable physical-part output
        ↓
2D / single-part 3D / assembly 3D / DXF / Save→Reload
```

硬規則：

- 2D、3D、DXF、Save→Reload 不得各自重算第二份製造幾何。
- Cabinet Family 決定 family-specific policy；Topology 決定實體板件與折法。兩者不能互相冒充。
- physical-part identity、Fold、feature、relief 與 persistence 必須沿 authoritative manufacturing state 傳遞，不能由 UI label / renderer / test expected 反推。
- `canonical parameters` 必須有獨立來源，例如 project state、Family/Topology policy、Certified Registry、authoritative T、approved DXF datum/feature；不得來自單次驗收差值。

### 3. `ae_engine.__init__` current public surface

Current public surface 以 `ae_engine/__init__.py` 實際 export 為準。若 public export 改變，應同步更新本 CURRENT contract 與永久 guard；不得讓文件繼續描述不存在的舊 API。

### 4. Certified Registry 是已知 Relief 的 production authority

Registry HIT = canonical manufacturing answer；3D collision/backprojection 只做 shadow validation，不得覆蓋 Certified answer。Registry MISS 才可進 discovery/candidate；candidate 未經正式 promotion 不得成為 Certified truth。Ambiguity/conflict 必須 fail closed。

### 5. Validation is one-way

expected value、fixture、probe、tolerance、collision 與 QA artifact 都只屬 validation evidence，不得回灌 production formula、offset、compensation、branch selection 或 placement。

### 6. Current references

修改 ae_engine / Registry / Corner / Relief 前，至少交叉讀：

- `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`
- `基準檔/截角資料庫/README_母規則說明.md`
- `基準檔/截角資料庫/certified_relief_rules.json`
- `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`
- `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`

Preflight / test evidence 只能證明這些 authority 被遵守，不能反過來成為製造公式來源。
