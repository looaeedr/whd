# WHD 板金展開自動化系統 — AI 接手總覽

## [CURRENT] 2026-09-02 Runtime semantic guard

- `OVERLAY = 貼外`。
- `包覆貼外 = 高階 preset`；`WRAP = 下方局部包覆 Joint`；**包覆貼外 ≠ OVERLAY ≠ WRAP**。
- Receiving EndCap D core = `D - 2T`。
- Vault EndCap D core = `D - 3T`。
- Active standard OVERLAY rule：`ENDCAP_TOP_OVERLAY_STANDARD_V1@3`，正式公式以 STANDARD + semantic delta 為 Source of Truth：`primary_u = side_fold + FW`、`primary_v = ytop1 + FW - T`、`secondary_u = side_fold`、`secondary_depth = T`。fixture `T=2 / side_fold=15 / FW=25 / ytop1=16` = **`40×39 + 15×2`**。
- `formed FW` 只保留作 3D shadow / collision evidence，**不得作 runtime CUTTING oracle**，也不得回寫 EndCap material FW。
- **`40×23 + 16×4` 只屬 linked-FW `INSERT_OVERLAY` fixture**（`ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1@1`），不是標準 OVERLAY oracle。

## 2026-08-29 最新接手重點：EndCap 單級 INSERT 截角 38×27 真值與三視圖同步

- 使用者實檔 `自訂(9).p6fold` 已確認：封頭／封尾上方單級 `INSERT` 的正確製造截角為 **38×27 mm**，不是 40×27，也不是把 38.98 四捨五入成 39×27。
- 根因分兩層：
  1. 單板 3D 若 canonical relief state 驗證失效，會退回 legacy fixed relief，曾顯示 40×27。
  2. collision backprojection 若直接採用 ±T/2 physical skin 的外側交線，會把正常貼合 skin contact 算成穿透，得到約 38.98×27。
- 正式規則：**正常面接觸／skin 接觸帶不是實體干涉**。單級 `INSERT` 必須以折後實際 mating boundary 回投影為 relief 邊界；`T=2` 的本實檔對應為 38×27。
- 38 是幾何結果，不得硬寫成通用常數。換 W/D/FW/T/Fold Profile 後仍由 3D 裝配幾何重新求解。
- 單板 2D、單板 3D、組合圖尺寸文字與組合 material 全部只消費 canonical `PartSpec -> Manufacturing API -> PartRenderData`；不得任何畫面另用 legacy CornerType/fixed relief 算尺寸。
- `自訂(9)` fresh runtime：Head/Tail `verified=True`、`errors={}`；左右角皆 `38×27`；主 2D vs assembly Head/Tail material `symmetric_difference.area == 0`。
- 相關驗證文件：`docs/superpowers/verification/2026-08-29-endcap-relief-38-sync.md`。


目前基準：**V5 / 金庫型第一套 Factory Policy**。

本文件是下一個 AI 的第一入口。需要細節時再讀 `handoff/`。

## 核心資料流

```text
Config / 1.csv / Baseline DXF
        ↓
Part Adapter
        ↓
Structural Geometry
        ↓
Features / Factory Policy
        ↓
Drawing primitives
        ↓
DrawingScene / SceneData
        ├─ GUI renderer
        └─ DXF serializer
```

## 模組責任

- `sheetmetal_geometry.py`：純 2D 結構幾何。Shapely topology / boolean、CUTTING、BEND。不得依賴 ezdxf/tkinter。
- `sheetmetal_features.py`：孔、功能切口、Factory Policy、Feature resolver、GUI interaction/world-space guides。
- `sheetmetal_part_adapters.py`：舊參數/config → `StructuralGeometryResult`。GUI/DXF 共用。
- `sheetmetal_drawing.py`：`DrawingScene`、`SceneData`、Polyline/Line/Circle/Text primitives、CHECK/STOCK/DATUM drawing semantics。
- `ae.py`：dispatcher + scene assembly + DXF serializer/save。不得重新推導主結構座標。
- `gui.py`：Canvas render/interaction。不得擁有製造幾何公式。

