# 截角資料庫－STANDARD 母規則說明

本資料庫決定「程式算什麼」。Skill 決定「AI 怎麼改」。兩條鏈分離：讀 Skill 不等於已更新資料庫；更新資料庫也不等於已完成 Skill verification。

## 啟動規則
- 修改 Corner / Relief / Assembly Intent / 3D backprojection 前，先讀本文件，再讀 `certified_relief_rules.json` 與 `certified_relief_rules.schema.json`。
- `ae_engine/certified_relief_registry.py` runtime HIT 時，Certified Rule 是 canonical 製造答案。
- Registry HIT 禁止在 production code 另寫第二套截角公式；Registry MISS 才可進 3D discovery / candidate flow。
- PROVISIONAL / candidate 結果必須附 3D shadow evidence 與 regression evidence，升級後才能進 Certified JSON。

## 尺寸語意
- 操作員輸入/看到的是包外尺寸；engine Fold Profile 的 `len` 是料尺寸。
- 折邊尺寸在討論時若未特別說「包外」，一律指料尺寸。
- `料尺寸 = 包外尺寸 - 實際相鄰折彎數 × T`。刪除折彎後必須重新判定。
- 「包外尺寸」是尺寸量法；「外側包覆 WRAP」是裝配語意，禁止混用。

## Certified Rule 必備 metadata
- `standard_ref`：引用哪一條 STANDARD 母規則。
- `affected_zone`：作用區段，例如 top FW band、bottom rear wrap zone。
- `dimension_space`：公式尺寸空間，限定 MATERIAL / OUTSIDE / FORMED_OCCUPATION。
- `target_semantics`：目標裝配語意，例如進入內緣、面齊、包覆保留。
- `adjustment_type`：STANDARD / INSERT / OVERLAY / INSERT_OVERLAY / WRAP。
- `adjustment_amount`：相對 STANDARD 的語意調整量，需保留單位與 basis。
- `topology_levels`：實際切刀階數，必須和 formula 一致。
- `certification_evidence`：認證證據、fixture、shadow validation 或 regression 記錄。
- `revision`：規則修訂版本；舊 revision 不可靜默覆寫。

## STANDARD
- STANDARD 永遠固定，所有 INSERT / OVERLAY / INSERT_OVERLAY / WRAP 只能相對它做 delta。
- 封頭尾上方：左右料折15、內邊框料16、FW料25，因此最內折線 STANDARD = **40×41**。
- 封頭尾下方：STANDARD = **15×15**。

## D200 / T2 範例
- 箱身包外 D=200。
- 封頭/尾成形包外 D=198 (= D-T)。
- 主面料尺寸=194 (= 198-2T = D-3T)。
- Y料鏈：16 + 25 + 194 + 15 = 250。
- STANDARD 在不同 X band 自然形成 194 → 196 → 198。

## OVERLAY 貼外
- 貼外的母語意是「面齊」。
- 上方 FW band 的 STANDARD 包外為196，目標面198，因此留肉1T。
- v3 certified geometry：**40×39 + 15×2**。
- formed FW 可以作診斷 evidence，但不得重新成為 CUTTING 公式輸入。

## INSERT 嵌入
- 嵌入的母語意是「進到對方內緣以下」。
- 從 STANDARD 的 FW band 做多切；INSERT 本身不是二級截角。
- 多切預設量若未經製造驗證，不得猜。

## Receiving 下方 WRAP
- 下方 STANDARD 永遠是15×15。
- WRAP 是獨立的下方局部面齊/包覆 Joint 語意，再從 STANDARD 衍生 L 型二級截角。
- 不得把下方母體改名成 INSERT_OVERLAY。
