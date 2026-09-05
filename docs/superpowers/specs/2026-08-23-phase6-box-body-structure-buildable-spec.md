# Phase6 箱身多結構型態 Buildable Spec

版本：2026-08-23 16:28（Asia/Taipei）  
狀態：ready-for-agent  
來源：已確認之箱身結構規格、CONTEXT.md 與本輪設計決策

## Problem Statement

Phase6 目前以一體成型箱身為主要既有結構，但實際產品存在正式的二件式與兩種三件式箱身。這些型態有些由型號／產品規劃直接指定，有些則在板材料幅不足時使用。現有系統需要在不破壞一體式既有行為的前提下，把多件式提升為正式領域模型，而不是以 UI 特例或 3D 特例補丁處理。

使用者需要能在「箱身」頁面中查看型號預設的結構型態；預設鎖定且隱藏進階細項，需要時可解鎖，在一體成型、二件式（W 二分）、三件式（W 三分）、三件式（側背分離）之間自由切換並即時比較。每種型態的設定必須獨立保留。

多件式的核心風險不是只有畫面分件，而是完整資料鏈一致性：分件尺寸、Fold Chain、BEND、十字截角、底板避讓、開孔切割、2D、3D、儲存／重載、DXF、NC 必須由同一份 Source of Truth / resolved geometry 驅動。任何一層自行重算都可能造成畫面正確但加工錯誤。

## Solution

在既有一體式箱身幾何之上建立正式的箱身結構型態模型，讓「分件」成為 resolved geometry 的一部分。

一體成型維持既有行為。二件式（W 二分）只拆中央 W；三件式（W 三分）把中央 W 拆成 W左／W中／W右；三件式（側背分離）則把原本連續箱身拆成左側板、後面板、右側板。各型態有自己的尺寸控制與狀態，但全部共用既有箱身的板厚、D、W、實際高度、FW／Z Fold Chain、封頭／封尾與底板幾何來源。

箱身頁面預設只顯示型態摘要與鎖定狀態。解鎖後才顯示型態選擇與該型態專屬參數。型態切換只切換 active configuration，不清除其他型態的歷史值。

多件式幾何由單一 resolved geometry 層輸出完整板件集合、成型尺寸、展開尺寸、BEND、CUTTING、截角與孔幾何。2D、3D、DXF、NC 與存檔皆消費這份已解析結果或同一來源狀態，不各自發明規則。

## User Stories

