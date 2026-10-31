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
