# OVERLAY nominal-side-fold correction — SUPERSEDED

> 本文件記錄兩次已被推翻的中間結論：40/320 與 25/350。兩者都不是現行製造契約。

## 歷史錯誤 1：40/320

flat-X OVERLAY 曾把 legacy `nominal_yl1/yr1=15` 加入 X CUT，得到 `15+FW25=40`。這是把相容／編輯 metadata 混入 manufacturing CUTTING。

## 歷史錯誤 2：25/350

移除 nominal side 後又曾直接把 EndCap nominal FW25 當成裝配避讓量。這仍然錯，因為實體必須避讓的是**箱身折後 formed FW occupation**。

## 現行契約

`金庫型貼外.p6fold`：`W=400, T=2, nominal FW=25`，Box Body formed FW=29。

- 上方 U=29/側，中央 342；單側 `29+371=400`。
- 上方 V=39，仍由 EndCap nominal FW25 決定。
- 下方 U=3/側，中央 394。
- Certified Registry rule：`ENDCAP_TOP_OVERLAY_STANDARD_V1@2`，geometry input=`BOX_BODY_FORMED_FW`，X formula=`primary_u=mating_width`。

現行完整驗證：`docs/superpowers/verification/2026-08-29-formed-fw-registry-3d-relief.md`。
