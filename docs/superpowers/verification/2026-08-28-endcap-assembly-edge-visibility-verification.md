# 2026-08-28 EndCap 組合體孔／折彎稜線可視化驗證

## 問題
標準未修改金庫型的封頭／封尾在 physical-sheet 組合體中，孔、留肉附近折彎線與 `ytop1` 第一折看起來消失。

## 根因證據
- 標準 Head/Tail Fold Profile 仍為 X 2 + Y 3 = 5 道 BEND。
- `PartRenderData.material` 仍保留 baseline secondary CUTTING holes。
- `folded_mesh_from_polygon()` 的 mid-surface 仍含第一折非共面 shared edge。
- `thicken_triangle_surface()` 將 sheet 封成 closed solid 後，through-hole tunnel 與 fold crease 都不再是 open boundary；舊 renderer 因此不畫它們。

## 修正
`Phase6FinalSceneView` 對 EndCap physical solid 保留原本實體面，同時由**加厚前、已折好的 authoritative mid-surface**抽取：
1. 單鄰接 edge：外輪廓／through-hole 輪廓。
2. 多鄰接 edge：相鄰三角面法向非共面時視為真實 formed crease。
3. 共面 triangulation diagonal：排除。

## TDD
- RED：physical EndCap 有 through-hole 時，assembly 只剩 BoxBody 4 條 outline，沒有 EndCap hole boundary。
- RED：有第一折的 EndCap physical solid 只顯示 T 厚度側邊，沒有跨整片的 crease。
- GREEN：兩項測試均通過。

## 不變項
- 不改 CUTTING / material。
- 不改 Fold Profile / BEND 數量。
- 不改 CornerType。
- 不改 Head/Tail assembly transform。
- 不改 2D / DXF。

## 06:49 追加修正：孔 rim 不得停在 mid-surface
前一輪雖已從 folded mid-surface 抽孔輪廓，但實際 GUI 仍可能看不到，原因是該線位於 physical sheet 中心面，被 ±T/2 外皮與後方 BoxBody 深度遮蔽。

### 新修正
- 新增 physical-solid feature edge extraction：保留 boundary edge 與相鄰法向非共面的 shared edge，排除共面 triangulation diagonal。
- EndCap 組合體改從 thickened solid 額外畫 physical feature edges，因此 through-hole rim 位於可視 skin，不再只在 z=0 中心面。
- 原 authoritative folded mid-surface crease overlay 保留作 fallback。
- 3D `BEND` guide 統一改為 solid `-`，linewidth 1.15，避免再以虛線顯示。

### TDD
- RED：要求 T=2 有孔平板的 hole rim 出現在 z=±1 physical skins；舊程式沒有 physical feature-edge API。
- GREEN：hole rim skin-edge 測試通過。
- RED：`_draw_scene_bends()` 仍輸出 `linestyle='--'`。
- GREEN：改為 `linestyle='-'` 後通過。

### 真 GUI 驗證
使用標準金庫型第一次進組合體啟動真 Tk/Matplotlib；Head 2 個固定孔、Tail 3 個固定孔均可由 physical rim 線辨識，且上／下折彎稜線以實線顯示。