## 已淘汰

- 手工 12/16/17 點主輪廓。
- Box Body `x1...x8` exporter bend chain。
- GUI/DXF 各算一套 geometry。
- `geom['polylines'/'lines'/'circles']` legacy contract。
- 多套 DXF serializer。

## 目前 topology

- Door / Indicator Box / Base Plate / End Cap-Tail → FourSideFlange family。
- Box Body → StripFoldChain。
- End Cap/Tail = FourSideFlange + 金庫型 Assembly Insertion Relief policy。

## 接手規則

1. 新盤名不等於新 geometry algorithm。
2. 新尺寸/厚度/左右非對稱不等於新 Rule。
3. 只有新的物理干涉、裝配關係或 topology 才新增 Policy/Rule。
4. Structural geometry 修改必須 TDD。
5. GUI 只 render world geometry；DXF 只 serialize DrawingScene。
6. 金庫型 factory rule 不可直接推廣成所有箱型通則。

## 目前驗證基準

目前 fresh verification：`97/97 PASS`。`ae.py` 的所有 exporter 已收斂到 `_save_scene_dxf()` 單一存檔路徑，並新增 `export_part_dxf()` canonical dispatcher；production code 已無 legacy geom dict contract。

## 閱讀順序

1. `AI_HANDOFF.md`
2. `handoff/01_ARCHITECTURE.md`
3. 若改金庫型裝配規則：`handoff/02_VAULT_FACTORY_RULES.md`
4. 若改零件 topology：`handoff/03_PART_TOPOLOGY_MAP.md`
5. 修改程式前：`handoff/04_DEVELOPMENT_RULES.md`
6. 下一階段：`handoff/05_NEXT_STEPS.md`


## Generic FeatureSurface / HoleRegion (2026-08-11)
- Any valid structural/CUTTING polygon can become a hole-capable surface; validation has no part-name allow-list.
- Full footprint containment is mandatory (`polygon.covers`), not center-point checks.
- Invalid drag stays at the last legal feature position.
- Head/Tail use the finished-face surface; Box Body/Door/Base/Indicator panels use authoritative unfolded outlines.
- Right-click opens the generic editor on Box Body, Door, Base Plate, Indicator Box, Indicator Door; Head/Tail keep double-click and also accept right-click.

## 2026-08-11 Unified Hole Editor finalization
- Head/Tail no longer own a separate hole editor UI; all seven supported panel surfaces use one unified editor.
- Main-panel entry is double-click only. Right-click on the main panel no longer opens holes; right-click inside the editor on an inserted feature selects its nine-position crosshair anchor.
- Nine reference anchors: 中心 / 中上 / 中下 / 中左 / 中右 / 左上 / 左下 / 右上 / 右下.
- Neighbor selection uses the same anchor point on other features and ranks perpendicular distance to the active reference line first, along-axis distance second, restricted to the active edge side.
- Center edge tie-break: X -> left; Y -> bottom.
- Left catalog remains persistent; Insert explicitly enters placement mode. Created-hole list double-click toggles CUTTING <-> BLIND_HOLE.
- Four large reference fields: X edge, X neighbor, Y edge, Y neighbor. Editing one moves the feature through pure reference helpers and refreshes the paired value.
- FeatureSurface full-footprint containment remains authoritative.
- Fresh verification at handoff: 171/171 pytest PASS; GUI init/draw and seven double-click bindings verified under Xvfb; CUTTING/BLIND_HOLE DXF round-trip verified.

