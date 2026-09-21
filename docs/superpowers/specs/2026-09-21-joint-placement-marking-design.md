---
whd_doc_role: CURRENT
whd_contract: assembly-joint-placement-marking
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 板件接合定位打標（Joint Placement MARKING）設計規格 v1.3

- **日期**：2026-09-21
- **狀態**：CURRENT／正式重寫版
- **Canonical repo path**：`docs/superpowers/specs/2026-09-21-joint-placement-marking-design.md`
- **取代**：同一路徑先前 v1.2 內容，以及未經 Skill gate 產生的 v1.3 PRE-GATE draft
- **適用範圍**：WHD Phase6 physical parts、assembly placement、FinalScene、2D、DXF；首個啟用案例為 Receiving inner-door left/right frame → shared horizontal Divider
- **實作可開始**：可以。幾何、policy、diagnostic、report 與 DXF parity 可施工；但「marking failure 是否阻斷原本可輸出的 DXF」仍為獨立產品決策，見 **OPEN-1 / ED-1**，不得由實作者自行選預設。

---

## Problem Statement

WHD 需要在實際承接／定位母板上產生**製造用打標線**，讓現場可直接依雷射淺刻位置放置、貼合、焊接或定位另一片鈑件。

這不是 UI 輔助線，也不是用 bbox、中心點、世界座標常數或畫面方向猜出的定位線。打標必須由 authoritative physical parts、assembly placement 與真實 legal contact 推導，最後寫入同一份 canonical `FinalScene` 的既有 `MARKING` layer，讓 2D 與 DXF 消費同一份結果。

v1.2 已確認核心產品意圖可進實作，但 review 指出四類實作前歧義：

1. contact-local frame 的 `L / C` 正負與 mirror/rotation 穩定性沒有完整定義；
2. `boundary_frame_contract` 曾出現在 policy schema，卻沒有完整正文 contract；
3. review 補強曾被錯標為 `CONFIRMED PRODUCT RULE`，尤其「marking failure 不阻斷 export」並未取得產品授權；
4. 只把 failure 放 metadata 會造成現場收到「少線 DXF」卻無法分辨是「本來無 policy」還是「應有 marking 但 fail-closed」。

本 v1.3 將這些問題正式收斂，並重新依 current repository、AI Library、既有 spec、tests 與 certified/reference data grounding。

---

## Confirmed Product Rules

> 本節只保留使用者已確認或由既有 authoritative product/manufacturing rule 支撐的產品行為。review hardening、implementation choice、tolerance 與 diagnostic schema 不在此冒充產品授權。

### CPR-1 — `MARKING` 是製造資料，不是 UI 輔助線

接合定位打標必須使用既有製造 layer：

`MARKING`

不得改用：

- `CHECK`
- `BEND`
- `CUTTING`
- 新造 `JOINT_MARK`
- 新造 `SCRIBE`

`MARKING` 的加工層定義仍由 `加工層分類與定義.md` 擁有。

### CPR-2 — 打標 owner 預設是 locator / receiver 母板

定位線畫在**承接／定位母板（locator / receiver part）**上。

被放置的 attached part 不重複畫同一組定位線，除非未來有另一個明確產品 rule 要求雙邊標示。

### CPR-3 — 幾何來源必須是真實 assembly / contact

MARKING 不得由以下來源直接決定：

- part bbox / renderer bbox；
- world origin；
- 畫面像素；
- 固定 50 / 80 / 170 等 UI 或 fixture 數值；
- part name → hard-coded coordinate；
- pytest expected；
- collision probe delta；
- DXF verifier tolerance；
- 「看起來差不多」的中心線或平移量。

正式來源必須沿：

`physical part → authoritative placement → formed true-thickness geometry → legal mating/contact → locator flat backprojection`

正向求解。

### CPR-4 — 必須使用真板厚

contact 必須建立在 formed true-thickness physical geometry 上。

不得以 zero-thickness mid-surface 接觸後再用 magic `T` / `T/2` 偏移猜兩條定位線。

`T` 只能由 authoritative thickness 進入既有真板厚模型。

### CPR-5 — 預設 footprint mode 為兩側定位邊界

第一階段預設 footprint mode：

`SIDE_BOUNDARY_PAIR`

輸出兩條定位側界：

- `SIDE_NEGATIVE`
- `SIDE_POSITIVE`

產品意圖是標示 attached part 在 locator 上的兩側定位範圍。

對此 mode：

- 只輸出兩側 longitudinal boundary；
- 不畫短端封口；
- 不把它畫成 CUTTING box；
- 長度使用完整有效接合範圍；
- 若 footprint 無法唯一解析成此 mode，fail closed，不得硬近似。

`SIDE_NEGATIVE / SIDE_POSITIVE` 的**工程定向方法**由 EC-2 定義；role 名稱本身不表示 world-left/right。

### CPR-6 — 不是所有 Assembly contact 都自動打標

每一類接合必須有 explicit `JointMarkingPolicy`（名稱可在施工時等價實作），至少決定：

- 是否需要 marking；
- locator part / selector；
- attached part / selector；
- locator contact region；
- attached contact region；
- footprint mode；
- boundary frame contract；
- contact span contract。

沒有 policy 的普通 joint/contact：

- 不產生 marking；
- 不產生 `POLICY_NOT_FOUND` 雜訊；
- 不使用「有碰到就全部刻」的 heuristic。

### CPR-7 — 首個正式案例：Receiving inner door → shared horizontal Divider

Receiving 上方 inner door 的第一個正式打標案例：

- locator = 該 inner door 真正共用的 horizontal Divider physical part；
- attached = 該 inner door 的 `left_frame` 與 `right_frame`；
- 不建立 fictitious physical `bottom_frame`；
- 每支 frame 在 shared Divider 上輸出一組 `SIDE_BOUNDARY_PAIR`；
- 每組 2 條；
- 標準案例合計 4 條 locator-side `MARKING`；
- 實際座標不得寫死，必須跟 current topology / placement / contact 重算。

