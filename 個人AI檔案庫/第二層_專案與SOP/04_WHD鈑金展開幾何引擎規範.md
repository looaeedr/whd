# 🔩 04. WHD 鈑金展開幾何引擎規範（ae_engine）

> 本文件的 CURRENT 區只描述 **現行 ae_engine 製造架構、公開 API 與 authority boundary**。實際 Corner/Relief 製造公式仍由 Certified Registry 與其 canonical references 擁有；本文件不得複製一套第二公式來源。

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

Current public surface 以 `ae_engine/__init__.py` 實際 export 為準。04 至少必須跟上以下 Registry / manufacturing contract API：

- `ManufacturingPolicy`
- `ManufacturingContext`
- `PartSpec`
- `DoorPartSpec`
- `BoxBodyPartSpec`
- `EndCapPartSpec`
- `BasePlatePartSpec`
- `IndicatorBoxPartSpec`
- `PartExportResult`
- `generate_part`
- `resolve_policy`
- `expected_baseline_path_for`
- `CabinetTypeRegistration`
- `registered_cabinet_types`
- `resolve_cabinet_type`
- `CertifiedReliefStatus`
- `CertifiedReliefRule`
- `CertifiedReliefResult`
- `CertifiedCornerPolicyRule`
- `CertifiedReliefRegistryError`
- `CertifiedReliefRegistryAmbiguityError`
- `registered_certified_relief_rules`
- `registered_certified_corner_policy_rules`
- `lookup_certified_endcap_relief`
- `lookup_certified_corner_state`
- `certified_corner_policy_for_part`
- `certified_rule_revision_exists`
- `build_relief_promotion_candidate`

若 public export 改變，應同步更新本 CURRENT contract 與永久 guard；不得讓文件繼續描述不存在的舊 API。

### 4. Certified Registry 是已知 Relief 的 production authority

#### 4.1 Registry HIT

**Registry HIT = canonical manufacturing answer。**

當 `CertifiedReliefRule` / `CertifiedCornerPolicyRule` 命中，production 使用該 rule 的 formula、preconditions、`rule_id`、`revision`、`trust_level`、`standard_ref`、`dimension_space`、target semantics 與 canonical parameters 產生製造結果。

對 Registry HIT：

- 3D collision / backprojection 只能做 **3D shadow validation**；
- shadow result 可以指出 conflict，但**不得覆蓋**已認證答案；
- current code 不得另寫第二套相同 Corner/Relief 公式；
- fallback 開關不得跳過 Certified lookup。

#### 4.2 Registry MISS

只有 **Registry MISS** 才可進未知 geometry 的 3D `discovery` / candidate flow。

MISS 不代表「任意量 collision bbox 就直接製造」。candidate 必須保持可追溯來源，並經正式 promotion / regression / human-approved authority 後才能成為 Certified rule。

`PROVISIONAL_3D` 不是 Certified production truth；只有符合 registry promotion contract 的結果才可能進 `CERTIFIED_FROM_3D` 或其他正式 Certified 狀態。

#### 4.3 Ambiguity / conflict

多條同等優先規則競爭時必須回報 `REGISTRY_AMBIGUOUS` / `CertifiedReliefRegistryAmbiguityError` 並 **fail closed**；禁止靠 list order、第一筆 match、UI 順序或舊 cache 猜答案。

Registry / engine conflict 同樣只能阻擋或診斷，不能偷偷採用 validation output 當新的 production formula。

### 5. Registry record / canonical parameter contract

Current Certified record 至少要保持可解釋的製造 provenance，包括：

- `rule_id`
- `revision`
- `trust_level`
- Cabinet Family scope / part role / joint face / Assembly Intent 或 Corner domain
- Topology / preconditions
- formula / canonical parameters
- `standard_ref`
- `dimension_space`
- target semantics / adjustment type
- certification evidence
- geometry inputs

Fixture 的固定輸出可以出現在 certification evidence；它不能取代 formula / parameter provenance。

Receiving Divider 的 current 例子是既有 `CornerType=CROSS + 參數`；Registry HIT 後 3D 只做 shadow/penetration verification。不得因 schema 不方便另造 Divider CornerType 或偷換成 INSERT_OVERLAY。

### 6. Validation is one-way

**Validation is one-way：validation 可以判定 production 對不對，但不得回灌 production。**

下列全部只屬 validation evidence：

