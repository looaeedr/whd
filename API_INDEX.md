---
whd_doc_role: REFERENCE
whd_contract: project-reference
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# WHD API 功能、參數與連結速查表

> **自動更新的功能／參數網頁：[WHD API Explorer](https://looaeedr.github.io/whd/api/)**（GitHub Pages 的 Actions 來源必須已開啟）。每次 WHD `localX` 更新會自動重建網頁，不需再人工增加 API 列。
>
> 本檔目前是首版核對快照，**新增 API 請看自動重建的網頁或其 GitHub Actions `whd-public-api-catalog` artifact**；不要把手動快照當成即時完整清單。
>
> **先從這一頁查。** 這是「**每項功能 → Python 呼叫名稱 → 參數 → 回傳／範圍 → 實際程式連結**」的查詢入口。  
> 本頁 2026-11-01 依 `looaeedr/whd localX@af31a68e6af5c1e7edfa6e13b4a6c71d21938738` 實際原始碼核對；`localX` 持續更新，施工時仍應核對該分支最新函式簽名。
>
> **這不是 HTTP / REST / Swagger endpoint。** 現行正式入口是同一 Python runtime 中 `from ae_engine import ...` 或 `from ae_engine import manufacturing_api`。GitHub 連結是查詢原始碼／參數的網址，**不能直接用 URL 發送製造要求**。已退役的安裝版 Worker／EXE 及 source-only JSON/CLI 不提供任何外部製造操作。

- [查全部 Headless API 詳細說明](HEADLESS_API.md)
- [WHD × CADSplit v5.1 整合／能力分級 REFERENCE](docs/integrations/WHD_CADSplit_API_架構與權威整合_REFERENCE_v5.1.md)
- [CURRENT Engine 架構權威（AI 庫 04）](個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md)
- [WHD 全部公開製造函式原始碼](ae_engine/manufacturing_api.py)；[WHD 整合入口原始碼](ae_engine/integration_api.py)；[資料型別定義](ae_engine/contracts.py)

## A. CADSplit 接入：來源、查詢、已解析 Bay 的出圖

| 功能 | Python API／直接看程式 | 傳入參數（實際名稱） | 回傳／製造範圍 |
| --- | --- | --- | --- |
| **查有哪些 Family／Python 整合入口** | [`dispatch_manufacturing_integration`](ae_engine/integration_api.py#L75) | `ManufacturingIntegrationRequest(operation="capabilities", family=None)`；`family` 可選 | `ManufacturingIntegrationResponse`：`known_families`、`family_implemented`、`python_api_available`；**不代表可加工** |
| **準備 CADSplit 來源識別** | [`dispatch_manufacturing_integration`](ae_engine/integration_api.py#L75) | `ManufacturingIntegrationRequest(operation="prepare", family="受電箱", source=ManufacturingSourceIdentity(...))` | `SOURCE_ACCEPTED_NOT_MANUFACTURING_READY`；仍需 Engine 解算物理片，**不會出圖** |
| **外部 `export` 要求** | [`dispatch_manufacturing_integration`](ae_engine/integration_api.py#L75) | `ManufacturingIntegrationRequest(operation="export", family=..., source=...)` | `EXTERNAL_EXPORT_NOT_CERTIFIED`；**強制拒絕，不寫 DXF** |
| **Receiving 已解析 Set/Bay：逐片驗證後原子出圖** | [`export_verified_resolved_integration_bays`](ae_engine/integration_api.py#L180) | `bays: Sequence[ManufacturingResolvedBayInput]`、`output_dir: str \| Path`、關鍵字必填 `pre_commit_guard`、`overwrite=False` | `VerifiedIntegrationBatchExport`，含 `output_files` 與 `physical_dxf_roundtrip_verified=True`；**不等於整箱已認證** |
| **同一 Engine sink：已解析多 Bay 批次驗證出圖** | [`manufacturing_api.save_verified_resolved_manufacturing_geometry_batch_dxf`](ae_engine/manufacturing_api.py#L797) | `instances`（`(namespace, ResolvedManufacturingGeometry)` 配對序列）、`output_dir`、`pre_commit_guard` 必填、`overwrite=False` | `dict[str, str]`（製造 key → DXF 路徑）；每片 staged Save→Reload 後才提交 |
| **Receiving Set/Bay 來源輸出命名空間** | [`manufacturing_api.receiving_manufacturing_instance_namespace`](ae_engine/manufacturing_api.py#L755) | 關鍵字 `set_id: str`、`bay_id: str` | `str`，用於輸出命名；**來源 ID 不等於物理 `part_key`** |

### A1. 資料物件／欄位

| DTO | 欄位（順序及型別） | 驗證規則 |
| --- | --- | --- |
| [`ManufacturingSourceIdentity`](ae_engine/integration_api.py#L25) | `panel_key: str`、`source_revision: str`、`set_id: str \| None = None`、`bay_id: str \| None = None` | 前兩者不得為空；Set/Bay 須成對。正式 Receiving Bay 出圖必須兩者皆存在 |
| [`ManufacturingIntegrationRequest`](ae_engine/integration_api.py#L35) | `operation: "capabilities" \| "prepare" \| "export"`、`family: str \| None = None`、`source: ManufacturingSourceIdentity \| None = None` | 未知操作／Family／來源拒絕 |
| [`ManufacturingIntegrationResponse`](ae_engine/integration_api.py#L44) | `operation`、`status`、`family`、`source`、`reason`、`family_implemented`、`python_api_available`、`manufacturing_authorized`、`dxf_roundtrip_verified`、`external_export_available`、`known_families` | `capabilities` 僅宣告入口可用，不能推論獲製造授權 |
| [`ManufacturingResolvedBayInput`](ae_engine/integration_api.py#L158) | `family: str`、`source: ManufacturingSourceIdentity`、`resolved_geometry: ResolvedManufacturingGeometry` | 目前 verified integration batch **只允許 Receiving**；幾何必須是 Engine 已解析且 `parts` 非空 |
| [`ResolvedManufacturingGeometry`](ae_engine/contracts.py#L608) | `parts: tuple[ResolvedManufacturingPart, ...]`，另可含 `joints`、`relief_rules`、`diagnostics` | Engine 唯一決定各 `part_key`、Fold／Corner／實體；CADSplit 不得從來源框線自行製造 |
| [`VerifiedIntegrationBatchExport`](ae_engine/integration_api.py#L171) | `output_files: Mapping[str,str]`、`physical_dxf_roundtrip_verified: bool`、`complete_assembly_certified: bool`、`external_cli_enabled: bool` | `complete_assembly_certified=False`、`external_cli_enabled=False`，只證明這批已提交的實體 DXF 重開驗證 |

**批次限制：** 1～20 個 Receiving Bay；暫存前實際 DXF 物理片總數也須為 1～20；禁止重複／碰撞 namespace。Caller 必須提供真的 `pre_commit_guard`，在 staged export 前及所有 DXF 重開後重新檢查可信專案／原圖版本和授權；不能用空函式假裝有 guard。缺少正式 PartSpec／Fold／Corner／Topology／Registry 資料時，應阻擋受影響範圍，不能用 bbox、金庫型預設或預覽推製造值。

### A2. 呼叫範例（同程序 Python，不是 HTTP）

```python
from ae_engine import (
    ManufacturingIntegrationRequest,
    ManufacturingSourceIdentity,
    ManufacturingResolvedBayInput,
    dispatch_manufacturing_integration,
    export_verified_resolved_integration_bays,
)

identity = ManufacturingSourceIdentity(
    panel_key="P1",
    source_revision="真實 CADSplit 來源版本或 SHA",
    set_id="Set-01",
    bay_id="Bay-01",
)

capability = dispatch_manufacturing_integration(
    ManufacturingIntegrationRequest("capabilities", family="RECEIVING")
)
assert capability.status == "SOURCE_API_AVAILABLE"

prepared = dispatch_manufacturing_integration(
    ManufacturingIntegrationRequest("prepare", family="受電箱", source=identity)
)
assert prepared.status == "SOURCE_ACCEPTED_NOT_MANUFACTURING_READY"

# 下兩個物件不是本入口自動生成的：
# geometry_from_engine: WHD Engine 正式解析出的 ResolvedManufacturingGeometry
# check_current_committed_project: 由可信專案持有者實作，重驗真實 source SHA／授權
result = export_verified_resolved_integration_bays(
    (ManufacturingResolvedBayInput(
        family="受電箱",
        source=identity,
        resolved_geometry=geometry_from_engine,
    ),),
    "output/加工圖",
    pre_commit_guard=check_current_committed_project,
    overwrite=False,
)
print(result.output_files)
assert result.physical_dxf_roundtrip_verified
assert result.complete_assembly_certified is False
```

## B. WHD Engine：一般板件、實體批次及 Save→Reload

這些是**已有的 Engine 函式**，並不表示任意來源、所有 Family／Operation 都獲認證。需要由 Engine 與現有 Registry／Policy 決定真正材料、實體和加工權限。

| 功能 | Python 函式／原始碼 | 主要參數 | 回傳／限制 |
| --- | --- | --- | --- |
| **單板件製造 DXF** | [`manufacturing_api.generate_part`](ae_engine/manufacturing_api.py#L687) | `spec: PartSpec`、`output_path`、`context: ManufacturingContext \| None = None` | `PartExportResult`；只接受既有支援的正式 PartSpec，受 baseline／Policy／輸出檢查約束 |
| **單組已解析實體 DXF** | [`save_resolved_manufacturing_geometry_dxf`](ae_engine/manufacturing_api.py#L759) | `resolved_geometry`、`output_dir`、`overwrite=False`、`part_only=False`、`instance_namespace=None` | `dict[str,str]`；`part_only` 不能擴大到整箱認證 |
| **一般已解析多 Bay 批次** | [`save_resolved_manufacturing_geometry_batch_dxf`](ae_engine/manufacturing_api.py#L779) | `instances`、`output_dir`、`overwrite=False`、`part_only=False` | `dict[str,str]`；**不保證每片在 commit 前 Save→Reload**，需要嚴格放行請用 verified 入口 |
| **每片驗證後的 FinalScene 原子提交** | [`save_verified_final_scene_batch_dxf`](ae_engine/manufacturing_api.py#L822) | `parts`、`output_dir`、`pre_commit_guard`、`overwrite=False`、`durable_stage_commit=None` | `dict[str,str]`；既有 FinalScene staging／reopen 機制，特定 durable hook 需符合其安全契約 |
| **單片 DXF 重開驗證** | [`verify_saved_part_render_data_dxf`](ae_engine/manufacturing_api.py#L843) | `render_data`、`output_path`、`coordinate_tolerance=1e-6`、`area_tolerance=1e-6` | 驗證物件（看 `ok`、`issues`）；不是自動出圖許可 |
| **多 Bay DXF 重開驗證** | [`verify_saved_resolved_manufacturing_geometry_batch_dxf`](ae_engine/manufacturing_api.py#L879) | `instances`、`output_dir`、`coordinate_tolerance=1e-6`、`area_tolerance=1e-6` | 驗證物件（`ok`、`issues`）；僅驗實際提供的物理庫存 |
| **生產 NC 能力查詢** | [`resolved_manufacturing_nc_capability`](ae_engine/manufacturing_api.py#L839) | 無 | `{"available": False, ...}`，尚未有正式 NC sink |

## C. Engine 製造輸入與展示 API

| 功能 | Python 函式／原始碼 | 主要參數 | 回傳／限制 |
| --- | --- | --- | --- |
| **門板操作輸入 → Engine PartSpec** | [`build_door_operator_part_spec`](ae_engine/manufacturing_api.py#L1190) | `values`、必填 `model_name`、可選 `features`、`indicator_hole`、`door_indicator`、`door_indicator_offset=(0,0)`、`use_box_distance=False`、`corner_policy`、`frame_edges`、`indicator_window_groups`、`nameplate_center_datum_top` | `DoorPartSpec`；需要已確認的 W/H/T/FW、gap、fold 等值，不會自猜 |
| **箱身操作輸入 → Engine PartSpec** | [`build_box_body_operator_part_spec`](ae_engine/manufacturing_api.py#L1275) | `values`、必填 `model_name`、`features`、`face_features`、`head_corner_policy`、`tail_corner_policy`、`fold_profile`、`structure_state`、`source_part_features`、`endcap_y_profiles`、`head_ybottom1`、`tail_ybottom1`、`snapshot` | `BoxBodyPartSpec`；由 Engine 解析來源物理結構 |
| **Door 展開尺寸讀取** | [`project_operator_door_blank_dimensions`](ae_engine/operator_door_blank_projection.py#L14) | `values`、必填 `material_frame_width`、`baseline_model=""`、`selected_cell_size=None`、`frame_edges=None` | `tuple[float,float]`；展示／操作計算，**不是 DXF 認證** |
| **EndCap 展開尺寸讀取** | [`project_operator_endcap_blank_dimensions`](ae_engine/operator_endcap_blank_projection.py#L15) | `values`、`baseline_model=""` | `tuple[float,float]`；展示／操作計算，**不是 DXF 認證** |
| **真實物理數量需求** | [`resolved_quantity_physical_demands`](ae_engine/manufacturing_api.py#L898) | `versions`、`per_box_counts=None` | Engine 數量投影結果；不是生產 DXF 放行 |

## D. Receiving NFB：已有、但各自有正式來源／局部放行條件的操作

| 功能 | Python 函式／原始碼 | 實際參數 | 範圍 |
| --- | --- | --- | --- |
| **驗證 NFB BasePlate 的來源／成品** | [`prepare_verified_receiving_nfb_base_plate`](ae_engine/receiving_nfb_base_partial_export.py#L51) | `bundle`、`layout`、`current_snapshot`、`base_spec`、`index_path=INDEX_PATH`、`profile_path=None` | 需現有 NFB verified submission、正式版來源；非整箱製造 |
| **NFB BasePlate 局部 DXF** | [`export_verified_receiving_nfb_base_plate`](ae_engine/receiving_nfb_base_partial_export.py#L156) | 上列參數再加 `output_directory` | 僅該範圍的已核准 BasePlate PART_ONLY |
| **NFB Inner Door 局部 DXF** | [`export_verified_receiving_nfb_inner_door`](ae_engine/receiving_nfb_inner_door_partial_export.py#L31) | `bundle`、`layout`、`current_snapshot`、`output_path`、`index_path=INDEX_PATH`、`profile_path=None` | 僅指定 NFB Inner Door PART_ONLY |
| **NFB Door + BasePlate 成對 DXF** | [`export_verified_receiving_nfb_door_base_pair`](ae_engine/receiving_nfb_pair_export.py#L37) | `bundle`、`layout`、`current_snapshot`、`base_spec`、`output_directory`、`index_path=INDEX_PATH`、`profile_path=None` | 經驗證的一對實體；不宣稱全 Set/Bay |
| **現行 CSV NFB 成對局部 DXF** | [`export_current_csv_nfb_door_base_pair`](ae_engine/receiving_nfb_pair_export.py#L147) | `snapshot`、`assembly_parts`、`base_spec`、`output_directory` | 現行 CSV NFB 來源／組合態限制，僅 PART_ONLY |
| **多個已標示 NFB Inner Door 部分匯出** | [`export_highlighted_nfb_inner_doors`](ae_engine/receiving_nfb_partial_batch_dispatcher.py#L78) | `ports`、`set_index`、`bay_indices`、`output_directory`、`allow_held=False` | 只匯出經現有 Engine gate 允許的 highlighted 項目 |
| **NFB 物理清單可顯示性驗證** | [`validate_receiving_nfb_manifest_view`](ae_engine/receiving_nfb_manifest_validation.py#L14) | `view` | read-only；不可當 DXF 授權 |
| **NFB highlighted 清單驗證** | [`validate_receiving_nfb_highlighted_manifest`](ae_engine/receiving_nfb_manifest_validation.py#L77) | `ports`、`set_index`、`highlighted_bays` | read-only；不可當 DXF 授權 |

## E. 資料與能力狀態：怎麼判斷「有 API」和「能加工」？

| 情況 | 真實狀態 |
| --- | --- |
| Python `capabilities` 可取得 Family | **可查詢**；Family 註冊不等於其所有 Part／Operation 認證 |
| Python `prepare` 回傳來源已接受 | **可接收來源身分**；尚未生成 Engine 製造實體 |
| `dispatch_manufacturing_integration(operation="export")` | **未開放**；返回 `EXTERNAL_EXPORT_NOT_CERTIFIED` |
| Receiving 已有 Engine `ResolvedManufacturingGeometry`，可信版本 guard、實體能力都合格 | 可經 **`export_verified_resolved_integration_bays`** 寫入本批 DXF，提交前 Save→Reload |
| CADSplit 只有原始 DXF／未完成的 `finalized info_data` | **不可直接加工**；需來源識別 → Engine PartSpec／Fold／Corner／Topology／Policy／正式實體解析 |
| RO／落地盤 Family 註冊 | `implemented=False`；未開放加工 |
| 外部 HTTP／REST／Swagger、安裝版 Worker／EXE | **無對外服務網址，且外部製造停用**；請勿把本頁 GitHub URL 當作 API endpoint |

### CADSplit 目前現有入口

- [CADSplit `modules/receiving_api_bridge.py`](https://github.com/looaeedr/CADSplit/blob/main/modules/receiving_api_bridge.py) 為**已存在的條件式 Bridge**，需核對其內嵌 `ae_engine` 版本；舊版可能沒有本表 verified integration 函式。
- [CADSplit `modules/export_tasks.py`](https://github.com/looaeedr/CADSplit/blob/main/modules/export_tasks.py) 有 Receiving 來源不足的 blocking path，不能用 Vault 公式替代。
- **各 Repo 的 Engine 不要求同 SHA 才能執行既有相容 API**；但實際使用哪一份引擎、每次輸入與輸出必須可追溯。

**本頁定位**：是可點擊的「功能／參數／原始碼」速查索引，包含與 CADSplit 串接直接有關的主要 API；更廣泛的 #2517 GUI、Fold、Hole、2D／3D 預覽與所有其他公開 callable 仍以 [完整 `HEADLESS_API.md`](HEADLESS_API.md)、[CURRENT AI 庫 04](個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md) 及真正 callable 簽名為準。本表未列出的函式，**不代表不存在**。