1. 作為操作人員，我希望型號帶入箱身結構型態後預設鎖定，避免誤改原規劃結構。
2. 作為操作人員，我希望鎖定時隱藏多件式細項，讓箱身頁面保持乾淨。
3. 作為操作人員，我希望需要比較或改製時可以主動解鎖箱身結構。
4. 作為操作人員，我希望解鎖後可以在一體成型、W 二分、W 三分、側背分離四種型態間自由切換。
5. 作為操作人員，我希望切換型態後原型態的設定仍被保留，方便即時比較。
6. 作為操作人員，我希望回到先前型態時恢復最後一次使用值，而不是重新套預設。
7. 作為操作人員，我希望一體成型維持現有幾何與加工結果，不因新增多件式而退化。
8. 作為操作人員，我希望二件式只拆中央 W，左右既有 D／FW／Z 結構保持原樣。
9. 作為操作人員，我希望二件式的 W左與 W右任一側都可輸入，另一側自動補足。
10. 作為操作人員，我希望二件式始終維持 W左 + W右 = W。
11. 作為操作人員，我希望二件式單邊 W 最小為 50 mm，避免無效板件。
12. 作為操作人員，我希望第一次切換到二件式時自動對半，減少輸入工作。
13. 作為操作人員，我希望 W 為奇數時系統能合法產生 0.5 mm 對半結果。
14. 作為操作人員，我希望人工輸入 W 分配時只接受整數，避免任意小數。
15. 作為操作人員，我希望系統自算的 0.5 mm 能完整保留到加工輸出，不被偷偷取整。
16. 作為操作人員，我希望二件式中央兩側都有向箱內的 90° 接合折邊。
17. 作為操作人員，我希望中央接合折邊預設 12 mm，且可調但不得小於 12 mm。
18. 作為操作人員，我希望二件式左右接合折邊連動，避免兩側輸入不一致。
19. 作為操作人員，我希望接合折邊調到 50 mm 以上時收到警告，但仍可繼續操作。
20. 作為操作人員，我希望接合折邊計入各板件展開尺寸，但不改變包外 W 分配。
21. 作為操作人員，我希望二件式組裝後 W左與 W右外表面共面，不產生搭接高低差。
22. 作為操作人員，我希望封頭端的中央接合折邊依封頭實際 ybottom1 產生正確端部十字截角。
23. 作為操作人員，我希望封尾端依封尾自己的 ybottom1 計算，即使上下 ybottom1 不相同也正確。
24. 作為操作人員，我希望封頭／封尾十字截角的額外避讓預設 +5 mm 且可調。
25. 作為操作人員，我希望十字截角單邊留肉預設 0.5T 且可調。
26. 作為操作人員，我希望上下端使用同一組避讓與留肉設定，差異只來自實際 ybottom1。
27. 作為操作人員，我希望底板折彎跨過中央接縫時使用正確十字截角，而不是把整條折彎縮短。
28. 作為操作人員，我希望底板十字避讓總長預設 20 mm 且可調。
29. 作為操作人員，我希望底板避讓總長以交會中心對稱分配。
30. 作為操作人員，我希望底板十字截角單邊留肉預設 0.5T 且可調。
31. 作為操作人員，我希望既有後面板孔若被二件式切線切到就照切，不自動移孔。
32. 作為操作人員，我希望跨切線孔自然分配到左右獨立板件，各自輸出加工幾何。
33. 作為操作人員，我希望三件式（W 三分）仍只拆中央 W，不改左右既有 D／FW／Z。
34. 作為操作人員，我希望 W 三分預設為 50 / (W-100) / 50，以便常見板材不足情境直接避開底板。
35. 作為操作人員，我希望 W 三分的 W左與 W右始終連動相等。
36. 作為操作人員，我希望修改 W左或 W右時另一側同步，中間 W 自動補足。
37. 作為操作人員，我希望直接修改 W中時左右自動平均補足。
38. 作為操作人員，我希望 W 三分沿用 W 二分相同的接合折邊規則，不需要學第二套操作邏輯。
39. 作為操作人員，我希望 W 三分兩條接縫的接合折邊全部連動。
40. 作為操作人員，我希望 W 三分的封頭／封尾端部十字截角隨實際接縫位置移動。
41. 作為操作人員，我希望 W 三分預設左右 50 mm 已避開底板時不要多做不必要的底板截角。
42. 作為操作人員，我希望若調整 W 三分後接縫實際進入底板折彎交會區，系統依幾何自動處理，而不是只看模式名稱。
43. 作為操作人員，我希望三件式（側背分離）由左側板、後面板、右側板三個獨立板件組成。
44. 作為操作人員，我希望左右側板成型深度仍等於 D。
45. 作為操作人員，我希望左右側板後側沿整個箱高增加一折，預設 15 mm 且可調。
46. 作為操作人員，我希望新增後折不改變側板 D 的成型尺寸定義。
47. 作為操作人員，我希望後面板放置在左右側板新增後折的上方。
48. 作為操作人員，我希望後面板成型寬為 W 減去可調補償量。
49. 作為操作人員，我希望後面板寬補償預設 0.5T 且可調。
50. 作為操作人員，我希望側背分離三片板共用既有箱身解析後的實際高度，不因分件各自重算高度。
51. 作為操作人員，我希望箱身結構所有設定都集中在既有「箱身」頁面，不散落到全域設定或其他頁面。
52. 作為操作人員，我希望不同型態只看到對應欄位，避免看到無意義的 W左／W中／W右或其他參數。
53. 作為操作人員，我希望進階截角／避讓參數預設可收合，不佔滿主要操作區。
54. 作為操作人員，我希望調整任何多件式尺寸後 2D 與 3D 立即反映同一結果。
55. 作為操作人員，我希望接合折邊過大警告在設定面板、2D、3D 同步呈現。
56. 作為操作人員，我希望存檔保存實際值而不是保存暫時 warning flag，重載後重新依規則判斷。
57. 作為操作人員，我希望每個獨立板件都有自己的 2D／DXF／NC 加工結果。
58. 作為操作人員，我希望孔、BEND、CUTTING、十字截角與展開尺寸全部來自同一份幾何解析結果。
59. 作為維護者，我希望一體式和多件式共用既有 D／W／H／T／FW／Z 等 Source of Truth，不建立互相漂移的重複尺寸。
60. 作為維護者，我希望多件式功能有完整回歸測試，確保修改 GUI 或 3D 時不會破壞 DXF／NC。

## Implementation Decisions

### 1. 箱身結構型態為正式領域狀態