若 shared Divider identity 消失或變得不唯一，marking 必須 fail closed / 消失，不得黏在舊 stable ID。

### CPR-8 — 能力是 generic，不只做 Receiving 內門

核心 projection 能力不得寫成 Receiving-only 座標公式。

未來 top ↔ left/right frame、Divider ↔ 其他板件等接合，可以使用同一 marking pipeline，但只有在：

1. authoritative placement 存在；
2. legal contact 可唯一解析；
3. policy 明確指定 locator / attached / regions / footprint mode；

三者都成立時才啟用。

### CPR-9 — FinalScene 是 2D / DXF 的共同製造來源

marking 必須在 manufacturing owner 產生，寫入 locator 的 canonical `PartRenderData.scene` / FinalScene。

DXF serializer 不得含 joint-specific 幾何公式。

2D manufacturing preview 與 DXF 必須讀同一份 `MARKING` primitives。

3D 若未來顯示刻線，只能 presentation 同一份 marking，不得反過來成為 manufacturing geometry authority。

### CPR-10 — derived marking 座標不是 project truth

Project Save 保存：

- authoritative topology；
- stable part identities；
- assembly / placement state；
- marking policy selection / revision（若為 persistent product state）。

不得把每條 derived marking XY 另存成第二份 Source of Truth。

Reload 後必須重新 canonical resolve，得到等價 marking identity 與 geometry。

### CPR-11 — fail-closed：不能猜線

下列情況不得產生猜測 MARKING：

- locator 不存在；
- attached 不存在；
- stable identity stale；
- placement 無法解析；
- legal contact 找不到；
- contact 不唯一；
- contact 其實是 penetration；
- boundary frame 無法建立；
- footprint mode 不匹配；
- world→flat backprojection 失敗；
- mark 超出 locator Final Material；
- 只能取得 bbox / centerline / renderer evidence。

failure 的**export disposition**不在本條決定；見 OPEN-1 / ED-1。

### CPR-6B — SUPERSEDED / RECLASSIFIED

v1.2 曾將「marking failure 不阻斷既有 DXF export」寫成產品規則。

本 v1.3 **撤銷其 CONFIRMED PRODUCT RULE 身分**。

正確分類：

- 「不猜 marking、不改 CUTTING/BEND/holes/relief/final material、一定回報 failure」＝已確認工程安全行為；
- 「failure 時 DXF 還能不能輸出」＝**OPEN PRODUCT DECISION**。

### CPR-4A / CPR-6A / CPR-6C — RECLASSIFIED

v1.2 review hardening 中的：

- legal-contact 細部判定式；
- boundary role 的 deterministic frame；
- 無 authority 時 overlap 預設 NONE；

全部改列 **Engineering Contracts**，不得再標成使用者產品授權。

---

## Current State / RED Evidence

### CS-1 — `MARKING` layer 與 primitive / DXF sink 已存在

Current code 已有：

- `DrawingScene.add_line(... layer="MARKING")`
- `DrawingScene.add_polyline(... layer="MARKING")`
- `DrawingScene.add_circle(... layer="MARKING")`
- `MARKING` color 211
- DXF layer `MARKING`
- `_add_drawing_scene_to_dxf()` 直接 serialize DrawingScene primitives

因此本功能不是「新增 DXF layer」，而是新增**marking geometry resolver**。

### CS-2 — canonical export 已能直接消費 `PartRenderData.scene`

`save_part_render_data_dxf()` 的 current contract 是：

> serialize already-built authoritative FinalScene，不重建 PartSpec geometry。

`save_resolved_manufacturing_geometry_dxf()` 逐 physical part 直接把 canonical `render_data` 送進同一 sink。

因此 joint marking 的正確 seam 在 **Resolved Manufacturing / PartRenderData 形成階段**，不是 serializer。

### CS-3 — Receiving shared lower frame 已有 authoritative stable identity

Current Receiving topology 已證明：

- `left_frame` / `right_frame` 是 physical parts；
- upper inner door 可只包含 `top / left / right` physical frames；
- horizontal Divider 是 box-body-owned physical part；
- `resolve_inner_door_lower_frame_role()` 會指向 exact Divider stable ID；
- `resolve_inner_door_lower_frame_placement()` 的 `bottom_frame` 是 shared-role/placement handle，`mate_target` 指向 Divider；
- current test 明確要求「沒有獨立 bottom-frame physical part」。

所以 marking owner 必須是 Divider，不可為了打標再造一片 bottom frame。

### CS-4 — current placement 已是 authoritative assembly data

`ae_engine/assembly_placement.py` 明確定義：

- placement 是 assembly data，不是 GUI state；
- unsupported / ambiguous stable identity fail closed；
- Divider placement 由 Door topology + FW formed-face relation解析；
- 2D receiving overlay 已有 test 防止回到 local 50px offset。

marking 必須消費同一 placement resolver，不得再建第二套 offset。

### CS-5 — current geometry 已有 flat↔world provenance，但 legal coplanar contact resolver 尚未存在

Current geometry 已有：

- `folded_mesh_with_flat_uv_from_polygon()`
- `MappedSkinTriangle(flat, world, side)`
- `world_skin_with_flat_uv()`
- barycentric world→flat mapping
- true-thickness sheet construction

Current collision path主要處理 non-coplanar crossing / penetration，且明確忽略 coplanar mating contact。

**RED gap：**

Joint Placement Marking 需要的是**coplanar legal contact area / boundary overlap**，不是 current penetration segment。

因此不得直接把 `detect_world_mesh_surface_interference()` 或 collision backprojection 的 crossing segment 當 marking footprint。

### CS-6 — frame terminal contact涉及 true-solid boundary wall

Receiving left/right frame 的 longitudinal material axis是 blank `Y = frame.span`。

其下端與 horizontal Divider 的接觸是**terminal/end contact**；在 true-thickness solid 中，attached contact face來自材料邊界 side wall，而不是單純 mid-surface skin。