## 2026-08-11 Finished Boundary / fullscreen / catalog double-click UX
- Catalog list: single click selects; double-click on non-custom catalog definitions enters insert mode immediately. Custom circle/rectangle still require entering dimensions first. Insert button remains available.
- Reference overlays: layout_reference_overlay_rects keeps X/Y edge and neighbor inputs plus the anchor action panel outside the selected feature bbox and mutually non-overlapping.
- Fullscreen: toolbar button + F11 toggle. Uses native Tk fullscreen where supported; falls back to screen-sized geometry when the window manager ignores -fullscreen; restores prior geometry on exit.
- Finished Boundary: user-facing dimension/reference guide uses assembled/finished dimensions rather than bend-line spans. It is drawn as an external dashed guide and the W/H labels report finished dimensions. Reference-distance editing uses the same guide, so an entered 50 means 50 mm from the assembled reference boundary.
- FeatureSurface containment is unchanged: Finished Boundary is a measurement/reference guide only and does not enlarge the valid cutting surface.
- Verification: 187/187 pytest PASS; core modules py_compile PASS; Xvfb GUI verification confirmed Finished Boundary labels, fullscreen fallback/restore, and editor controls.

## 2026-08-11 Round-hole pattern / pipe catalog update
- Unified hole editor now shows two visible catalogs: `一般開孔` from `基準檔/開孔/開孔.csv` and `管孔清單` from `基準檔/開孔/管孔尺寸清單.csv`.
- Pipe CSV parser accepts diameter prefixes such as `Ø 116.0000`; the bundled file now loads 15 pipe rows instead of 0.
- Double-clicking any non-custom row in either catalog enters insertion mode. Custom circle/rectangle still require explicit size input.
- Main reference overlay groups X/Y edge distances together and X/Y neighbor distances together. Entry font reduced to 14pt while preserving collision avoidance.
- Circular placed features enable `圓孔排列設定` with six directions: left/right/up/down/both horizontal/both vertical.
- Both `孔心距` and `間距` stay visible and synchronized. Editing either field makes it the current driver. For circles: center distance = gap + r1 + r2.
- `填滿` preserves the current circle as seed and extends in the chosen direction; `重新填滿` rebuilds the run against/within available FeatureSurface span without preserving the seed's run coordinate.
- If another circular hole exists, round settings expose `孔心齊 / 管頂齊 / 管底齊`.
- Round settings use their own transactional Confirm/Cancel. Main `確定定位` records reference authority; round `確定` records round authority. Whichever workflow is confirmed last owns the resulting geometry when they conflict.
- Fresh tests at delivery: 201 passed. Runtime Xvfb checks verified 15 pipe rows, round settings controls, gap->center synchronization, circular alignment controls, fill preview, and cancel restoration.

## 2026-08-11 — Right-click reference UI + Undo + tests/ migration
- Removed the visible reference-anchor combobox from the unified hole editor. The nine-point reference anchor is changed only from the placed-hole right-click menu.
- Reference distance controls use compact 12pt numeric entries.
- Edge/neighbor/confirm-cancel overlay groups follow the active crosshair position, not only the feature bbox, while still avoiding the feature footprint and each other.
- Floating reference panel now contains compact `確定` / `取消` and round-pattern entry; it moves with the crosshair.
- Added `↶ 回上一步` and Ctrl+Z/Ctrl+Shift-case binding via `EditorUndoHistory(max_steps=50)`.
- Undo snapshots cover committed reference edits, process toggles, deletes, and confirmed round-pattern changes; an in-progress reference transaction is cancelled first when Undo is pressed.
- All root `test_*.py` files were moved to `tests/`. `tests/conftest.py` restores project-root imports; path-sensitive source tests now reference the parent project directory.
- Fresh verification: 208/208 pytest PASS; core py_compile PASS; Xvfb Tk smoke confirms 0 reference comboboxes, Undo button/Ctrl+Z, and floating overlay frames.

## 2026-08-17 CornerType / 未知類型

截角公式已改為兩層責任：

```text
Fold Geometry（折幾彎、折多大、折線位置）
+
CornerType（角本身固定規則）
=
Final CUTTING
```

CornerType 不得保存任何實際折彎尺寸。現有型式：