建立四種正式型態：

- 一體成型
- 二件式（W 二分），建議內部識別 `TWO_PIECE_W_SPLIT`
- 三件式（W 三分），建議內部識別 `THREE_PIECE_W_SPLIT`
- 三件式（側背分離），建議內部識別 `THREE_PIECE_SIDE_BACK_SPLIT`

型態不得由板材尺寸臨時計算結果隱式決定。型號／產品規劃可帶入預設型態；板材不足也可促使使用者切換型態，但兩者都是正式型態來源。

### 2. 鎖定與 active configuration 分離

鎖定只是防誤改狀態，不代表型態永久不可變。型號帶入時預設鎖定；解鎖後四種型態全部可選。

每種型態保存自己的 configuration。切換 active type 只改目前生效型態，不清除其他 configuration。

### 3. 測試 seam / 幾何 seam

首選且最高層 seam 為「箱身結構 state + 既有箱體 Source of Truth → resolved box-body geometry」。

這個 seam 應一次解析出：

- active structure type
- 獨立板件集合與板件角色
- 各板件成型尺寸
- 各板件展開尺寸
- Fold Chain / BEND
- CUTTING / relief / 十字截角
- 開孔裁切後幾何
- 2D/3D 所需定位資料
- DXF/NC 可消費的加工幾何
- warning facts（例如接合折邊 >= 50），但 UI 呈現狀態不持久化

2D、3D、DXF、NC 不得各自重新推導多件式規則。

### 4. 一體式零退化

一體成型必須繼續使用現有 Fold Chain 與輸出邏輯。新增 structure resolver 時應提供與既有一體式等價的 resolved result，或在可驗證的相容層維持原輸出；不得為了多件式重寫一體式幾何造成不必要 blast radius。

### 5. 二件式（W 二分）只拆 W

原一體式中央 D-W-D 中，兩側 D 完整保留；左右既有 FW／Z 也各自完整留在自己的板件。只把 W 解析為 W左與 W右。

約束：

- W左 + W右 = W
- W左、W右人工輸入皆可作為驅動端
- 任一側人工修改後另一側自動補足
- W左、W右各 >= 50 mm
- 初次無歷史值時 W/2、W/2
- 人工輸入只接受整數
- 系統計算允許 .5 mm，且不得在後續資料鏈取整

### 6. 二件式中央接合折邊是一般 BEND

每個切口兩側各新增向箱內的 90° BEND。

參數：

- 預設 12 mm
- 最小 12 mm
- 可調
- 左右連動
- 無硬上限
- >= 50 mm 產生 warning fact，但不阻擋解析或輸出

接合折邊不屬於 W 包外尺寸；必須加入各板件實際展開尺寸。

焊接只描述製造目的，不新增特殊幾何類型，不新增焊接 MARKING，也不建模焊縫間隙。

### 7. 封頭／封尾端部使用十字截角 resolved geometry

中央縱向接合折邊與封頭／封尾是不同板件。此處的截角是為組裝空間避讓，不應實作成「同一板件兩條 BEND 線相交」。

上端使用封頭實際 ybottom1；下端使用封尾實際 ybottom1。

共用參數：

- 額外避讓預設 +5 mm，可調
- 單邊留肉預設 0.5T，可調

上下兩端參數連動，實際幾何差異只由各自 ybottom1 產生。

這必須產生真正 CUTTING / relief 幾何，同時修正 BEND span；不得只在 3D 隱藏或縮短視覺線段。

### 8. 底板交會使用同一十字截角概念

底板折彎在組裝後位於後面板表面，與 W 分件接縫在實際交會時需要局部十字截角。

參數：

- 避讓總長預設 20 mm，可調
- 以交會中心對稱分配，預設前後各 10 mm
- 單邊留肉預設 0.5T，可調

不得以縮短整條底板折彎取代局部截角。

是否需要底板截角必須由實際 resolved geometry 交會判定；不能僅依 structure type 開關。

### 9. 開孔先存在，再被板件分割自然裁切

多件式不得重新排孔。既有孔幾何先依原 Source of Truth 解析，再與實際板件 CUTTING 邊界求交／裁切：

- 完全在某板件內：歸該板件
- 跨分件線：照切成多個板件結果
- 不移孔
- 不禁止切線
- 不為多件式建立另一套孔座標 Source of Truth

加工輸出使用各獨立板件局部結果。

### 10. 三件式（W 三分）重用 W 分件模型

W 解析為 W左、W中、W右，左右既有 D／FW／Z 不變。