Current `MappedSkinTriangle` 對 mid-surface ±T/2 skins 保留 flat UV；`thicken_triangle_surface()` 雖建立 boundary side walls，但目前沒有 generic「mapped physical contact face」contract。

**RED gap：**

marking resolver 需要 neutral physical-face/contact seam，不能假設「所有 contact 都是兩張 mapped skin triangle 直接重疊」。

第一階段只需要 locator Divider contact skin具 flat mapping；attached end wall可以提供 world-space physical face。未來若 locator 本身是 boundary wall，需擴充 mapped physical face能力後才啟用。

### CS-7 — tolerance 尚未有單一 geometry-neutral owner

Current production geometry存在多個 numerical defaults，例如：

- `thicken_triangle_surface(... tolerance=1e-7)`
- `detect_world_mesh_surface_interference(... tolerance=1e-6)`
- assembly collision / backprojection 多處 `1e-6`

這些是 **CURRENT IMPLEMENTATION / consolidation debt**，不是已存在的 canonical single owner。

DXF verifier：

`verify_saved_part_render_data_dxf(... coordinate_tolerance=1e-6, area_tolerance=1e-6)`

屬 validation authority，不能反向成為 production contact tolerance owner。

### CS-8 — current DXF acceptance 已能檢查 layer/type/count，但 marking 需新增 focused roundtrip

Current verifier：

- 真正 `ezdxf.readfile()` reopen；
- 比對 entity type / layer counts；
- 檢查 layer mismatch；
- `coordinate_tolerance=1e-6` 只在 verifier seam 生效。

目前 tests 已驗 CUTTING/BEND/holes/layer mismatch，但尚未有 joint-placement MARKING 的 exact geometry roundtrip case。

### CS-9 — current repository 尚無 Joint Placement Marking resolver / registry / report

現有 canonical spec 描述需求，但 production 尚無以下正式 owner：

- `JointMarkingPolicy` registry；
- legal coplanar contact resolver；
- deterministic boundary-frame resolver；
- marking result / diagnostic DTO；
- export-visible skipped-marking summary。

這些是 v1.3 的實作範圍。

---

## Solution

### SOL-1 — 唯一資料鏈

```text
Canonical Project / Family / Door Topology
        ↓
Physical Parts + Stable IDs
        ↓
Resolved Assembly Placement
        ↓
Final PartRenderData + true-thickness formed geometry
        ↓
JointMarkingPolicy match
        ↓
Legal Coplanar Contact Resolver
        ↓
Contact-local deterministic frame
        ↓
SIDE_BOUNDARY_PAIR extraction
        ↓
Locator world→flat backprojection
        ↓
Final-material containment validation
        ↓
MARKING LinePrimitive(s)
        ↓
Locator PartRenderData.scene / FinalScene
        ↓
2D + DXF
        ↓
Independent export summary + DXF reopen acceptance
```

禁止建立：

- 第二份 2D marking geometry；
- renderer-only marking geometry；
- DXF-export-time joint formulas；
- persisted derived XY truth。

---

### SOL-2 — `JointMarkingPolicy`

建議建立 immutable policy DTO（名稱可等價）：

```text
JointMarkingPolicy
- policy_id
- revision
- enabled
- locator_selector
- attached_selector
- locator_contact_region
- attached_contact_region
- footprint_mode
- boundary_frame_contract
- contact_span_contract
- allowed_overlap_contract
```

Policy 用 stable semantic identity / topology selector，不用 raw coordinate。

Policy registry 的結果只有三種：

1. `MATCHED`：正式求解；
2. `NO_POLICY_REQUIRED`：普通 joint/contact，不求解、不報錯；
3. `EXPLICIT_POLICY_ID_MISSING`：上游明確要求 policy_id 但 registry 找不到，才報 `POLICY_NOT_FOUND`。

禁止把所有 AssemblyJoint 自動轉成 marking。

---

### SOL-3 — 不新增 `AssemblyJointRelation`

Joint Placement Marking 是 manufacturing projection capability。

不得新增：

- `MARK`
- `WELD_MARK`
- `FRAME_MARK`

等假的 AssemblyJoint relation。

Policy 可以引用：

- Resolved AssemblyJoint；
- topology role；
- shared frame role；
- stable physical-part relation；

但不改寫既有 INSERT / OVERLAY / INSERT_OVERLAY / WRAP 語意。

---

## Engineering Contracts

### EC-1 — Legal coplanar contact classifier

第一階段 legal contact 必須同時成立：

1. locator / attached 都來自 authoritative formed true-thickness physical geometry；
2. policy 指定的兩個 regions 存在；
3. 候選 physical faces 在 production geometry tolerance 內共面；
4. face outward normals 都先 canonicalize；
5. 相向 normal 的 normative 判定為：

`norm(N_locator + N_attached) <= opposed_normal_residual_tolerance`

其中兩者皆為 unit normal；

6. 不得把 `dot(N_locator, N_attached) ≈ -1` 的 raw dot 誤差直接當 normative tolerance；若內部為效能使用 dot/angle，必須證明與 residual contract 等價；
7. 在 contact plane 上存在 positive-area overlap；
8. attached solid 不得穿越 locator mating side形成未授權 positive-volume / through-thickness penetration；
9. single-face / terminal-face contact可以合法，不要求 attached 兩張 sheet skin 同時接觸；
10. collision crossing segment 本身不是 legal contact footprint。

Contact resolver 輸出至少包含：

```text
ResolvedLegalContact
- locator_part_id
- attached_part_id
- locator_region
- attached_region
- contact_plane
- locator_outward_normal
- attached_outward_normal
- overlap_world
- locator_flat_mapping
- evidence
```

若 attached terminal face由 true-solid boundary wall形成，可以只要求其 world physical face；**locator side 必須具有 authoritative world→flat mapping**，因 marking 最終寫在 locator。

---

### EC-2 — `contact_span_contract`：數值 tolerance 不等於有效接合尺度

不得使用：

`span > 1e-6`

作為「有效 marking contact」的產品尺度判定。

每個 `SIDE_BOUNDARY_PAIR` policy 必須明確選擇：

