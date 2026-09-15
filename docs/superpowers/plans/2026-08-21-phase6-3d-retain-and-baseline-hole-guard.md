# 三維留肉折面歸屬與基準檔孔防護

## 目標

修正真實三維 CUTTING mesh 的兩個回歸：

1. `CROSS / 留肉` 角落留下的材料不可同時被兩個相交折彎帶走。
2. 目前型號基準檔中的 secondary `CUTTING` 孔必須和使用者新增孔一樣進入三維真洞。

## 留肉折面歸屬

`CROSS / RETAIN` 會在原本的角落 relief 內留下小段材料。這段材料雖位於兩個折邊座標範圍交界，但製造語意只屬於其中一側板面：

- 留肉方向為「寬」：材料屬於上／下折邊，不再套左／右 X 折彎。
- 留肉方向為「高」：材料屬於左／右折邊，不再套上／下 Y 折彎。

三維 bridge 先依 CornerType 產生 fold-exemption region，再把 material 沿 exemption 邊界切開後三角化，避免一個三角面跨越兩種折面 ownership。

這只修正三維折面歸屬；不改 `CUTTING`、`BEND`、DXF 或 CornerType 公式。

## 基準檔孔資料流

正式三維 material 改為：

```text
目前結構／CornerType CUTTING
+ 使用者新增 CUTTING
- 目前型號基準檔 secondary CUTTING
= 三維真實 material
```

基準檔只提供 secondary through-cut，不得覆蓋目前結構外框或折彎。

支援：

- `CIRCLE` CUTTING 孔。
- 封閉 `LWPOLYLINE` CUTTING 孔。
- 炸開成 `LINE`／open polyline 的封閉 CUTTING 迴路，以 polygonize 還原成孔。
- 基準 scene 同時存在「新公式外框」與「映射舊外框」時，兩個同 blank bounds 的結構外框都不會被誤判為孔。

## 資料來源

- 已知型號箱身：目前選定 baseline model 的 `箱身.dxf`。
- 已知型號封頭／封尾：`封頭尾.dxf`。
- 已知型號門：`門.dxf`。
- 指示燈盒／小門：既有 shared baseline resolver。
- 自訂模式沒有已知型號 baseline secondary holes，不做隱性 fallback。

## 永久 TEST

新增 `tests/test_phase6_3d_retain_and_baseline.py`，鎖住：

- 基準圓孔與炸開線孔會成為 through-hole。
- 重複結構外框不會被誤判成大孔。
- 目前 material 會扣掉 baseline secondary CUTTING。
- `CROSS / 留肉 / 寬` 產生 X-fold exemption。
- 留肉 tongue 不再收到 X fold transform。
- 正式 `_phase6_render_true_cutting_mesh()` 真的使用 baseline holes 與 fold exemptions。
- 目前 3D baseline model 會傳給 Door baseline reader。

