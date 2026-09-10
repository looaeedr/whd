---
name: 驗證板件與DXF
description: 使用者要求驗目前板件、指定板件、全部板件、DXF反驗證或 Save→Reload 驗收時，對 current production state 執行 canonical geometry、2D/3D、DXF reopen、multipart physical-part 與 persistence parity；中隔另加 certified CROSS 參數、placement 與 shadow collision diagnostics。
---

# 驗證板件與DXF

## 專案技能邊界

- `修改DXF` **不是本專案 Skill**，不得因名稱含 DXF 就把外部／其他專案的 DXF 修改能力加入 WHD Registry、README、Preflight 或 router。
- 本 Skill **只負責驗證／驗收** current WHD manufacturing output：canonical geometry、2D/3D parity、DXF export→reopen、multipart 與 Save→Reload。
- 本 Skill **不得取代** `修改DXF`，也不得把「驗證輸出 DXF」擴張成「任意修改 DXF 檔案」的編輯能力。
- 若使用者另行點名外部 `修改DXF` Skill，必須回到該 Skill 所屬專案／來源判定其規則，不得自動掛入 WHD 技能樹。

## 何時使用

使用者要求下列任一工作時直接執行，不要只解釋：

- `驗目前板件` / `驗這個板件` / `查目前板件對不對`
- `驗箱身` / `驗中隔` / `驗封頭` / `驗封尾` / `驗門` / `驗底板`
- `驗全部板件` / `完整驗收全部板件`
- `DXF反驗證` / `驗輸出的DXF` / `驗全部DXF`
- `Save→Reload 驗收` / `存檔再讀回來驗`

## 支援板件與 identity authority

至少涵蓋 current canonical manufacturing physical identities：

- `box_body`
- multipart `box_body:left_side / box_body:back / box_body:right_side`
- `box_body:divider:*` / Receiving Divider
- `head`, `tail`
- `door` / dynamic `door_c*_r*`
- `base_plate` / dynamic `base_plate_c*_r*`
- `indicator_box`, `indicator_door`
- `inner_door:*`
- 其他由 current workspace/manufacturing resolver 實際產生的 dynamic IDs

禁止用 GUI 固定白名單或 `PART_LABELS` 冒充 physical-part authority；expected parts 從 current workspace / resolved manufacturing output 取得。

## 驗證模式

### A. 驗目前 / 指定板件

**不需要先存 `.p6fold`。** 直接從 current production state 驗：

1. canonical `PartRenderData` / Final Material；
2. material bounds / span / closed contour；
3. authoritative holes/features；
4. fold guides / BEND；
5. 2D / 3D / DXF 是否使用同一 resolved geometry；
6. 有 assembly contract 時，再驗 world placement / mating contact / illegal penetration。

### B. DXF 反驗證

不必先存專案，但必須真的輸出 DXF：

1. canonical manufacturing geometry → 實際 `.dxf`；
2. `ezdxf.readfile()` 從磁碟 bytes 重開；
3. 抽 `CUTTING / BEND / holes / layers`；
4. normalize 後 compare canonical；
5. multipart/dynamic 同時驗 `expected physical parts == exported DXF files`。

錯誤至少分類：

`MISSING_PART / EXTRA_PART / CUTTING_MISMATCH / BEND_MISMATCH / HOLE_MISMATCH / LAYER_MISMATCH / UNCLOSED_CONTOUR / SERIALIZATION_ERROR`。

### C. 完整板件驗收

A + B + Save→Reload parity：

1. current state 直接驗；
2. DXF export → reopen → compare；
3. `.p6fold` Save → Reload；
4. Reload 後重建 canonical manufacturing output；
5. 比 Final Material、holes/features、BEND、placement、dynamic IDs、physical-part count；
6. `config.ini` SHA256 before/after 一致。

### D. 驗全部板件

從 current workspace 列舉所有 existing physical parts，逐件跑 A/B，再跑 C 的 project parity。任一少檔、多檔、stale dynamic ID、geometry mismatch 都使整體 FAIL。

## 板件專用加強驗證

### Receiving Divider / 中隔

#### 製造 authority（不可被驗證反向覆寫）

Receiving Divider 現行正式製造模型是：**`CornerType=CROSS（十字截角）＋參數`**。

- certified `CROSS` rule / canonical parameters 與已核准 reference DXF 是 manufacturing authority；runtime 應由 Certified Registry / canonical parameters 解析。
- reference `基準檔/金庫型/中隔.dxf` 在其 certified scope 內可作 baseline/authority；不得因舊筆記說「DXF 不是 authority」就整體排除。
- 3D collision/backprojection、penetration probe、bbox/contact measurement 只屬 **shadow verification / diagnostic evidence**：用來判斷既有 CROSS＋參數折後是否干涉，不是最終截角公式來源。
- **Registry HIT 不得覆蓋**：validation/collision 不得以量到的差值、boolean fringe、bbox gap 或 probe 結果改寫已命中的 certified rule/參數。
- 若 shadow verification FAIL，回到使用者規格、Certified Registry、canonical parameters、reference DXF scope 查 root cause；不可把測試量測直接塞回 production。

除通用驗證外，再驗：