#### A. `EXPECTED_REGION_COVERAGE`

Policy 指向 authoritative expected mating region。

Resolver 驗證：

- expected region 的內部在 geometry tolerance 下被 overlap 覆蓋；
- overlap 不得只是 expected region 的微小碎片；
- connected-component / topology 必須符合 policy；
- 不以 fixture mm 常數作門檻。

#### B. `MINIMUM_SPAN`

只有當產品／mechanical authority 明確給出最小尺度時，policy 才能保存：

- `minimum_longitudinal_span`
- `minimum_cross_span`

數值必須有 authority provenance。

**第一個 Receiving left/right frame → Divider policy 使用 `EXPECTED_REGION_COVERAGE`。**

其 expected region是 attached frame 的 authoritative lower terminal mating footprint，在 current placement 下與指定 Divider support face應形成完整 end-contact；不得用任意 mm threshold。

---

### EC-3 — 單一 production tolerance owner

新增或收斂為一個 geometry-neutral production owner，例如：

`AssemblyGeometryToleranceContract`

名稱可調整，但必須只有一個 canonical owner。

至少區分：

- coplanar distance tolerance；
- normal residual / angular tolerance；
- flat/world mapping tolerance；
- boundary separation / degenerate tolerance；
- polygon robustness epsilon（如需要）。

禁止：

- marking policy 自己塞 epsilon；
- renderer 擁有 production tolerance；
- DXF verifier tolerance被 production import；
- pytest fixture expected變成 production epsilon。

**ID-8 invariant 保留：tolerance owner 必須 geometry-neutral 且唯一。**

Current `1e-6 / 1e-7` 只作 baseline evidence；v1.3 不把它們升格成 normative production values。

---

### EC-4 — `boundary_frame_contract`：flat-basis preserving，不再用模糊「canonical mapping」

`SIDE_BOUNDARY_PAIR` 必須有完整：

```text
boundary_frame_contract:
  frame_version: CONTACT_LOCAL_FRAME_V1
  basis_part: LOCATOR | ATTACHED
  basis_contact_region: <semantic region id>
  longitudinal_flat_axis: +X | -X | +Y | -Y
  cross_flat_axis: +X | -X | +Y | -Y
  normal_rule: LOCATOR_TO_ATTACHED
  handedness_rule: FLAT_BASIS_PRESERVING
  negative_role: SIDE_NEGATIVE
  positive_role: SIDE_POSITIVE
```

限制：

- `longitudinal_flat_axis` 與 `cross_flat_axis` 必須來自**同一個 basis_part / 同一 contact panel 的 canonical flat UV**；
- 兩軸必須正交；
- 不得用 bbox long side、world X/Y/Z、renderer orientation 或 endpoint sorting猜軸。

#### EC-4.1 — `N`

`N` = locator contact face 的 unit normal，方向由 locator material 指向 attached mating side。

不得直接信任任意 triangle winding。

若 outward orientation 無法由 physical solid / face ownership唯一決定：

`BOUNDARY_FRAME_UNRESOLVED`

#### EC-4.2 — `L`

以 policy 明確指定的有號 flat axis取得 basis vector，經該 contact panel 的 authoritative fold + placement affine mapping到 world。

投影到 contact plane後：

`L = normalize(project_to_plane(mapped_longitudinal_axis, N))`

若退化：

`BOUNDARY_FRAME_UNRESOLVED`

**L 的正號完全來自 policy 的 signed flat axis。**

#### EC-4.3 — `C` 與 mirror parity

v1.3 **不採用無條件 `C = N × L`**。

原因：world mirror / orientation transform可能是 improper transform；只用 world cross product會在 mirror 下交換 semantic side role。

正確 contract：

1. policy 的 `cross_flat_axis` 也由同一 flat basis映到 world；
2. 對 N / L 做 Gram-Schmidt 投影，得到 semantic `C`；
3. `C` 的正號保留 `cross_flat_axis` 的 canonical sign；
4. 記錄：

`h = sign(dot(C, normalize(N × L)))`

因此：

`C = h × normalize(N × L)`

其中 `h ∈ {+1, -1}` 是**由 canonical flat-basis mapping推導的 orientation parity**，不是可自由切換的設定。

這保證：

- rigid rotation 不換 role；
- mirror / inward orientation不靠 world handedness偷偷換 role；
- `SIDE_NEGATIVE / SIDE_POSITIVE` 跟 part-local canonical flat basis綁定。

#### EC-4.4 — boundary role

取 overlap 的 canonical reference `O`（projected overlap centroid）。

對候選 side boundary `B`：

`s(B) = mean(dot(P - O, C))`

- 較小 = `SIDE_NEGATIVE`
- 較大 = `SIDE_POSITIVE`

若兩側 signed separation在 production geometry tolerance 內無法唯一分離：

`BOUNDARY_PAIR_AMBIGUOUS`

Role 不能叫：

- LEFT / RIGHT
- INNER / OUTER
- X_MIN / X_MAX

因為這些會把 renderer/world orientation混進 manufacturing identity。

---

### EC-5 — 第一個 Receiving policy 的 boundary frame

第一個 Receiving inner-door `left_frame` / `right_frame` → shared horizontal Divider policy固定：

- `basis_part = LOCATOR`
- `basis_contact_region = Divider CORE_PHYSICAL_SEGMENT support face`
- `longitudinal_flat_axis = +X`
- `cross_flat_axis = +Y`
- `normal_rule = LOCATOR_TO_ATTACHED`
- `handedness_rule = FLAT_BASIS_PRESERVING`

Grounding：

- Divider canonical blank 的 `X` 是 fold-chain / depth cross-section axis；
- `Y` 是 Divider span；
- horizontal Divider placement 把 canonical geometry放進 cabinet assembly；
- frame marking 要在 Divider support face上表示兩個豎框 terminal footprint 的兩側定位範圍；
- 使用 locator flat basis避免 attached `frame.span (+Y)` 在 terminal end contact時投影到 support plane退化。

