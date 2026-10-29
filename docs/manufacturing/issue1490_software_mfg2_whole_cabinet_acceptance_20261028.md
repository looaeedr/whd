---
whd_doc_role: CURRENT
whd_contract: issue1490-source-certified-software-mfg2-whole-cabinet
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #1490 完整軟體製造驗收 — 來源認證整櫃 DXF

## 結案範圍
#1490 軟體出圖／製造 MFG-2 僅以現行受電箱真實來源和實體板件為驗收依據。
工廠操作員的 NC 特定機台代碼、焊接工人手藝／設備校正不能由無機型端點的軟體憑空認證；它們**不作為 #1490 整櫃軟體 DXF 的結案阻擋**，也不得在 receipt 宣稱已取得機台或工廠放行。

## 必須直接執行的 MFG-2 軟體驗證
- 使用當前提交且來源 PIN 的 NFB 數值 CSV V5、內門、所有真實 Base 層和 EAR/PAD，以及同一 FinalScene。
- 完整出圖需包含原場景全部已安裝的物理板件（箱身側板／背板、head、divider、門框／門板、每層底板等），加上由來源驗證得出的實體 EAR/PAD；不得以僅勾選 BODY/DOOR/BASE 就聲稱整箱所有板件已輸出。
- 必須先完成已存在的來源 ID、CSV、NFB 孔、切割輪廓、折彎站、signed EAR、實體 Z 接觸、side UV MARKING、PAD full-T seating／碰撞驗證。任何缺口立即 fail-closed，不能以 metadata manufacturing_ready=true 跳過。
- 原子寫入每份 DXF；先以 ezdxf 讀回和原場景比對（既有 verify_saved_part_render_data_dxf 與 MARKING UV）；建立一份帶原樣本 SHA256／每份 DXF SHA256／板件對應／數量、台灣時區以外不強制當下時間的不可改竄收據；與全部 DXF 原子一批提交。
- 允許一般選取少量板件合法出圖，但不頒發「整櫃軟體製造認證」。UI 完整勾選時自動出具整櫃收據，沒有新增按鈕。
- 凡來源有失效、漏選、輸出檔案讀回失敗、碰撞接觸 fail，整批不可留下成功收據或半套 DXF；不能關掉 generic MFG2／NC 避險守衛。

## 負向實證
1. 正常 W800 一層來源全選 + PAD -> 一整套 DXF + JSON 收據，逐檔 SHA256 驗證。
2. 合法同深度／雙層沒有 PAD 時，PAD 件數可以是 0（不能硬塞）。
3. 漏 HEAD 或 divider 等已安裝實體，即使 BODY/DOOR/BASE 已選，完整 MFG2 驗收應 fail closed，但原先「部分出圖」仍可合法。
4. 第二層 Base/PAD 來源、EAR 真 Z、MARKING、DXF 讀回錯誤全部 fail closed。
5. 不開放 NC machine sink、不改工藝認證、不發布正式 X；新分支經 exact HEAD CI 才合入 GitHub localX。
