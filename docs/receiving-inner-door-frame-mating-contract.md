---
whd_doc_role: CURRENT
whd_contract: receiving-inner-door-frame-physical-mating
whd_canonical: ae_engine/inner_door_frames.py
whd_schema: WHD_DOC_META_V1
---

# 受電箱內門框：箱身實體貼合面與折後外包尺寸

## 已確認的實體裝配規則（不可混用）

**貼箱身的是各內門框折彎鏈「最後一段 22 mm 折邊」。**

| 內門框 | 已有折彎鏈（保留正負號方向） | 最後 22 mm 貼合對象 |
| --- | --- | --- |
| 上框 | `22 / 46 / 22` | 箱身上封頭板內側實體面 |
| 左框 | `-22 / 20 / 46 / 22` | 箱身左側板內側實體面 |
| 右框 | `22 / 46 / 22` | 箱身右側板內側實體面 |

- **46 mm 是共同的中間段，不是貼箱身的接合折邊。**
- **50 mm = 46 mm + 2T（T=2 mm 時）**，表示內門框折後的外包尺寸；**不是**從外門邊緣向內縮 50 mm，也不是接合面本身長 50 mm。
- 左框比上／右框多出的 `-22 / 20` 是現有折彎鏈的一部分；不可為了 3D 對齊而刪除、強制改成相同折彎鏈、任意鏡射或重排。
- 左／右直框下端接合到實際共用中隔板；中隔是下方支承，不能虛構第四支實體內門框。
- 預設 80 mm 是內門深度方向的可調偏移，與 **50 mm 折後外包尺寸**、**22 mm 箱身貼合折邊**是三個不同概念。

## 3D / 打標 / 內門尺寸的實作要求

1. 先由真實箱身側板／上封頭／中隔的成形表皮及各框最後一段 22 mm 的成形表皮取得安裝位置與方向；不要使用外門成品面加 `50 mm inset` 反推框的實體 X/Y。
2. 框的折彎方向與左右鏡射須按各自 signed Fold Chain 保留；正確安裝後，最後 22 mm 的**實際物理接合面**必須與對應箱身母板實體貼合，不得有空隙或干涉。
3. 接合打標線須在驗證實體接觸成立後，才從母板真實接觸位置回投到母板展開 UV。**正交投影到母板上**不能代替框與母板**真的貼在一起**。
4. 內門成品尺寸應以修正後的內門框實體開口計算，再沿用外門相同的門縫／折邊製造演算法；**不得**直接拿外門成品寬再扣左右各 50 mm，更不能重複扣除板厚。
5. 回歸驗證應涵蓋上／左／右的折後接觸、左右框對中隔下端、門縫、3D 視覺與 DXF 打標。不能把舊的「有投影距離也算接觸」測試當作 GREEN。

## 程式權責及製造驗收

- `ae_engine/inner_door_frames.py` 保留 signed Fold Chain 並提供 `inner_door_frame_formed_occupation(T)`，一律由共同 46 mm 段求 **46＋2T**。
- `ae_engine/assembly_geometry_primitives.py`：左框折後 U 朝箱身左側（−X），右框朝右側（+X），上框朝上封頭（+Y）；**不是鏡射或修改製造折彎鏈**。
- `ae_engine/assembly_placement.py`：以最後 22 mm 折後段的實際座標，貼向箱身左右側板或封頭的**內側實體表皮**。外門座標僅仍提供內門的可調深度方向偏移。
- `ae_engine/cabinet_types/receiving.py`：內門與框寬由同一個 46＋2T 實體開口來源計算；800 寬、T=2、左右門縫各 3.5 mm 時，**內門成品寬 693 mm**。
- `ae_engine/inner_door_panels.py` 與 `ae_engine/manufacturing_scene_orchestration.py`：內門沿用既有四側折門製造公式，左右折邊各 19 mm 時，**下料寬 727 mm**，不得把成品寬當平板下料寬。
- `ae_engine/receiving_joint_marking.py`：以各母板明確的內向法線選取實體皮面，要求末段 22 mm **真實共面、法線相對、區域重疊**；合格才回投至母板 UV 寫入打標。禁止用整塊多折邊側板的 centroid 判斷接合方向。
- `tests/test_issue1050_receiving_mother_plate_marking.py`、`tests/test_receiving_inner_frame_last_flange_contact.py`、`tests/test_phase6_t15_inner_door_panels.py` 與產品回歸須同時覆蓋上述接合、DXF、3D 及 693/727 尺寸。
- 舊相容欄位 `INNER_DOOR_INSET_LEFT/RIGHT/TOP=50` **不得再參與新實體 3D/製造定位計算**；保留它們不能解讀為允許重啟外門 50 mm 相對位移。
- `docs/superpowers/specs/2026-09-06-receiving-inner-door-frame-80.md` 為 HISTORICAL，僅追溯深度偏移，不覆蓋此物理接合契約。

> 製造重點：**最後一段 22 mm 折邊貼箱身；46＋2T 是 50 mm 折後外包尺寸；80 mm 是深度偏移。三者不能互相取代。**
