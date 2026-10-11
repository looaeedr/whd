# #1494：NFB X 基準證據（v1.4-evidence-2）

本交付是證據資料與回歸測試，**不是可製造能力註冊，也未核准任何絕對 X**。JSON：`docs/receiving-nfb-x-evidence.json`。每個 `rule_id` 是可追溯的證據身份；`revision` 是證據版本，**不等於**實體 owner 核准的 `certified_x_revision`。

需求 owner 為使用者提供的兩份 `docs/specs/*20261010_v1.4.md`；JSON 固定其 SHA256 與引用章節。規格原檔及客戶原始大圖不納入此交付。

| 組合 | 已核准相鄰名義距離 mm | 目前 X 結論 |
| --- | --- | --- |
| W600×1、W750×1、W800×1 | 未定 | 僅預覽；禁止猜 W/2 |
| W600×2 | 180 | 僅預覽；起點、方向、原點與物理映射待證 |
| W750×2 | 310 | 僅預覽；起點、方向、原點與物理映射待證 |
| W800×2 | 325 | 僅預覽；起點、方向、原點與物理映射待證 |
| W800×3 | 180、180 | 僅預覽；已取得原圖並核對局部 X，CUTTING 身份與箱體映射待核准 |

未列組合亦僅預覽。單顆未核准不阻止多顆獨立取證；每組均須自己的證據，不互相外推。

## W800/T2 三孔：已知與缺口

內門實體契約固定箱身淨寬 796、成品寬 689、下料 CUTTING 寬 723 mm。測試直接量測既有內門製造 API 的 CUTTING 外輪廓，避免只比 metadata。

規格記錄三孔從圖面左邊量得 181.5／361.5／541.5，相鄰距離為 180／180；其數學中點 361.5＝723/2。使用者補充的 `800x3.dxf` 已提供對應原圖，SHA256 `2e3143124a4bd81394143a12b464d78dd030f479c0da2d02279b1dd502ad4416`。左側 LINE `A1` 的 X=5292.99589、右側 LINE `A0` 的 X=6015.99589，相距 723。三組主孔的左右側邊中點 X=5474.49589／5654.49589／5834.49589，減去圖面左側 X 得 181.5／361.5／541.5，與規格觀測相同。`tests/fixtures/receiving_nfb_w800_three_source.json` 保留原圖相關 LINE 的座標及 handle，golden 測試從這些真實圖元重新量測，不用全圖 bbox 定孔心。尚未證明圖面左邊就是該 723 mm 下料 CUTTING 左緣，也未核准下料→成品面→箱體世界 X 的可逆映射。JSON 對所有方向、原點、映射、part ID 與核准版本保留 null，不能作已認證規則消費。

## 已排除的真 DXF 反例

RC 唯讀原圖 SHA256 `e65e77ffa676defc0c16eeed6f1eb808f41cdbe8bc100f0ab8f4e5d0cb6c191c` 的 DIMENSION `30F001`／`30F01D` 具有 90° 尺寸方向，量測值約 361.5063 mm。它們的標註文字包含 361.5，卻是 Y 尺寸，鄰近外框 `3083F9` 為 650×850 mm，不能當作 W800×3 的橫向孔心。

`tests/fixtures/receiving_nfb_x_negative_source.json` 僅保存必要 handle、尺寸定義點、方向與量測值，不含完整客戶圖。測試從定義點及方向重新計算投影，證明文字搜尋本身不能認證 X。

初步 723 寬 LWPOLYLINE 搜尋亦不能取代外框重建：圖可能以 LINE／ARC／INSERT 組合。未找到不能宣告整批原圖不存在對應內門。

## 出場缺口與下一步

1. **已完成**：使用者提供 `800x3.dxf`，已核對原圖左右側間距與三孔局部 X。
2. **待核准**：來源 LINE／ARC／CIRCLE 為 layer 0／Color 7（DIMENSION 為 ByLayer），外框上緣未閉合，並非可直接交付的正式 CUTTING。需實體 owner 確認圖面 `A1` 就是內門下料 CUTTING 左緣、實際內門 part ID 與方向。原 DXF 不補線、不改色、不改寫。
3. 由實體 owner 核准該組的下料→成品→箱體 X 正反向映射與 rule/revision，再增加真原圖 golden 測例。
4. #1497／#1498 只可將取得上述核准的組別送能力註冊；Y 與 NFB 主孔型證據另由 #1495／#1496 提供，X 證據不代表整個 MFG-1 已通過。

**#1494 保持 OPEN。** 本次 partial evidence 不聲稱 AC-49／SWT-AC-30 的原圖同一性與箱體映射已通過，不允許正式 NFB 開孔、不改內門或其他產品幾何、不發布正式 X。

## 補充：沿用實體內門裝配的 X 投影檢查（shadow，不是製造核准）

測試使用既有 ae_engine.assembly_placement.resolve_inner_door_panel_placement() 與 ae_engine.cabinet_types.policy.derive_inner_door_panels()，沒有為 NFB 建立平行的箱體 X 起點。W800／T2／折邊 19／門縫 3.5 對應 inner_door:upper:panel，成品寬 689、正式生成封閉 CUTTING 下料寬 723，裝配 anchor 為 inner_door_frame_opening:upper。

來源 800x3.dxf 的 LINE A1（X=5292.99589）及 A0（X=6015.99589）水平相距 723；這僅證實圖面幾何寬度。原圖圖層 0／ACI 7，不是已分類及閉合的正式 CUTTING 輪廓；相同寬度不等於 A1 已認證為 CUTTING 左緣。

以下**只是一組條件式可逆影子公式，不是製造公式**：令 S=來源 DXF x，L=A1 x，B=內門 unfolded_width=723，P=既有 resolve_inner_door_panel_placement().world_offset.x。只有在 A1 的正式下料身份、來源與展開 X 同向、孔位位於合法核心面、折後映射保留本投影都獲正式證實後，候選 X_shadow = P + (S-L-B/2)，逆算 S=(X_shadow-P)+B/2+L。

回歸獨立驗證：單柱 W800 時 P=0，左側另有 W400 柱時 P=200；三孔影子 X 分別為 [-180,0,180] 與 [20,200,380]，逆算回到真原圖 handle 中心。這些影子世界值**不可**寫入正式證據 JSON 的 box_world_centers_mm；測試永遠確保 certified_x_revision=null、box_world_centers_mm=null、逐組 x_status=PREVIEW_ONLY。

**待補實證／核准：** 真實來源 A1 → 程式生成 CUTTING 左邊的同一性、內門下料 UV → 成品核心面 → 既有箱體裝配 X 的方向與正反映射，以及實際 NFB 主開孔型號幾何，全部須由實體 owner 核准 rule/revision。#1494 在此之前只有證據與 shadow 回歸，不能將此輸出視為 #1497/#1498 可製造能力。