預設：

- W左 = 50 mm
- W右 = 50 mm
- W中 = W - 100 mm

控制：

- W左 = W右
- 改 W左或 W右 → 另一側同步，W中補足
- 改 W中 → W左 = W右 = (W - W中) / 2
- 人工輸入整數；系統結果可 .5

不得自行加入 W中 >= 50 mm 規則；目前未確認 W中 額外最小值。

所有接合折邊沿用二件式同一組參數與 warning 規則，全部連動。兩條接縫的封頭／封尾十字截角由各自實際位置解析。

預設左右 50 mm 的目的之一是讓接縫通常避開底板，因此底板局部截角只在 resolved geometry 實際交會時產生。

### 11. 三件式（側背分離）是另一種拓撲

板件固定為：左側板、後面板、右側板。

左右側板：

- 成型深度 = D
- 後側沿整個箱高增加一個縱向 90° 折邊
- 預設 15 mm，可調
- 額外折邊不改變 D 的成型定義

後面板：

- 放置在左右側板新增後折的上方
- 成型寬 = W - compensation
- compensation 預設 0.5T，可調

三片板的高度沿用既有箱身解析後的實際高度；不得建立獨立的後面板 H 公式。

### 12. GUI 僅屬於箱身頁面

箱身結構相關設定不得放入全域設定，也不得開新頁。

鎖定時：

- 顯示目前型態摘要與鎖定狀態
- 隱藏型態編輯與細項參數

解鎖後：

- 顯示型態選擇
- 顯示 active type 專屬主要尺寸
- 進階截角／避讓參數以可收合區呈現

二件式顯示 W左、W右、接合折邊與進階截角參數。

W 三分顯示 W左、W中、W右、接合折邊與共用進階截角參數。

側背分離顯示側板後折、只讀 D、後面板補償與即時計算後面板寬；不得顯示 W左／W中／W右。

### 13. warning 是 derived fact，不是持久化 UI state

接合折邊 >= 50 mm 時 resolved result 產生 warning fact。設定面板、2D、3D 各自呈現同一 fact。

存檔只保存接合折邊實際數值。重載後重新解析 warning；不得存 warning boolean 作為 Source of Truth。

### 14. 儲存／重載契約

專案保存至少需要完整重建：

- active structure type
- lock state（若現有專案格式持久化 UI/編輯鎖狀態）
- 各型態自己的 configuration
- 所有可調截角／避讓參數

派生值（W 補全結果如可由保存輸入穩定重算、warning、resolved geometry、2D/3D cache）不應成為獨立 Source of Truth；若為相容性需要持久化，重載後仍必須經 resolver 驗證／正規化。

### 15. 輸出契約

每個 resolved 板件獨立輸出：

- CUTTING
- BEND
- 原既有 MARKING / DATUM 等非本功能新增層
- 開孔裁切結果
- DXF
- NC（適用時）

不得在輸出階段才根據 structure type 臨時切板；分件結果應在輸出前已是正式板件幾何。


## 程式查核補充決策（2026-08-23 16:58 Asia/Taipei）

以下決策來自目前 Phase6 source code 查核。標記「既有程式直接證據」者可視為相容性契約；標記「由既有 convention 約束」者表示新拓撲尚無舊實作，但不能違反現行資料／尺寸語意。

### A. Legacy `.p6fold` structure migration【既有程式直接證據】

- 現行 `phase6-fold-project-v1` 只驗證 snapshot 容器，不要求固定 snapshot key；目前 GUI restore 也以 optional key / fallback 方式相容舊資料。
- 舊專案沒有 `box_body_structure` 時，解析為**一體成型**，以保存舊版連續 D-W-D Fold Chain 的物理結果；不得依目前型號新預設回溯改成多件式。
- 缺少 structure lock 時，只在 migration 當下沿用現有 model editability convention：已知基準型號預設 locked；`自訂`／legacy `未知類型` 預設 unlocked。
- 新版本一旦保存 explicit active type / lock / per-type configuration，重載後必須使用保存值，不重新從 model 推導覆寫。

### B. Manual W edit validation【既有程式直接證據】

沿用現行多門尺寸 commit 行為與幾何 validator 原則：

- 人工輸入 commit 時驗證。
- 不合法時拒絕該次輸入、恢復上一個 committed 合法值並提示；**不得 silent clamp**。
- W 二分若補算後任一側 `<50`，該次人工輸入無效。
- 人工來源必須是整數；resolver 自己補算出的 `.5` 合法。
- resolver 對 corrupt/direct-API invalid state 必須拒絕產生 manufacturing geometry。

