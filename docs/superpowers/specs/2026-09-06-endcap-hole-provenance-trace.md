# 封頭／封尾 Hole and Secondary Feature Provenance Trace 規格書

- **工單編號**: T5 (Issue #5)
- **基準分支**: cleanup/2d-3d-sync
- **日期**: 2026-09-06
- **狀態**: 已完成程式與幾何追溯 (Completed)
- **依據設計文件**: docs/superpowers/specs/2026-09-05-2d-3d-receiving-box-integrity-design.md

---

## 1. 目的與核心原則

在對受電箱 (Receiving) 封頭／封尾 (Head / Tail) 孔位進行修改或考慮共用金庫型 (Vault) Policy 前，必須嚴格追溯每一個實體 hole / secondary feature 的來源、製造語意、適用面、基準線與座標幾何依據。

### 核心原則 (Hard Constraints)
1. **禁止盲目共用 (No Blind Sharing)**：不得因 feature 名稱相同即判定語意相同；不得在未完成追溯前將 Vault 全套 hole policy 複製到 Receiving。
2. **禁止猜測常數 (No Guessing Constants)**：不得在未經製造認證前新增或硬編碼 Receiving hole XY 常數。
3. **基準線單一真相 (Single Source of Truth for Datums)**：座標必須綁定物理折線 (Bend line)、截角線 (Relief boundary) 或成品面 (Finished face)，禁止依賴毛胚外框無自適應常數。

---

## 2. 封頭／封尾 Hole and Feature Provenance Table

| Feature 名稱 | Source (程式與設定來源) | Semantic Purpose (製造語意) | Face (作用面) | Datum (基準線) | Coordinate Basis (座標計算基礎) | Family Applicability | Share Status (共用策略) |
|---|---|---|---|---|---|---|---|
| **左吊掛孔**<br>left_hanging_hole<br>(vault_endcap_hanging) | VaultEndCapFeaturePolicy<br>config.ini [HOLES]<br>hang_hole_radius=3.2<br>hang_hole_y_from_top_bend=6.0<br>hanging_hole_offset_from_primary=10.5 | 金庫型封頭/封尾上方懸掛與吊裝吊孔，供起吊與吊具固定使用 | 封頭/封尾上方折邊區 (top_first_fold 內側/交界) | **X**: 上方左一級截角邊界線<br>relief.top_primary_left<br>**Y**: 上方第一折折彎線<br>top_first_fold | `X = relief.top_primary_left + 10.5`<br>`Y = total_depth - abs(ytop1) + 6.0`<br>高度依賴金庫型 40x41 Primary Relief | **Vault Only**<br>(金庫型專用) | **DO_NOT_SHARE**<br>Receiving 預設停用。<br>僅圓孔形狀公式可共用，定位 policy 絕對不共用。 |
| **右吊掛孔**<br>right_hanging_hole<br>(vault_endcap_hanging) | VaultEndCapFeaturePolicy<br>config.ini [HOLES]<br>hang_hole_radius=3.2<br>hang_hole_y_from_top_bend=6.0<br>hanging_hole_offset_from_primary=10.5 | 金庫型封頭/封尾上方右側對稱吊孔 | 封頭/封尾上方折邊區 (top_first_fold 內側/交界) | **X**: 上方右一級截角邊界線<br>total_width - relief.top_primary_right<br>**Y**: 上方第一折折彎線<br>top_first_fold | `X = total_width - relief.top_primary_right - 10.5`<br>`Y = total_depth - abs(ytop1) + 6.0` | **Vault Only**<br>(金庫型專用) | **DO_NOT_SHARE**<br>Receiving 預設停用。<br>高度依賴 Vault Primary Relief。 |
| **方孔**<br>square_hole<br>(vault_endcap_square) | VaultEndCapFeaturePolicy<br>config.ini [HOLES]<br>sq_x_left=3.0<br>sq_y_bottom=18.0<br>sq_width=4.0<br>sq_height=4.0 | 金庫型左下角接地片固定或組裝卡榫專用方孔 | 展開料左下角折彎過渡區 | **X**: 毛胚左緣 X=0<br>**Y**: 毛胚底緣 Y=0<br>(歷史寫死毛胚外框) | `X_center = 3.0 + 4.0/2 = 5.0`<br>`Y_center = 18.0 + 4.0/2 = 20.0`<br>未考慮板厚 T、bottom_fold 與折彎扣量 | **Vault Only**<br>(歷史遺留) | **DO_NOT_SHARE**<br>Receiving 預設停用。<br>若移至 Receiving 會直接踩在 WRAP/底折線上。 |
| **封尾底部中心圓孔**<br>tail_bottom_center_round_hole<br>(vault_tail_bottom) | VaultEndCapFeaturePolicy<br>config.ini [HOLES]<br>bottom_hole_radius=2.5<br>bottom_hole_y_from_bottom=5.0 | 僅限封尾 (Tail, is_tail=True)：底折邊中央洩水與底座裝配孔 | 封尾底折邊 (bottom_fold 面) | **X**: 板材水平對稱中心線<br>total_width / 2.0<br>**Y**: 毛胚底緣 Y=0 | `X = total_width / 2.0`<br>`Y = 5.0`<br>Y=5.0 未隨 bottom_fold 深度自適應 | **Vault Tail Only**<br>(金庫型封尾專用) | **DO_NOT_SHARE**<br>Receiving 預設停用。<br>Receiving 底側具 WRAP 接合，不得沿用 5.0mm 寫死常數。 |
| **使用者自訂開孔**<br>user_surface_features<br>(head_holes, tail_holes) | BoxCalculatorGUI.surface_features<br>2D/3D 孔位編輯器<br>resolve_endcap_features | 使用者依實際配電盤需求繪製之進出線孔、固定孔與儀表開孔 | 封頭/封尾折後成品主面 (finished_face) | 由使用者設定之 FeatureAnchor 決定 (如 TOP_LEFT, CENTER) | `finished_point = anchor + offset`<br>`(x, y) = _map_endcap_finished_point(...)` | **Universal**<br>(所有箱型通用) | **SHARE_CONTRACT**<br>完全共用相同的成品面映射與往返保存合約。 |

---

## 3. 每個 Feature 的 9 問 9 答 (Detailed Q&A Trace)

### 3.1 左吊掛孔 (left_hanging_hole)
1. **誰定義？**：由 ae_engine/sheetmetal_features.py 中的 VaultEndCapFeaturePolicy 定義，並在 ae_engine/ae.py 中實例化。
2. **使用哪個 policy / registry / config？**：VaultEndCapFeaturePolicy，參數來源為 config.ini [HOLES] 區段之 hang_hole_radius、hang_hole_y_from_top_bend、hanging_hole_offset_from_primary。
3. **製造語意？**：金庫型箱體吊掛定位孔。
4. **哪個 face？**：封頭/尾展開圖上方第一折折彎區域 (top_first_fold)。
5. **哪條 datum line？**：X 軸以左上方一級截角內邊線 relief.top_primary_left 為 Datum；Y 軸以上方第一折線 (ytop1) 為 Datum。
6. **座標量測來源？**：X = top_primary_left + 10.5，Y = total_depth - ytop1 + 6.0。
7. **是否涉及 relief / bend / thickness？**：是。強烈依賴金庫型特定的一級截角深度（通常為 40mm）與第一折位置。
8. **Vault 與 Receiving 是否真的是相同語意？**：否。Receiving 箱體不一定具備 ytop1 折邊，其截角與接合方式亦與金庫型不同，若直接套用會造成孔位漂移或破孔。
9. **可共享的是什麼？**：僅形狀定義 (ResolvedCircle) 與渲染邏輯可共用；定位 Policy 與幾何常數禁止共用。

### 3.2 右吊掛孔 (right_hanging_hole)
1. **誰定義？**：同左吊掛孔，由 VaultEndCapFeaturePolicy 定義。
2. **使用哪個 policy / registry / config？**：VaultEndCapFeaturePolicy + config.ini [HOLES]。
3. **製造語意？**：右側對稱吊掛定位孔。
4. **哪個 face？**：封頭/尾展開圖上方第一折折彎區域。
5. **哪條 datum line？**：X 軸以右上方一級截角線 total_width - relief.top_primary_right 為 Datum；Y 軸以上方第一折線為 Datum。
6. **座標量測來源？**：X = total_width - top_primary_right - 10.5，Y = total_depth - ytop1 + 6.0。
7. **是否涉及 relief / bend / thickness？**：是。強烈依賴金庫型右側截角與第一折位置。
8. **Vault 與 Receiving 是否真的是相同語意？**：否。
9. **可共享的是什麼？**：形狀定義可共用，Family Policy 禁止共用。

### 3.3 方孔 (square_hole)
1. **誰定義？**：由 VaultEndCapFeaturePolicy 定義。
2. **使用哪個 policy / registry / config？**：VaultEndCapFeaturePolicy + config.ini [HOLES] (sq_x_left, sq_y_bottom, sq_width, sq_height)。
3. **製造語意？**：金庫型專用接地片或組裝卡榫方孔。
4. **哪個 face？**：展開板件左下角過渡區。
5. **哪條 datum line？**：毛胚外框左緣 (X=0) 與底緣 (Y=0)。
6. **座標量測來源？**：直接自毛胚左下角測量 (3.0, 18.0)。
7. **是否涉及 relief / bend / thickness？**：否。未隨板厚與折邊尺寸自適應，屬於歷史寫死坐標。
8. **Vault 與 Receiving 是否真的是相同語意？**：否。受電箱下方具備 WRAP 包覆接合，該區域需要保持完整的母材與退讓，若盲目開方孔會破壞 WRAP 氣密與結構強度。
9. **可共享的是什麼？**：僅 ResolvedRect 圖元結構可共用，Policy 禁止共用。

### 3.4 封尾底部中心圓孔 (tail_bottom_center_round_hole)
1. **誰定義？**：由 VaultEndCapFeaturePolicy 定義，條件限制 is_tail=True。
2. **使用哪個 policy / registry / config？**：VaultEndCapFeaturePolicy + config.ini [HOLES] (bottom_hole_radius, bottom_hole_y_from_bottom)。
3. **製造語意？**：金庫型封尾底邊正中央之洩水／定位孔。
4. **哪個 face？**：封尾底折邊 (bottom_fold)。
5. **哪條 datum line？**：X 軸為水平中線 (total_width / 2.0)；Y 軸為毛胚底緣 (Y=0)。
6. **座標量測來源？**：X = total_width / 2.0, Y = 5.0。
7. **是否涉及 relief / bend / thickness？**：部分涉及（X 自適應寬度，但 Y=5.0 寫死）。
8. **Vault 與 Receiving 是否真的是相同語意？**：否。受電箱封尾下方具有獨立的底板接縫與 WRAP 避讓，底邊幾何語意與金庫型封尾不同。
9. **可共享的是什麼？**：水平居中圓孔之幾何公式結構可共用，Family Policy 禁止共用。

---

## 4. 對後續 T6 (Receiving Hole Policy) 的決策指引

1. **獨立 Policy 定義**：
   - 必須建立獨立的 ReceivingEndCapFeaturePolicy（或由 Cabinet Family Registry 解析），不得在 _build_end_cap_scene 中無條件呼叫 resolve_vault_endcap_fixed_features。
2. **預設行為 (Default Safe State)**：
   - 受電箱 (Receiving) 封頭與封尾的固定預設特徵集合為 **空 (Empty)**。
   - 除非操作員顯式啟用或未來有明確受電箱認證圖紙，否則**預設不得自動打出 Vault 的吊掛孔、方孔或尾底圓孔**。
3. **自訂開孔保留**：
   - 使用者透過 2D/3D 孔位編輯器加入的自訂孔位，透過 surface_features 與 resolve_endcap_features 正常保留並輸出。

---

## 5. 驗收結論

- [x] 完整追溯 4 項固定特徵與 1 項自訂特徵之程式碼位置與定義。
- [x] 完整回答 9 項製造與幾何核心問題。
- [x] 明確劃分 Vault 與 Receiving 的邊界，確認 4 項 Vault 固定特徵之 Share Status 皆為 DO_NOT_SHARE。
- [x] 本文件作為工單 T6 實作之權威依據。