- `C01 標準截角`：殘差 `(0, 0)`。
- `C02 單邊留肉 1T`：殘差 `(-1T, 0)`；旋轉 90° 後為 Y 向留肉，仍是 C02。
- `C03 雙向多切 0.5T`：殘差 `(+0.5T, +0.5T)`。
- `C04 雙段截角`：Primary `(FW, FW-T)`；Secondary `(+0.5T, depth=2T)`。

**金庫型 Factory Policy 不可由 GUI 改動。** 固定映射為：Door / Indicator Box / Indicator Door → C02；Base Plate → C01；EndCap/Tail 下方 → C03；上方 → C04。只有新增的 `未知類型` 模式顯示手動 CornerType 選擇與小圖預覽，且未知類型不載入 baseline DXF secondary features。

重構驗證：代表性 direct Door / EndCap / Base Plate / Indicator Box，以及 stretched Door / EndCap，在重構前後 DXF modelspace entity geometry 逐項一致。

## 2026-08-29 Assembly collision / registry delivery gate
- Never diagnose assembly collision from already-relieved display material. `AssemblySceneRenderData.interference_probe_parts` carries pre-solve Head/Tail geometry only for diagnostics; `assembly_parts` carries canonical solved production material.
- All registered box assembly intents are regression-driven from `BOX_ASSEMBLY_TYPE_IDS`; do not hand-maintain a separate test whitelist.
- Required invariants per registered intent: Head/Tail pre-solve collision evidence, verified zero retained-material penetration, legal corner topology stage count preserved, symmetric geometry -> mirror-equal results, main 2D == single 3D == assembly material, collision overlay visible, Save/Reload stable.
- OVERLAY flat-X is not exempt from topology normalization. Triangle skin noise must not create a fake secondary stage. A residual skin crossing may be treated as contact only when it lies inside the small topology boundary band AND the semantic mid-surface is clear.
- [FIXTURE] User regressions: `自訂(9)` INSERT remains 38×27; `自訂(10)` INSERT_OVERLAY remains `40×23 + 16×4`; both are regression fixture evidence, not runtime dead dimensions; both show actual collision evidence before relief and verify after relief.

## 2026-08-29 接手重點：Certified Relief Registry
- 不要再讓 3D solver 覆蓋已認證截角公式。
- `lookup_certified_endcap_relief()` 命中時，正式結果來自 registry formula；solver 只做 shadow validation。
- 第一筆 certified rule 是 `ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1`。
- 這筆規則不是「寫死 38×27」；38×27 是標準 linked-FW INSERT 參數下由公式算出的結果。
- OVERLAY / INSERT_OVERLAY 尚未全部升格為 CERTIFIED；不要擅自把目前 3D 結果寫成認證公式。

## 2026-08-29 Certified Relief Registry — 正式 Source of Truth
- **已知組合不再以即時 3D discovery 為最高真值。** Active `CERTIFIED / CERTIFIED_FROM_3D` rule 命中後，registry formula 是正式製造 Source of Truth；3D 只能 shadow validate。
- Registry owner：`ae_engine/certified_relief_registry.py`。
- 金庫型與受電箱固定 CornerType policy 已 family-aware 入庫；Door/Base/Indicator adapters 與 known-model GUI state 都應從 registry 取值，不得重新散落硬建 C01~C04。
- Active EndCap TOP rules：standard INSERT / OVERLAY / INSERT_OVERLAY、linked-FW INSERT 38×27 formula、linked-FW INSERT_OVERLAY 二級 formula。
- `ENGINE_CONFLICT`：正式結果仍採 certified formula，只報診斷；禁止用 3D 候選覆蓋。
- `REGISTRY_AMBIGUOUS`：直接阻止自動決策；禁止 exception swallowing 後 fallback。
- 3D fallback 開關只控制 registry MISS 的 discovery；不能關閉 certified lookup。
- Save/Reload 必須保留 `rule_id / rule_revision / trust_level`；stale revision 必須 invalidation。
- Promotion 按鈕只建立 manifest；runtime 不得直接改正式 registry。
- **Head canonical orientation 注意**：Head 最終 2D Y-mirror，因此 semantic TOP joint 位於 canonical physical bottom；Tail semantic TOP 位於 physical top。不要用角名文字直接猜 assembly joint。
- GUI acceptance matrix 必須從 active Certified Relief Registry 自動列舉。新增新組合若沒有 active rule/fixture/matrix PASS，不能宣稱可生產。

