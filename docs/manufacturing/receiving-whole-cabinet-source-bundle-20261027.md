---
whd_doc_role: CURRENT
whd_contract: issue1490-source-verified-complete-sheet-bundle
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #1490：既有出圖路徑的來源驗證「完整板件圖包」，含實體 PAD

## 定義與邊界

- **不是新增操作按鈕**，不變更原 GUI 的「輸出所選板件」契約。原入口 `gui_modules/project/export_actions.py::_export_selected_resolved_parts` 預設只匯出所選的合法板件，不承諾整箱所有實體完整。
- `save_verified_receiving_formed_fixing_plate_bundle(..., require_complete_cabinet_inventory=True)` 為程式上的**嚴格來源完整性**請求，重用已存在的 current CSV V5 內門、實體底板、來源折後固定片、左右側板、3D 接觸、UV 打標，以及與 `PAD+Base PART_ONLY` 相同的 PAD 真實來源驗證器。
- PAD 只由現行 committed Set/Bay 的 `NFB數值規格.csv`、真實裝配 Base FinalScene、CUTTING 四個正方孔、展開折線與折後 PAD skin 推導，不能從板件計數、畫面上隨意複製或 `manufacturing_ready` flag 推導。
- PAD+Base 來源驗證共享 `ae_engine.receiving_nfb_pad_pair_manufacturing.verified_pad_base_physical_sheets`：同時檢查目前 CSV hole physical id、對應真實層 Base、PAD identity、四孔／兩條 BEND、全 T 接觸、後皮面與基座碰撞。嚴格圖包將已驗證的 **PAD 實體圖元**加入原本的 DXF 原子 staging，重新開檔比對，缺原始來源／幾何或失效時不得輸出半包。
- 已通過的 EAR 固定片原圖 T2、BEND23、焊接面世界座標與側板 MARKING，仍受 [當前固定片廠牌最大深度 Z 規則](receiving-fixed-ear-brand-max-z-20261026.md) 約束。淺型 NFB 不會把固定片改 Z。
- 不修改 `manufacturing_export.py` 的 generic MFG2 fail-closed，不把 PAD+Base 區域驗證當作**全廠牌/全箱裝配製造合格證**，**不宣告焊接工藝已通過**； `resolved_manufacturing_nc_capability()` 的 NC machine sink 仍尚未實作，不捏造設備格式。

## 回歸要求

1. 混深度士林現行 V5、真實來源 Base/EAR/SIDE/DOOR 選件：嚴格請求的 DXF 圖包 **包含 PAD**, 真實 PAD CUTTING/BEND，可由 `ezdxf` 重開，每件 ID 與選項來源相同。
2. 真實 Base Z / CSV 改動成為 stale：在寫入任何 DXF 以前報錯，禁止半包。
3. 僅選所選板件：保持既有輸出成功；嚴格請求在缺內門或底板時拒絕。
4. 單層、雙層、PAD 對應層與世界 Z/UV、不同 Bay 多連不得借用其他 Bay 證據。未通過不得合併，也不能宣告工單 #1490 結案。
5. 任何變更先從 GitHub `localX` 新分支，精確 HEAD Product CI，合回 `localX`；正式 `X` 只在使用者當次 `/推推` 後發布。
