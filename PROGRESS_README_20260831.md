# Phase6 尺寸語意／STANDARD 截角－進度包

此包是使用者要求的「先給目前改好的」進度版本，**不是正式 Release FULL/UPDATE**。

## 已落入 production 的項目

1. Receiving 箱身操作員包外鏈會依實際 BEND topology 轉為 canonical material chain：
   - 包外：24 / 24 / 29 / 350 / 800 / 350 / 29 / 18
   - 料：22 / 20 / 25 / 346 / 796 / 346 / 25 / 16（T=2）
   - 讀回可無損還原包外鏈。
2. Receiving EndCap：
   - FW 29 包外 -> FW 25 料。
   - D350 -> EndCap D 主面料346（D-2T）；相鄰實際折彎只透過 `ui_len_add` 還原操作員包外尺寸，不改材料核心。
   - 讀回仍為 FW29 / D350。
3. Receiving 後面板補償：W - 2.5T。
4. Receiving 下方 Corner 母體固定 STANDARD；WRAP 由獨立 Joint/Registry 衍生。
5. Certified Relief contract 升 v3。
6. OVERLAY v3：STANDARD 40x41，FW band 留肉1T，最終 40x39 + 15x2。
7. formed FW 保留為診斷 evidence，不再作 OVERLAY 正式公式輸入。
8. 截角資料庫新增 STANDARD 母規則說明文件；完整母規則同步進個人AI檔案庫。

## 已做的最小 fresh 驗證

- py_compile：相關修改 Python 檔通過。
- Receiving box outside->material->outside：PASS。
- Receiving EndCap FW/D material/readback：PASS。
- Receiving back_width_comp_t=2.5：PASS。
- Registry v3 formula：40x39 + 15x2：PASS。
- git diff --check：PASS。
- config.ini SHA256 保持 canonical：5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d。

## 尚未完成

- 全專案 stale 說明/公式清掃。
- 全套 3D/Collision/Save-Reload regression。
- 正式 release FULL/UPDATE packaging gate。

因此這個包可以先給使用者檢查目前修正方向，但不能當正式生產交付包。