**SUPERSEDES PRE-GATE DRAFT：**

先前 PRE-GATE v1.3 曾寫：

`Receiving frame L = attached +Y`

該說法未經完整 grounding，且 terminal contact下可能退化，現正式撤銷，不得作 implementation oracle。

---

### EC-6 — `SIDE_BOUNDARY_PAIR` 是 contact envelope，不是整個 footprint outline

對 policy-resolved legal contact overlap，`SIDE_BOUNDARY_PAIR` 只取相對 semantic `C` 的兩個外側 longitudinal support boundaries。

要求：

- boundary沿 L 方向有有效連續 coverage；
- `SIDE_NEGATIVE` / `SIDE_POSITIVE`各唯一；
- 不輸出 short end-cap boundary；
- 不輸出 interior concavity / inner edge當第三、第四條 mark；
- 不可跨越 contact 不存在的 gap製造虛假 boundary。

若 footprint topology無法在該 policy 下唯一形成兩個 longitudinal side boundaries：

`FOOTPRINT_MODE_MISMATCH`

並 fail closed。

若未來需要 U-shape 全輪廓、centerline、multiple strips，必須新增另一個 explicit footprint mode；不得偷偷讓 `SIDE_BOUNDARY_PAIR`改義。

---

### EC-7 — Design overlap 的 fail-closed default

在沒有 owning mechanical authority時：

`allowed_overlap_mode = NONE`

若產品設計本來允許 overlap：

- owning AssemblyJoint / Family / mechanical policy 必須宣告 legal overlap region；
- marking policy只能引用；
- resolver必須把 legal overlap與 marking mating interface分開；
- 不得直接把 penetration footprint拿來打標。

第一個 Receiving frame → Divider policy：

`allowed_overlap_mode = NONE`

此為 engineering fail-closed default，不是新增產品 relation。

---

### EC-8 — backprojection 與 Final Material containment

Resolved world contact boundary 必須透過 locator authoritative flat provenance反投影。

不得：

- inverse renderer transform；
- bbox interpolation；
- world-axis比例換算；
- test fixture offset。

Backproject 後每條 mark：

- 必須位於 locator Final Material；
- 不得穿過 CUTTING hole / removed relief；
- 不得自動把超出部分「clip到看起來合理」。

第一階段預設：

若 boundary 任何有效段超出 Final Material或跨 CUTTING void：

`MARK_OUTSIDE_FINAL_MATERIAL`

fail closed。

未來若產品需要合法 clipping，必須另有 policy，不得 implicit clip。

---

### EC-9 — stable marking identity

每條 derived mark必須有 stable semantic identity，不能用座標 hash當主要 identity。

建議：

```text
jointmark:
  <policy_id>:
  <locator_part_id>:
  <attached_part_id>:
  <boundary_role>
```

例如兩支 frame各自有：

- `SIDE_NEGATIVE`
- `SIDE_POSITIVE`

stable ID 在純尺寸／placement改變但 topology identity不變時不變；geometry座標可以改。

實作可以把 identity保存在 resolver result / `PartRenderData.metadata["joint_markings"]`，不要求立即修改 `LinePrimitive` 基礎型別。

---

### EC-10 — marking scene enrichment 必須 pure / deterministic

marking enrichment 必須：

- 讀 canonical resolved parts / placements；
- 回傳新的 locator `PartRenderData` 或新的 scene；
- 不改 `material`；
- 不改 `fold_guides`；
- 不改 CUTTING；
- 不改 BEND；
- 不改 holes；
- 不改 relief；
- 不持久化 derived XY；
- 同一 resolved input + policy revision → 相同 mark identity / geometry / order。

不得對已 enrich scene反覆 append造成 duplicate MARKING。

推薦 pipeline：

`base PartRenderData → marking resolve once → enriched PartRenderData`

而不是 widget callback incremental mutation。

---

### EC-11 — Diagnostics：failure 不可只藏 metadata

建立 dedicated result / diagnostic contract，例如：

```text
ResolvedJointMarkingResult
- policy_id
- policy_revision
- locator_part_id
- attached_part_id
- status
- mark_ids
- diagnostic_code
- diagnostic_detail
- export_disposition
- evidence
```

`status` 至少：

- `EMITTED`
- `SKIPPED_FAIL_CLOSED`

普通「沒有 policy」不建立 failure record。

#### Diagnostic codes

至少包含：

- `POLICY_NOT_FOUND`
- `LOCATOR_MISSING`
- `ATTACHED_MISSING`
- `STALE_STABLE_ID`
- `PLACEMENT_UNRESOLVED`
- `CONTACT_NOT_FOUND`
- `CONTACT_NOT_COPLANAR`
- `CONTACT_NORMAL_MISMATCH`
- `CONTACT_SPAN_BELOW_MINIMUM`
- `CONTACT_NOT_UNIQUE`
- `PENETRATION_NOT_CONTACT`
- `OVERLAP_AUTHORITY_MISSING`
- `BOUNDARY_FRAME_UNRESOLVED`
- `FOOTPRINT_MODE_MISMATCH`
- `BACKPROJECTION_FAILED`
- `BOUNDARY_PAIR_AMBIGUOUS`
- `MARK_OUTSIDE_FINAL_MATERIAL`

語意要求：

- `POLICY_NOT_FOUND` **只**在上游明確指定/要求某 policy_id，registry卻找不到時產生；
- ordinary joint沒有 marking policy＝正常，不報錯；
- `CONTACT_NOT_FOUND`＝policy/parts/placement/regions都有效，但找不到 legal contact candidate；
- 找到 candidate但 normal不合＝`CONTACT_NORMAL_MISMATCH`；
- 找到 legal geometry但 coverage太小＝`CONTACT_SPAN_BELOW_MINIMUM`；
- 多個不可唯一決定的合法 candidate＝`CONTACT_NOT_UNIQUE`。

---

### EC-12 — Export / manufacturing summary 必須可見

只存在 `PartRenderData.metadata` 不足以防止 silent missing lines。