- `W - 2T` / Final Material span；
- fixed-hole authoritative DXF feature datum；
- Ø6.4 hole count/diameter/physical-edge offset；
- certified CROSS relief geometry；
- true-thickness skin→solid sweep；
- FW face flush / core inward / authoritative placement；
- pre/post collision shadow diagnostics；
- `illegal penetration = 0`、retained mating contact；
- head/tail shared datum parity。

### Multipart BoxBody

- 每個 physical piece 有 stable identity / own geometry / own DXF；
- Receiving 三件式至少辨識 `left_side / back / right_side`；
- aggregate `box_body` 不得取代逐片 manufacturing acceptance；
- exported DXF count = resolved physical-piece count。

### Head / Tail

Head/Tail 分開驗；不得用一端 PASS 推另一端。mirror/native orientation、FW/Corner policy、BEND、holes 以各自 resolved output 驗證。

### Door / Base Plate / Indicator / Inner Door

依 current resolved identity 驗 Final Material、holes/features、BEND、DXF reopen；dynamic rows/columns 使用 stable IDs，family/project reload 後不得殘留 stale IDs。

## 通用正式測試族

DXF / multipart / production export：

```text
tests/test_dxf_acceptance.py
tests/test_multipart_dxf_acceptance.py
tests/test_resolved_manufacturing_export.py
tests/test_resolved_manufacturing_geometry.py
tests/test_manufacturing_api_finished_face_contract.py
```

Project / Save→Reload / dynamic IDs：

```text
tests/test_issue41_persistence_parity.py
tests/test_issue45_dynamic_parts_2d_roundtrip.py
tests/test_phase6_project_controller.py
tests/test_phase6_project_file.py
tests/test_phase6_project_ownership.py
tests/test_phase6_project_session.py
```

中隔加強族：

```text
tests/test_issue38_receiving_divider_baseline.py
tests/test_issue39_divider_relief.py
tests/test_issue40_divider_6p4_shared_datum.py
tests/test_phase6_t16_receiving_placement.py
tests/test_dm3_divider_canonical_relief_contract.py
tests/test_dm4_divider_resolved_sinks.py
```

實際任務仍依 requested part 與 current source seam 擴充 targeted tests；清單沒列到不代表可跳過真正 owner。

## 必須回報

至少回：branch / tested head / run_id / terminal status、requested/resolved physical IDs、每件 PASS/FAIL、Final Material bounds/span、hole/feature count/datum、BEND parity、DXF reopen、multipart expected/actual file count、placement/collision shadow evidence（適用時）、Save→Reload parity（需要時）、`config.ini` before/after SHA。

中隔再加 certified CROSS rule/parameters、middle segment、FW planes、illegal penetration、retained contact、skin→solid areas 與 shadow collision diagnostics。

## Remote QA 硬規則

- 建立 remote run 後讀 `.agents/skills/engineering/monitoring-remote-qa/SKILL.md`，鎖同一 `run_id + head_sha` 輪詢到 `completed`；`queued/in_progress` 不得停。
- install/preflight/import/dependency failure 不能冒充產品 FAIL。
- one-shot workflow/evidence 用完刪除並遠端反讀確認不存在。
- tested head 之後 production/test blob drift，原 GREEN 失效並重跑。

## Validation / Production 邊界

驗證只判對錯，不能反向成為 production 計算來源。pytest expected、DXF reopen measurement、boolean fringe、collision probe、bbox、單次差值都不是 manufacturing authority。

## UI 邊界

本 Skill 是 AI/工程 QA 入口，不代表 GUI 已新增「驗證板件」按鈕；要 GUI 一鍵驗證需另開 UI feature。

## 自動交接：Focused QA 不得取代成品板件驗收

只要修改會影響下列 production seam，在 merge/close/release 前自動交接本 Skill：

- physical-part identity / dynamic part / multipart topology；
- 2D preview、3D FinalScene、2D↔3D navigation/sync；
- manufacturing Final Material / holes / BEND / placement；
- DXF export / physical-piece file set；
- Save→Reload / persistence；
- GUI/Bridge adapter 會改變操作員看到或選到的 physical part。

issue-specific regression 只證明該 bug seam，不能取代 DXF reopen、physical enumeration、Save→Reload 或 requested-part parity。

只改單一板件且 scope 明確，至少跑「驗該板件」；跨 2D/3D/DXF/persistence/dynamic IDs/multipart 則升級「完整板件驗收」。

缺少本 Skill 成品驗收 evidence 時，狀態只能是 **focused GREEN / final acceptance pending**，不得標 ACCEPTED。

## DXF reopen 的獨立性邊界

- 獨立 = 真的保存 `.dxf` 再 `ezdxf.readfile()` 從磁碟 bytes 重開；不能拿 serializer/scene memory 冒充 reopen。
- CUTTING 的 semantic reconstruction（structural primary、segmented LINE/LWPOLYLINE endpoint snapping、polygonize、same-sheet duplicate、contained holes）屬 production-owned canonical geometry policy。Verifier 呼叫同一 production helper，不在 verifier 維護第二套 tolerance/polygonize 公式。
- Validation 比 canonical Final Material 與 reopen material；不能把 symmetric_difference 面積/差值/test epsilon 寫回 production。
- 若 scene→DXF entity type/count/coordinates 一致但 material reopen mismatch，優先查 verifier 的 canonical reconstruction policy 是否漂移，不先改 exporter/production geometry。
- Negative guards 保留：移動 CUTTING、刪 hole、刪 BEND、改 layer 必須仍被 acceptance 抓到。