### C. Cross RETAIN / 單邊留肉語意【既有程式直接證據】

- 既有正式表示為 `CornerTypeId.CROSS + CrossCornerMode.RETAIN + CornerDirection + amount_t`。
- 「單邊」指**局部 WIDTH 或 HEIGHT 軸**，不是左／右 mating panel ownership。
- W split endcap/base-plate relief 應重用同一 semantic；0.5T 表示 `amount_t=0.5`。
- corner 的左／右／上／下鏡射由 geometry placement 處理；若 adapter local axes 旋轉，只轉換 `CornerDirection`，不得新增 left-owner/right-owner 規則。

### D. T-relative parameter persistence【既有程式直接證據】

- 既有 Relief/CornerType 保存 factor / `amount_t`，解析時乘目前 T。
- 本功能的 `0.5T` 可調值也遵循此契約：保存 dimensionless T factor，不保存當下 resolved mm 作為 Source of Truth。
- 包含 endcap retain、base-plate retain、side/back rear-panel compensation。

### E. Side/back assembly envelope【由既有 convention 約束；新拓撲無直接舊實作】

目前 source tree 查無 `THREE_PIECE_SIDE_BACK_SPLIT` 既有 assembly transform。現行可確定的是：

- BoxBody user-facing face dimensions 是 outer dimensions：left/right = `(D,H)`、back = `(W,H)`；厚度補償在 manufacturing/unfolded boundary 才套用。
- 因此側背分離完成後，成品外部 envelope 仍必須是同一 W/D/H；15 mm 後折不能把 formed D 改成 D+15，也不能因板厚疊放把外深變成 D+T。
- rear-panel compensation 保存為 T factor；resolved total compensation `c = factor*T`，finished rear width = `W-c`。
- 預設 assembly 應保持原 back-face centerline；因此 total compensation c 以中心對稱方式在左右各退 c/2。此項必須以新 resolver golden geometry 驗證，若未來真實基準檔有不同證據再修正。
- 不得在 2D、3D 或 export 階段另外猜 D±T transform；resolved assembly result 必須一次提供各板件 transform/reference plane。

### F. Operation-aware feature clipping【既有程式直接證據】

既有 drawing/material pipeline 已區分 `CUTTING / BLIND_HOLE / MARKING / DATUM`，且 material subtraction 只接受 CUTTING。因此多件式 clipping 必須：

- CUTTING：裁到各 part material boundary 後仍為 CUTTING。
- BLIND_HOLE：裁 linework/contour，但仍為 BLIND_HOLE，不得升級為 CUTTING。
- MARKING/DATUM：保留原 layer；不可用 seam 補成假封閉 cutting contour。
- `ProfileFeature.layered_profiles` 各 sub-layer 分開 clip 並保留 layer。
- feature position/source state 不因分件而搬移或複製成第二套 Source of Truth。


## Testing Decisions

### 測試原則

測試外部可觀察行為，不鎖死內部函式分解。優先從最高層的 box-body resolver seam 驗證「給定 state 與既有箱體尺寸，得到哪些板件與幾何」。

對真正輸出風險，再以少量端到端 golden tests 驗證同一 state 在 2D/3D/DXF/NC 的一致性。避免為每個 UI callback 寫脆弱單元測試。

### Resolver 行為測試

至少覆蓋：

1. 一體式輸出與既有基準完全等價。
2. 二件式 W=1200 初次解析為 600/600。
3. 二件式 W=1201 初次解析為 600.5/600.5，後續不取整。
4. 二件式人工輸入左值時右值正確補足。
5. 二件式人工輸入右值時左值正確補足。
6. 二件式單邊 <50 被拒絕／正規化為無效輸入，不產生錯誤加工幾何。
7. 接合折邊 12、49、50、>50 的合法性與 warning fact。
8. 接合折邊加入展開但不改 W 包外總和。
9. 封頭／封尾 ybottom1 相同時上下十字截角一致。
10. 封頭／封尾 ybottom1 不同時上下截角各自依實際值生成。
11. +5 避讓參數修改後 CUTTING 與 BEND span 同步變化。
12. 0.5T 留肉修改後實際 relief 幾何同步變化。
13. 底板交會時產生 20 mm 對稱局部截角。
14. 底板避讓總長修改後仍以中心對稱。
15. 底板未實際交會時不產生多餘截角。
16. 孔完全在單一板件時完整保留。
17. 孔跨二件式切線時被裁成左右幾何，不移孔。
18. W 三分預設為 50/(W-100)/50。
19. W 三分改左／右時左右連動、中間補足。
20. W 三分改中間時左右平均補足，可出現系統 .5。
21. W 三分兩條接縫沿用同一接合折邊設定。
22. W 三分預設接縫避開底板時不產生底板 relief。
23. W 三分調整後若實際交會底板，依 geometry 產生 relief。
24. 側背分離左右側板成型 D 不因 15 mm 後折改變。
25. 側背分離後面板寬 = W - compensation。
26. compensation 修改後成型寬與 2D/3D 同步。
27. 三片側背分離板件高度等於既有 resolved box-body height。