每次 resolved manufacturing export / batch export若存在 `SKIPPED_FAIL_CLOSED` marking，必須產生 machine-readable summary。

至少列：

```text
policy_id
policy_revision
locator_part_id
attached_part_id
status
diagnostic_code
export_disposition
```

GUI 若有 export summary surface：

- 顯示 skipped count；
- 可查看 detail。

Headless：

- 回傳 structured result / report；
- 不得只 print warning。

因此現場拿到「少線 DXF」時，可以區分：

- 此 joint根本沒有 marking policy；
- policy有啟用但 marking fail-closed。

---

## OPEN / Engineering Decision

### OPEN-1 / ED-1 — marking failure 是否阻斷 DXF export

產品尚未明確確認：

A. `BLOCK_EXPORT`

或

B. `ALLOW_EXPORT_WITH_DIAGNOSTIC`

v1.3 不選邊。

實作要求建立獨立 integration contract，例如：

```text
JointMarkingFailurePolicy
- disposition: BLOCK_EXPORT | ALLOW_EXPORT_WITH_DIAGNOSTIC
```

但 production default 在取得產品決策前保持：

`UNRESOLVED`

因此：

- geometry resolver可先完成；
- diagnostics / report可先完成；
- A/B兩種 disposition均可寫 contract tests；
- **不得由實作者把 non-blocking 或 blocking硬編成產品預設**；
- final production activation / acceptance 必須在 owning product authority決定後鎖定。

---

## First Receiving Policy

### RP-1 — identity

建議 policy id：

`RECEIVING_INNER_DOOR_VERTICAL_FRAME_TO_SHARED_DIVIDER_V1`

實際命名可依 registry convention調整，但 revision必須可追蹤。

### RP-2 — selector

對每個 Receiving inner door：

1. 由 canonical inner-door state取得 stable inner door ID；
2. 由 `resolve_inner_door_lower_frame_role()`取得 exact shared horizontal Divider stable ID；
3. attached candidates只包含該 door physical：
   - `left_frame`
   - `right_frame`
4. 不建立 physical bottom frame。

### RP-3 — locator / contact region

Locator：

`shared Divider physical part`

Locator contact region：

`Divider CORE_PHYSICAL_SEGMENT support face`

Attached region：

各 frame 的 authoritative lower terminal end-contact region。

不得用：

- panel bbox；
- whole frame bbox；
- fake bottom frame；
- viewer intersection。

### RP-4 — contact span

`EXPECTED_REGION_COVERAGE`

expected region由 actual formed frame terminal face產生；不得把 fixture尺寸硬寫進 policy。

### RP-5 — boundary frame

```text
basis_part = LOCATOR
basis_contact_region = CORE_PHYSICAL_SEGMENT
longitudinal_flat_axis = +X
cross_flat_axis = +Y
normal_rule = LOCATOR_TO_ATTACHED
handedness_rule = FLAT_BASIS_PRESERVING
```

### RP-6 — output

每個 attached frame：

- `SIDE_NEGATIVE`
- `SIDE_POSITIVE`

各 1 條 `MARKING`。

標準 upper inner door：

- left frame：2
- right frame：2
- total：4

如果某一 frame policy fail closed：

- 不用另一 frame 的座標補；
- 不用 symmetry猜；
- 該 policy輸出 structured failure。

---

## User Stories

### US-1 — 現場定位

身為組裝人員，我在 shared Divider DXF / 加工板件上可以看到 left/right inner-door frame的兩側定位 MARKING，直接依刻線放置零件。

### US-2 — 尺寸變更

身為設計人員，我修改 Door ratio、inner-door size或 placement後，marking跟著 authoritative geometry重算，不需要手動搬線。

### US-3 — 不靜默漏線

身為製造／QA人員，如果某個本來應有 marking 的 policy求解失敗，我可以在 export/manufacturing summary看到 `SKIPPED_FAIL_CLOSED` 與原因，而不是收到一張看似正常但少線的 DXF。

### US-4 — 不污染既有製造幾何

身為工程師，我加入 marking功能時，CUTTING / BEND / holes / relief / final material不會因 marking resolver改變。

### US-5 — 可擴充

身為後續開發者，我可以為新的 mechanical joint新增 explicit policy，而不用在 DXF exporter / renderer新增 hard-coded offset。

---

## Implementation Decisions

### ID-1 — RED-first

不得以 canonical spec存在就假設 production已有 marking resolver。

第一票先建立 RED contracts，證明目前缺：

- policy registry；
- legal coplanar contact；
- boundary frame；
- diagnostic/report；
- Receiving 4-line output。

### ID-2 — geometry helper neutralization

legal contact / face overlap / flat backprojection若需要新 helper，放在 GUI-independent geometry owner。

不得 import：

- Tk；
- renderer；
- DXF verifier；
- tests。

### ID-3 — policy 與 geometry 分離

Policy只描述 semantic intent / selector / mode / contracts。

Geometry resolver只解：

- parts；
- faces；
- contact；
- frame；
- boundary；
- backprojection。

不得把 Receiving part names散落在 generic geometry math中。

### ID-4 — stable identity先於座標

mark ID由：

`policy + locator stable ID + attached stable ID + boundary role`

決定。

不得用 coordinate string / bbox / entity index作唯一身份。

### ID-5 — FinalScene integration在 manufacturing owner

Integration發生在擁有所有 canonical physical `PartRenderData` 與 placements的 resolved manufacturing orchestration。

不得發生在：

- DXF serializer；
- 2D canvas renderer；
- 3D renderer；
- export verification。

### ID-6 — shared lower frame不建立第二 physical part

`bottom_frame` 只能是 shared role / placement handle。

manufacturing part list中 locator仍是原 Divider physical part。

### ID-7 — diagnostics 必須 export-visible

v1.2 的「diagnostic但 non-blocking」拆開：

- diagnostic / report visibility＝必做；
- export blocking disposition＝OPEN-1。

### ID-8 — tolerance owner geometry-neutral且唯一

保留 v1.2 ID-8，並明確：

