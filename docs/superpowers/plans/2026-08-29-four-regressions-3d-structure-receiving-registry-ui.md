# Phase6 Four Regressions Implementation Plan

**Goal:** 修正箱身 3D BEND、結構切換預設/即時 3D、受電箱下方截角 3D 真值鏈，以及截角資料庫繁中表單。

**Architecture:** 保持既有 Source of Truth。多片箱身的 3D 變換由單一 helper 同時供 mesh 與 BEND 線使用；結構切換先 materialize 該型態 canonical defaults 再 commit；受電箱多片箱身加入 Assembly Solver world-solid 路徑並把下方接合升格 Registry/3D shadow 驗證；資料庫表單只翻譯 display labels，不改持久化 ID。

**Global Constraints:** 不修改 config.ini；不建立第二套 UI-only 幾何；INSERT/OVERLAY/INSERT_OVERLAY 全回歸；2D/單板3D/組合圖/Save-Reload 一致。
