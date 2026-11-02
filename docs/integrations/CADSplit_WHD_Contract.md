---
whd_doc_role: REFERENCE
whd_contract: cadsplit-whd-worker-wire-v1
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# CADSplit × WHD — source-only Worker wire contract

This document describes the retained JSON/CLI **wire shape**. It is not
evidence of an installed Worker, WHD-Engine.exe, enabled manufacturing
capability, or certified DXF output. Manufacturing authority remains in WHD
Engine CURRENT owners and the Certified Registry.

## Public source-mode operations

The only public operations are:

- `python integration_cli/cadsplit_worker.py capabilities --response <JSON>`
- `python integration_cli/cadsplit_worker.py prepare --request <JSON> --response <JSON>`
- `python integration_cli/cadsplit_worker.py export --request <JSON> --response <JSON>`

There is no public `verify`, no `--installation-id`, no private installed
command, and no executable packaging contract.

Versioned v1 schemas remain under `integration_cli/schemas/`:

- `request_v1.schema.json`
- `response_v1.schema.json`
- `capabilities_v1.schema.json`

Draft v1.1 schemas may remain as compatibility/reference artifacts for the
previous external experiment; their presence does not activate a runtime
route.

## Current runtime state

## 強制同源規則：source-only wire 不是 CADSplit 的第二條製造路徑

**WHD GUI 怎麼用正式 Engine API 取得製造結果，CADSplit 就必須怎麼做；只可在操作來源（GUI controls／Project 相對 CADSplit DXF→CSV／孔位／尺寸／source link）不同。** 兩邊都要形成可信、等價的 Request／PartSpec／Context 並走同一適用的 `manufacturing_api`，由同一 Family／Registry／物理板件／FinalScene／DXF reopen 驗證。任何 CADSplit 專用 DXF executor、私有製造公式、caller 例外認證都**嚴禁**。完整來源的板件逐片出圖，不完整板件逐片報錯；完整 Set/Bay 另驗 BOM 與裝配。

**本 wire 現在仍是 source-only、沒有製造資格，保留所有 fail-closed 拒絕。** 它的拒絕**不能**用來否決 CADSplit 既有合法內嵌 Python Engine 公開製造入口；反之也不得為了外部 export 而取消認證。權威 AI 庫 04 CURRENT；本 REFERENCE 不創造新的已啟用能力。


Source-mode `capabilities` reports:

- `engine_version=source-only-unreleased`;
- zero `supported_part_kinds`;
- zero enabled capabilities;
- null Registry/baseline/policy hashes;
- `installation_id=source-only-<commit-prefix>` as protocol metadata only.
  It is **not** an installed WHD authority.

Public `prepare` and `export` validate JSON/schema/correlation fields and
then return `WHD_OPERATION_NOT_IMPLEMENTED` with
`manufacturing_verified=false`. They must not initialize Tk, manufacture
FinalScene, or write DXF.

The wire field `client_installation_id` is retained as an external client
identity for schema compatibility. It does not select a WHD installation,
key store, source custody, output authority, or manufacturing permission.

## Geometry and provenance boundary

Wire `kind`, dimensions, Frame, feature, process and transform fields remain
transport evidence only. They cannot create WHD geometry, BEND, physical
identity, Factory Policy or Certified Registry truth. Any future enabled
consumer must call the same verified WHD Engine public APIs used by the
product; it may not reconstruct manufacturing rules in CADSplit or in the
wire adapter.

Malformed JSON, duplicate keys, unsupported protocol values, unsafe response
paths and unsupported manufacturing requests fail closed. Existing response
files are never overwritten.

## Installed Worker / EXE retirement

The former Windows installed/packaged path is retired. There is no active
contract for:

- `WHD-Engine.exe` onedir packaging;
- packaged identity/resource manifest admission;
- DPAPI/HMAC installation keys or installer-provisioned source/output custody;
- `capabilities --installation-id`;
- `_private_installed`;
- public installed `prepare/export` certification;
- Gate-A activation based on an installed Worker.

Historical #2375/#2381/#2382 evidence remains in Git/GitHub history only and
must not be used to re-enable the retired path.

If an external executable/installer is proposed again, it requires a new
explicit user decision and must consume WHD Engine public APIs instead of
restoring the retired installed Worker implementation.