- current scattered `1e-6 / 1e-7` 是 debt；
- DXF verifier 1e-6 是 validation-only；
- production Joint Marking 必須走 single neutral contract。

### ID-9 — contact-local frame保存 flat-basis parity

不使用「固定 world cross product即代表 semantic side」。

role identity綁 canonical flat basis，world handedness只做 derived evidence。

### ID-10 — 不要求 LinePrimitive立刻承載 source_id

第一版可在 `ResolvedJointMarkingResult` / PartRenderData metadata保存 mark identity，再把 deterministic line primitives append進 scene。

如果後續需要 primitive-level provenance，再獨立擴充 `LinePrimitive`，不能為了本功能強制改所有 DrawingScene consumer。

---

## Testing Decisions

### TD-1 — policy routing

測：

- matching Receiving policy → resolve；
- ordinary unrelated joint → no policy, zero noise；
- explicit policy id miss → `POLICY_NOT_FOUND`。

### TD-2 — legal contact classifier

至少測：

- exact / tolerance-near coplanar face contact → legal；
- opposing normal residual超界 → `CONTACT_NORMAL_MISMATCH`；
- no contact → `CONTACT_NOT_FOUND`；
- interior / through-plane penetration → `PENETRATION_NOT_CONTACT`；
- multiple disjoint valid candidates → `CONTACT_NOT_UNIQUE`。

### TD-3 — frame role invariance

對同一 canonical contact：

- rigid rotation；
- current assembly inward orientation；
- mirror-equivalent transform；

驗證：

- mark stable IDs不換；
- `SIDE_NEGATIVE / SIDE_POSITIVE`不交換 semantic role；
- `L / C`由 signed flat basis重建；
- `h` parity可變，但 role不因 world handedness翻轉。

不得只測座標 set 相同；要測 role identity。

### TD-4 — contact span / fragment rejection

對 `EXPECTED_REGION_COVERAGE`：

- full expected terminal contact → PASS；
- 微小碎片 contact，即使尺寸 > numerical tolerance → FAIL；
- 缺一段 expected region → `CONTACT_SPAN_BELOW_MINIMUM` 或等價 coverage failure；
- fixture數值不得出現在 production policy。

### TD-5 — Receiving exact topology

Receiving upper inner door：

- physical frames只有 top/left/right；
- shared horizontal Divider exact stable ID；
- left/right各 2 marks；
- total 4；
- no fictitious bottom-frame DXF。

### TD-6 — dynamic topology

變更：

- row ratio；
- width；
- inner-door size；
- inward placement；
- shared Divider identity；

驗：

- same stable topology → same mark IDs、geometry隨 placement移動；
- boundary消失 → marks消失；
- ambiguous rebinding → fail closed，不貼到鄰近 Divider。

### TD-7 — no manufacturing mutation

marking前後 compare：

- material symmetric difference = 0；
- CUTTING primitives unchanged；
- BEND / fold_guides unchanged；
- holes unchanged；
- relief metadata/geometry unchanged。

### TD-7A — design overlap

在無 overlap authority：

- penetration不能被 marking resolver當 legal contact。

有 explicit test-only authority時：

- 只允許宣告區域；
- marking interface仍與 penetration evidence分離。

### TD-8 — FinalScene / DXF roundtrip

建立有 joint MARKING 的 locator PartRenderData：

1. save；
2. `ezdxf.readfile()` reopen；
3. verify：

- MARKING LINE count一致；
- MARKING layer一致；
- coordinates在 verifier `coordinate_tolerance`內一致；
- CUTTING / BEND entity set無 drift；
- removed / layer-changed MARKING可被 focused acceptance偵測。

DXF verifier tolerance只能驗，不參與 production contact solve。

### TD-9 — silent-skip report

建立至少以下 fail cases：

- `CONTACT_NOT_FOUND`
- `CONTACT_NOT_UNIQUE`
- `BOUNDARY_FRAME_UNRESOLVED`
- `BACKPROJECTION_FAILED`
- `BOUNDARY_PAIR_AMBIGUOUS`
- `MARK_OUTSIDE_FINAL_MATERIAL`

每個都要驗：

- zero guessed mark；
- `SKIPPED_FAIL_CLOSED`；
- export/manufacturing summary有 policy/parts/code/disposition；
- 不只藏 metadata。

### TD-10 — Save / Reload

Save project不得保存 derived XY。

Reload後：

- same topology/policy revision → same mark IDs；
- marking geometry在 production tolerance內等價；
- stale stable ID不復活。

### TD-11 — 2D owner

2D preview讀 enriched FinalScene。

測試不得讓 2D renderer自行重算 contact或 marking。

### TD-12 — 3D presentation boundary

若本 phase不顯示 3D mark：

- 3D marking presentation可為 N/A；
- manufacturing marking仍不得依賴 3D renderer。

若加入3D顯示：

- 只能投影 same resolved mark；
- 刪除3D display不能改 DXF。

---

## Out of Scope / Open Items

### OPEN-1 — export disposition

`BLOCK_EXPORT` 或 `ALLOW_EXPORT_WITH_DIAGNOSTIC` 待產品確認。

這是本 v1.3 唯一刻意保留的產品決策，不由工程實作偷選。

### OUT-1 — CAM process parameters

不處理：

- laser power；
- marking speed；
- depth；
- machine-specific layer mapping。

### OUT-2 — dashed / segmented marking

canonical geometry仍是完整 boundary。

CAM若要間斷刻線是下游 process policy。

### OUT-3 — 文字、編號、QR、焊接符號

不在本 phase。

### OUT-4 — 人工拖曳 marking

不允許手動拖線變成第二 geometry truth。

### OUT-5 — 非 mapped locator boundary-wall marking

第一階段要求 locator contact face具有 authoritative flat mapping。

若未來 locator本身是 terminal/boundary wall，先擴充 neutral mapped physical-face contract，再新增 policy；不得用 renderer inverse補洞。

---

## Evidence / Traceability

### Skill / process evidence

本輪 fresh-read：

