# OVERLAY FW Width Invariant Correction — SUPERSEDED

> **本文件曾把 nominal/material FW=25 直接當成裝配避讓量，得到 25/350。這已被實際 formed-FW 組裝驗證推翻，不再是現行契約。**

## 歷史錯誤

`金庫型貼外.p6fold` 的 EndCap nominal FW 確實是 25，但箱身 FW 折彎後在接合面真正佔據的 formed width 不是 25。只用 `FW=25` 作上方 X CUT，會忽略箱身 Fold Profile 的 outside-dimension / bend occupation。

因此以下舊結論全部失效：

- 上方每側 U=25。
- 中央 span=350。
- `25+375=400` 作為裝配驗收式。

## 現行契約

現行 Source of Truth 是 **Box Body formed FW occupation**。fixture `W=400, T=2, nominal FW=25` 時 formed FW=29：

- 上方每側 U=29。
- 單側未截 run=371，因此 `29+371=400`。
- 左右都截後中央 span=342。
- Y 仍用 EndCap nominal FW25，標準值為 39。
- 下方 1.5T / T2 仍為每側 3、中央 394。

現行完整驗證：`docs/superpowers/verification/2026-08-29-formed-fw-registry-3d-relief.md`。