### 狀態與 GUI 行為測試

至少覆蓋：

1. 型號帶入後預設鎖定且細項隱藏。
2. 解鎖後四型態可選。
3. 切換型態不清除其他型態 configuration。
4. 返回先前型態恢復最後設定。
5. 鎖回後 active type 保留但細項不可編輯／隱藏。
6. 側背分離頁不顯示 W左／W中／W右。
7. W 二分／W 三分顯示正確專屬欄位。
8. >=50 warning 同步出現在設定、2D、3D，但操作不被阻擋。
9. 存檔／重載後 warning 由數值重新推導而不是讀舊 flag。

### 輸出與回歸測試

建立代表性 golden cases，對同一 state 驗證：

- resolved 板件數量與角色
- 2D 板件輪廓
- 3D 組裝位置與外表面共面
- BEND 位置／長度
- 十字截角 CUTTING
- 孔裁切結果
- DXF 實體／圖層語意
- NC 路徑（適用時）
- 儲存後重載輸出等價

至少保留一組既有一體式 golden case 作為零退化門檻。

### Prior Art

優先沿用專案現有的：

- Fold Chain / resolved geometry 驗證方式
- 2D/3D 同源幾何測試
- DXF/NC golden data / regression tests
- 既有封頭／封尾 CornerType、十字截角與單邊留肉測試語意
- 基準檔開孔與板件輸出的回歸檢查

若現有測試 seam 無法直接驗證多板件 resolved result，新增 seam 應位於 box-body geometry resolver 層，而不是為每個 renderer 建新的測試 API。

## Out of Scope

本規格明確不包含：

- 焊接工法設計
- 焊縫間隙
- 焊接線或額外 MARKING
- 焊接順序與治具
- 中央接合折邊除已確認十字截角之外的 45°、圓角或其他端部 relief
- 未確認的 W中 額外最小值
- 因極端尺寸而自行發明的上限限制；接合折邊只有 >=50 warning，不設上限
- 自動依板材料幅強制替使用者選擇型態的完整最佳化演算法
- 新的全域設定頁或新的箱身專用頁面
- 對既有封頭／封尾、底板、開孔領域模型做與本功能無關的重構

## Further Notes

- 「焊接」在本規格只描述接合目的；幾何上仍是普通 BEND。
- W 二分與 W 三分的接合／截角應盡量共用同一 W-split primitive，避免複製規則。
- 側背分離是另一種拓撲，不應勉強塞進 W-split 的數學模型；可以共用更高層的 resolved panel interface。
- 底板是否需要十字避讓必須由實際幾何交會判斷。三件式 W 三分預設左右 50 mm 是常見可避開底板的配置，但不是關閉底板 relief 的硬編碼旗標。
- 人工輸入整數與系統計算 .5 是兩種不同來源，驗證層必須區分，不能讓 UI validator 否決 resolver 自己合法算出的 .5。
- 任何實作若只改 3D、只改 GUI、或在 DXF export 階段才切板，都不符合本 spec。
- 完成本 spec 後，再使用 `to-tickets` 拆成 tracer-bullet tickets；tickets 應依 resolver / W 二分 / relief / W 三分 / 側背分離 / GUI+全鏈驗證等垂直能力拆分，而不是依檔案或技術層水平拆票。


### G. Global W commit reconciliation【本輪 code-audit hardening 補充】

- strict resolver 對 contradictory saved/direct state 維持 fail closed。
- 正常 GUI 修改 enclosure W 時，在 settings commit seam 依 W 二分／W 三分最後 driver 重算補全值，再提交新的 structure state。
- 若新 W 無法滿足該型態合法條件，拒絕該次 W 並恢復上一個 committed 合法值；不得把 corrupt state 留給 renderer，也不得在 resolver silent repair。