- `.agents/skills/engineering/寫成規格書/SKILL.md`
- `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`
- `AGENTS.md`
- `.agents/skills/skill_registry.json`
- `docs/governance/WHD_規格書Skill前置與Grounding規則.md`

Preflight：

- `寫成規格書` ✓
- `phase6-corner-3d-model-integrity` ✓
- global pitfall reference ✓
- certified relief README ✓
- certified relief registry JSON ✓
- assembly/relief pitfall reference ✓

### Product / manufacturing authority

- `加工層分類與定義.md`
  - `MARKING` = 製造打標／刻字／定位記號／輔助線；Color 211。
- `個人AI檔案庫/第二層_專案與SOP/01_DXF與CAD自動化全域規範.md`
  - Final 2D / FinalScene 是 CUTTING/BEND/MARKING 的製造來源。
- `PHASE6_組合尺寸截角與JointGraph_整合最高優先規格_20260831.md`
  - assembly truth由 Resolved AssemblyJoint Graph / Resolved Manufacturing Geometry承接；2D/3D/DXF不得各算一套。

### Current production code readback

Current target at rewrite start：

`cleanup/2d-3d-sync @ bbf66fdea210420366c6cac805ec279b45330897`

Readbacks：

- `ae_engine/sheetmetal_drawing.py`
  - blob `274f0e1e5fbf1dbbd6046e4d0fff1e2b596b8b6f`
- `ae_engine/ae.py`
  - blob `06cdec4eceab2d8989bc050d98a3963d81a96fa3`
- `ae_engine/manufacturing_api.py`
  - blob `4b2d2ded30d0a86cd92f2cba0a864f1a7208c1d3`
- `ae_engine/inner_door_frames.py`
  - blob `0ebf28d7a7ac15142158ca7c898712b7d9e8da22`
- `ae_engine/door_dividers.py`
  - blob `225b515165d4917de82150fb1ca1a9a86454d57f`
- `ae_engine/assembly_geometry.py`
  - blob `4173836bf3ef878b62e49c4e89d9453f97a60d7c`
- `ae_engine/assembly_collision.py`
  - blob `fc8080986c462370cdc90cc8c528d10c0151946b`
- `ae_engine/dxf_acceptance.py`
  - blob `bb3d60aaba512fdd76589e5f5cd788aface79436`
- `ae_engine/contracts.py`
  - blob `3cb0470e5349a1a6de1262547236c0f713ced88c`

### Current test oracles readback

- `tests/test_sheetmetal_drawing.py`
  - MARKING primitives / color 211
- `tests/test_phase6_t04_inner_door_frames.py`
  - generic frame physical-part contract
- `tests/test_phase6_t05_box_body_dividers.py`
  - Receiving shared lower-frame role，no physical bottom frame
- `tests/test_phase6_t16_receiving_placement.py`
  - authoritative Receiving placement / shared Divider
- `tests/test_phase6_t17_receiving_inner_door_80.py`
  - family inward-vector placement current oracle
- `tests/test_assembly_placement_divider.py`
  - horizontal Divider orientation
- `tests/test_joint_local_collision_classifier.py`
  - legal boundary contact vs penetration current oracle
- `tests/test_dxf_acceptance.py`
  - actual save→reopen verifier / 1e-6 validation seam
- `tests/test_resolved_manufacturing_export.py`
  - resolved export uses exact canonical render_data

### Tolerance re-read requested by v1.2 review

Review要求對 `acdfcfc6…` 重新確認。

已確認：

- `ae_engine/dxf_acceptance.py::verify_saved_part_render_data_dxf()` 在該 lineage 使用 `coordinate_tolerance=1e-6`；
- production assembly geometry / collision存在散落 `1e-6 / 1e-7` defaults；
- current HEAD相關 blobs仍維持上述實作。

分類：

- **CURRENT IMPLEMENTATION**，不是 normative product value；
- DXF `1e-6` 是 **validation-only authority**；
- v1.3 的 normative要求是「single geometry-neutral production tolerance owner」，不是「production 一律 1e-6」。

### Superseded draft record

下列 PRE-GATE v1.3 說法不得再使用：

- `attached frame +Y` 無條件作 contact-local L；
- 無條件 `C = N × L`；
- `marking failure blocks_export=false` 當產品規則；
- metadata-only diagnostic即可；
- `span > linear tolerance` 即視為有效 contact。

本文件為正式 v1.3 replacement。

---

## Completion Gate

實作可宣告 geometry feature GREEN 前，至少必須同時滿足：

- [ ] explicit marking policy registry；
- [ ] legal coplanar contact與 penetration分離；
- [ ] single production tolerance owner；
- [ ] `EXPECTED_REGION_COVERAGE`拒絕碎片 contact；
- [ ] `CONTACT_LOCAL_FRAME_V1`使用 signed flat basis；
- [ ] mirror / inward transform不交換 boundary semantic role；
- [ ] first Receiving policy用 locator Divider `+X / +Y` basis；
- [ ] left/right frame各 2 marks，標準 total 4；
- [ ] no fictitious bottom-frame physical part；
- [ ] marking不改 CUTTING/BEND/holes/relief/material；
- [ ] failed policy出現在 export/manufacturing summary；
- [ ] `POLICY_NOT_FOUND`不污染 ordinary no-policy joints；
- [ ] DXF save→reopen MARKING parity；
- [ ] Save→Reload derived geometry parity；
- [ ] 3D renderer不是 manufacturing authority；
- [ ] OPEN-1 在 final production activation前由產品 authority明確選定。

---

## 一句話 Source of Truth

> **接合定位打標不是「在圖上補兩條線」：它是 explicit marking policy 對 authoritative physical parts 與 placement 求得 legal true-thickness mating contact，再以 canonical flat basis穩定定義兩側 role、反投影到 locator Final Material，最後把 MARKING 寫回同一份 PartRenderData / FinalScene；DXF只序列化，validation tolerance不回灌 production，任何應有 marking 的 fail-closed 都必須可見且不可靜默。**