## 2026-08-29 INSERT / C04 最新硬性契約
- 純 INSERT 與 OVERLAY 永遠是單級；secondary_* 只屬於 INSERT_OVERLAY。
- Registry 必須驗證 rule.topology_levels 與實際 corner relief stage count，違反直接拒絕。
- linked-FW C04/INSERT_OVERLAY 正確公式不是 16×23+14×4。正確為 primary_u=side+FW、primary_v=FW-1T、secondary_u=side+0.5T、secondary_depth=2T；T2/side15/FW25 fixture = 40×23+16×4。
- 先前 16×23+14×4 是錯誤 3D candidate，禁止再作 regression 或 promotion evidence。

## [HISTORICAL/SUPERSEDED — 不可作 runtime oracle] 2026-08-29 OVERLAY formed-FW / flat-X 契約
- `OVERLAY` 的 EndCap X topology 為 flat：**沒有左右 X BEND**。legacy `yl1/yr1` 不得再加入 flat-X manufacturing CUTTING。
- EndCap nominal/material `FW` 與 Box Body formed FW occupation 必須分離。fixture `W=400/T=2/FW=25` 的 EndCap FW 仍是 25，但箱身 Fold Profile 折後 formed FW occupation 是 **29**。
- [HISTORICAL/SUPERSEDED — 不可作 runtime oracle] 當時標準 OVERLAY 上方 X relief 讀 `BOX_BODY_FORMED_FW`；`ENDCAP_TOP_OVERLAY_STANDARD_V1@2` 使用 `primary_u = mating_width`，fixture 每側 U=29、中央 342。此 contract 已被 v3 STANDARD + semantic delta 取代。
- Y relief 仍以 EndCap 自身 nominal FW 計算：`ytop1 + FW - amount_t*T = 16+25-2 = 39`。**禁止把 EndCap frame_width 改成 29**，否則 Y 會被錯放大。
- 下方 CROSS / EXTRA_CUT / WIDTH / 1.5T 與上方裝配 relief 獨立；T=2 時每側 3、中央 394。
- [HISTORICAL] 當時 `.p6fold` committed relief 使用 `relief_contract_version=2` 與 formed-FW fingerprint；僅保留 migration/fixture 證據，**不得作 runtime oracle**。
- 歷史錯誤 `40/320`（加了 nominal side 15）與 `25/350`（漏看 formed FW）都已 superseded，不得再作 regression oracle。

## 2026-08-30 Receiving lower WRAP clarification

- Receiving Box Body remains `THREE_PIECE_SIDE_BACK_SPLIT`; WRAP is not a fourth EndCap Assembly Intent.
- Head/Tail keep INSERT / OVERLAY / INSERT_OVERLAY; each can additionally enable lower external WRAP. WRAP is lower-face-only for this receiving implementation and is normally linked Head↔Tail.
- WRAP lower relief uses its own Registry formula with adjustable `reserve_u` (default 2 mm) and `reserve_v` (default 1 mm). These controls live in the unlocked parameter area.
- Default 15/15/15 geometry evaluates to 28×14 + 15×1, but reserves are explicit mm inputs, not fixed T multipliers.
- Blank/unfolded stock information is measured from each part's canonical final material. Head and Tail never copy each other's material even when WRAP settings are linked.
- Receiving uses core-origin EndCap assembly placement; this is intentionally family-scoped so Vault/custom placement remains unchanged.
- Project skills now live only under `.agents/skills/`. Any corner/Joint/3D change must invoke the corner-3D model integrity gate.