- pytest `expected value`
- fixture output / golden result
- collision / solver `probe`
- screenshot / rendered number
- bbox / measured delta
- assertion `tolerance` / epsilon / boolean fringe
- PASS / FAIL log

硬規則：

- expected value、fixture、probe、tolerance **不得回灌 production** formula、offset、compensation、branch selection 或 placement。
- 若 actual=A、expected=B，禁止把 `B-A` 寫成 magic compensation；必須回查 requirement → Family/Topology → canonical parameters → Registry / manufacturing derivation。
- tests、fixtures、QA artifact 不得被 production import/read 來決定製造答案。
- 只有具獨立 authoritative provenance 並正式進 canonical spec/state/Registry 的數值，production 才能使用。

### 7. 3D / collision 的 current role

3D 仍然重要，但角色必須依 HIT/MISS 分流：

- Registry HIT：3D = shadow validation / penetration check / conflict evidence。
- Registry MISS：3D 可以參與 discovery，產生 candidate，但 candidate 不是 Certified truth。
- promotion 後：runtime 回到 Registry formula；不得每次重新用 3D 發明已知答案。
- visibility / renderer 只影響顯示，不得改 mechanical authority 或 collision datum source。

因此「先碰撞、再決定所有正式 CUTTING」不是現行全域通則；它只可能是未知 geometry discovery 的一段流程。

### 8. Current references

修改 ae_engine / Registry / Corner / Relief 前，至少交叉讀：

- `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`
- `基準檔/截角資料庫/README_母規則說明.md`
- `基準檔/截角資料庫/certified_relief_rules.json`
- `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`
- `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`

Preflight / test evidence 只能證明這些 authority 被遵守，不能反過來成為製造公式來源。

---

## [HISTORICAL/SUPERSEDED] Legacy ae_engine notes

> **以下內容只保留歷史 provenance，不可作 CURRENT routing / runtime oracle。** 2026-09-13 起，若本區與上方 CURRENT contract、AI 07 或 Certified Registry 衝突，一律以上方 CURRENT authority chain 為準。

### Historical local workspace locator

早期文件曾以本機路徑定位程式：

- `Z:\Ollama-整合whd\ae_engine\`
- `Z:\whd-corner-new-engine-implemented\`

這些只代表當時開發機 workspace，已 **SUPERSEDED**；current locator 是 repo-relative `ae_engine/`。

### Historical Layer A / B / C 架構描述

早期曾把系統簡化成：

```text
Layer A = 純 2D Geometry
Layer B = 舊 ae / DXF 轉接
Layer C = GUI / 拆圖
```

並以 `sheetmetal_geometry.py → ae.py → gui.py` 類型的三層鏈作主要 current architecture。這段在 Family、physical topology、Manufacturing API、Certified Registry、AssemblyJoint、shared 2D/3D manufacturing state 成形前有歷史價值，但已不足以描述現行系統，故不得繼續作 current architecture authority。

### Historical collision-first relief direction

早期 04 曾把 BoxBody / EndCap assembly relief 固化成：

> **先形成名義板件與折後實體，再由實際干涉反推 2D CUTTING**。

當時流程大意是：nominal part → collision region → ownership → 3D/2.5D backprojection → relief candidate → CUTTING → replay。

這段對「未知 geometry discovery」仍有歷史背景價值，但作為**全域 production rule 已 SUPERSEDED**：

- Registry HIT 時 Certified formula 已是 canonical manufacturing answer；3D 只能 shadow validate，不得覆寫。
- Registry MISS 才允許 discovery/candidate。
- candidate / measured collision result 不會因驗證通過自動升格成 Certified formula。

### Historical fixed-model / CornerType sediment

舊 04 曾逐次追加 C01/C02/C03/C04、INSERT/OVERLAY/INSERT_OVERLAY、WRAP、UI lock/unlock、assembly scene、placement、collision 等大量階段性規則。這些段落的單次數值或當時 UI 結構都只應視為歷史演進證據。

Current 製造語意應回到：

- AI 07 的尺寸語意 / STANDARD / semantic delta；
- current Cabinet Family + Topology；
- Certified Registry 的 active rule / revision / canonical parameters；
- current production API；
- validation one-way boundary。

不得因舊文件曾記錄某個 fixture、probe 或碰撞量測，就把該數字重新寫回 current production。
