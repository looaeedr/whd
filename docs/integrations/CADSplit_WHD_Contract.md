---
whd_doc_role: REFERENCE
whd_contract: cadsplit-whd-worker-wire-v1
whd_canonical: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
whd_schema: WHD_DOC_META_V1
---

# CADSplit × WHD-Engine — external Worker protocol 1.0.0

> Issue [#2376](https://github.com/looaeedr/whd/issues/2376), W-02.
> **This is a wire contract, not evidence of a built Worker, enabled capability, or certified manufacturing output.**
> The approved cross-project v1.1 specification is the requirement source;
> WHD CURRENT 04/07, the Certified Registry and actual production code retain
> manufacturing authority. This document introduces no fabrication formula.

## Operations and schema ownership

The only public operations in protocol 1.0.0 are:

- `WHD-Engine.exe capabilities --response <JSON>`
- `WHD-Engine.exe prepare --request <JSON> --response <JSON>`
- `WHD-Engine.exe export --request <JSON> --response <JSON>`

There is **no independent `verify` command**. `export` must verify the
canonical FinalScene through Save→Reload plus geometry/layer/feature acceptance
before commit, and must report physical parts separately. Versioned schemas are:

- [request_v1.schema.json](../../integration_cli/schemas/request_v1.schema.json)
- [response_v1.schema.json](../../integration_cli/schemas/response_v1.schema.json)
- [capabilities_v1.schema.json](../../integration_cli/schemas/capabilities_v1.schema.json)

A rejected `export` request may be malformed before any `transaction_mode` is
known: in a `failed` response that field may be absent. A successful or
partial `export` response must include it; callers must never infer that an
absent mode means a successful all-or-nothing transaction.

These files validate **wire shapes only**. The runtime must independently
enforce geometric, resource, security and transaction invariants below. No
capability can be set true until its implementation and tests actually pass.

Missing or invalid Registry, baseline or policy resources must be reported
through `resource_health` with a **null hash**, never an invented or cached
content hash. A healthy resource must carry its actual SHA-256. A complete
`resource_revision` may remain null until the snapshot is verified; an
incomplete snapshot must not enable manufacturing.


## Wire-to-domain mapping (not Python enum identity)

Transport `kind` v1 defines `door`, `end_cap_head`,
`end_cap_tail`, `indicator_box`, `indicator_small_door`. These
are external protocol labels, **not** new `ae_engine` enum values:
`manufacturing_api._part_kind` currently distinguishes `door`,
`end_cap_head`, `end_cap_tail`, `indicator_box` among others;
`indicator_small_door` must map through the *existing*
`indicator_small_door_spec` helper and may be enabled only after W-03/04.
`box_body`, `base_plate`, `custom_fold` are reserved for later
capabilities; they are not accepted as v1 request part kinds merely because
WHD has Python PartSpecs for them.

Wire `dimension_semantics` must be explicitly one of
`cabinet_outer` (overall operator formed outside dimensions) or
`part_formed_outer` (confirmed physical part formed outside dimensions).
It is **not** a physical formula or an assertion that every family accepts
both. A Worker must use the current Phase6 size authority and its capability
requirements. Optional fold/gap/frame inputs may not be silently invented by
CADSplit; W-03 resolves WHD Factory Policy and returns the relevant snapshot.
Thickness, physical identity and relevant dimensions are positive real values.

Wire `process` is restricted to `THROUGH_CUT`, `BLIND_HOLE`,
`MARKING` (authoritative fabrication layers CUTTING, BLIND_HOLE, MARKING).
No CADSplit feature may prescribe `BEND`: WHD owns bending.
`CircleFeature`, `RectFeature`, `ProfileFeature` remain internal Python
types; the external `circle`, `rect`, `profile` shape labels are adapters.
Shape/process combinations and geometric bounds are WHD runtime acceptance,
not JSON Schema inference.

## Frame and provenance (coordinate contract revision 1)

Only explicitly confirmed `finished_face` coordinates with `units=mm`
are accepted on export. `target_frame_id` is issued by WHD `prepare`,
bound to job/item/physical part/face and carried unchanged to `export`.
The corresponding returned target frame includes 3D origin, oriented basis,
normal, face role, viewed-from direction and finished-face dimensions.
The wire `face_role` set `outer/inner/front/back` and
`viewed_from=along_normal/against_normal` distinguish references; they do
**not** assert an implicit origin or mirror policy for every PartSpec.
W-03 must certify each supported kind/face's target frame against CURRENT
geometry before enabling it; otherwise refuse `WHD_FRAME_UNVERIFIED`.

Each Feature carries stable `feature_id`, `source_ref`, and a
`source_transform` containing source frame, unit authority, explicit
source-to-mm scale, **source and target dimensions in mm**, 2×2 matrix,
translation, quarter-turn rotation,
both mirror flags, source geometry SHA-256 and source entity references.
For protocol revision 1, source units are explicitly limited to `mm` with
scale **1.0** or `inch` with scale **25.4**. The matrix acts on source
coordinates **after** the declared unit conversion; translation is in mm:
`target_mm = matrix_2x2 × (source_xy × source_to_mm_scale) + translation_mm`.
The scale must not be applied a second time. Schema validates unit/scale pairing;
WHD runtime still validates matrix/shape/Frame consistency.
CADSplit owns the source transform **evidence**, but WHD verifies target
acceptance. Negative source coordinates are legal evidence; manufacturing
feature geometry must remain within the accepted target face.

**Runtime checks beyond Draft 2020-12 JSON Schema**:
finite JSON numeric values (no NaN/Infinity), unit conversion consistency,
non-singular matrix, orientation determinant vs. mirror flags, compatible
rotation/mirror composition, winding, transform applied exactly once,
target bounds, source/target physical-part identity, unique item/feature IDs,
unique destination paths, source document integrity, and the
`prepare`→`export` token/digest binding. A client assertion of `verified`
is not sufficient. Failed evidence must fail closed.

## Job identity, canonical digest, resource freeze

Both operations share `(client_installation_id, job_id)` and the same item
identity. The de-duplication key is
`(client_installation_id, job_id, operation)`; `request_id` is transport
correlation, **not** a de-duplication key.

The canonical request digest is SHA-256 of canonical UTF-8 JSON under
[RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785).
Exclude exactly the transport-only `request_id` and `request_digest`
fields; include all semantic request fields and item order, output path,
overwrite and transaction mode. Only valid JSON numeric values are supported;
duplicate JSON object keys must be rejected before hashing. On receipt the
Worker **recomputes** the digest, compares any client-supplied digest and
the durable job record, and rejects collisions with `WHD_JOB_ID_CONFLICT`.
The current tests validate wire format; W-06 owns executable idempotency and
canonicalization parity tests.

`prepare` returns immutable per-item `preparation_digest` and
WHD-issued `prepare_token`, bound to environment fingerprint and job.
`export` must re-evaluate build/engine SHA, Registry and baseline content
hashes, resolved Factory Policy/config, canonical dimensions, frame and
protocol revision before any render and again before commit (or against a
proven immutable snapshot). A mismatch is `WHD_PREPARE_STALE` and the
entire batch is refused, even in per-part mode.

`max_batch_items` comes from verified capabilities; the schema does not
invent a universal count or imply cross-job global atomicity. Default
transaction mode is `all_or_nothing`; `per_part` is opt-in with explicit
user acknowledgement and may report partial.

## Timeout / durable result readback without fourth command

W-06 will persist a transaction journal and immutable job manifest under a
Worker-owned durable store, indexed by the canonical job identity and
operation. `capabilities.job_result_readback`, if implemented, advertises a
Worker-selected **read-only** store root and fixed `job_manifest.json` name.
CADSplit must never provide an arbitrary journal path to the Worker.

On timeout CADSplit should inspect the known durable result/manifest when
available; any receipt must match job identity, operation, digest, build,
output manifest and hashes. Missing/unknown/unfinished result is **not** proof
of rollback. Reissue the *same operation* with **same job_id, item identity,
canonical digest and semantic payload** (new transport request_id allowed).
The Worker first runs pending journal recovery and returns persisted
`committed`, `rolled_back` or `recovery_required` without a second export;
while another process still owns the job, it returns
`WHD_JOB_IN_PROGRESS`. If a fully trustworthy answer is unavailable,
CADSplit surfaces `recovery_required` and blocks the affected output.
No `status` or `verify` fourth public command is added.

Durable recovery, cross-process output-path locks, response atomicity,
cancellation at safe points and crash consistency are W-06, not accomplished
by these JSON files. A manifest read is **not** independently a manufacturing
pass unless WHD's persisted journal and output hashes agree.

## Compatibility and safe activation

The **document** v1.1 and **protocol** 1.0.0 are different version systems.
Unknown major, field, enum, missing evidence or unsupported capability fails
closed. Additive optional protocol fields require explicit minor revision and
compatibility tests; changed Frame semantics or default commit policy require
a major revision. Both sides must negotiate exact compatible capabilities,
not merely compare an EXE filename. Supported-part arrays and flags in a
capabilities response represent measured executable support; never publish a
true flag from a schema-only build.

W-01/03/04/06/05/07 respectively implement CLI, prepare, export, durable
transactions, Windows packaging and Gate A. Gate B/D/E and removal of
CADSplit's internal engine belong to CADSplit and user-controlled release;
the current branch does not enable or certify any of those.

## W-03 draft minor protocol extension (not enabled in W-01)

The original wire `1.0.0` schemas and W-01 source-only capabilities are
immutable. W-03 introduces optional Door `part.frame_edges`
(`left/right/top/bottom` booleans) **only** in separate draft schemas
`request_v1_1.schema.json` and `response_v1_1.schema.json` with
`protocol_version=1.1.0`. A successful Door-local in-process prepare
requires all four flags to have verified layout provenance; an omitted flag
must fail closed rather than silently default to all four true.
These schemas alone do not enable public `prepare`, `export`, DXF,
Windows EXE support or any non-Door physical Frame.
