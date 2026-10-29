# CADSplit → WHD-Engine Worker CLI — W-01 boundary (#2377)

Source of truth for the wire contract: [CADSplit_WHD_Contract.md](../docs/integrations/CADSplit_WHD_Contract.md) and `schemas/`.
This folder **does not duplicate** any WHD manufacturing formula or Registry.

## Three public operations only

```text
WHD-Engine capabilities --response C:\Jobs\capabilities.json
WHD-Engine prepare --request C:\Jobs\request.json --response C:\Jobs\prepare.json
WHD-Engine export --request C:\Jobs\request.json --response C:\Jobs\export.json
```

Source-only development entry point:

```text
python /absolute/path/to/whd/integration_cli/cadsplit_worker.py capabilities --response /outside-repo/capabilities.json
```

The Worker does not import Tk, `ae_engine`, or CADSplit just to parse CLI
arguments, validate wire JSON, or return disabled capabilities. It works from
a current working directory that is **not** the installation root.
The source-only handler derives the exact Git commit from Git metadata
and hashes its `ae_engine/**/*.py` plus Worker entrypoint. It labels its
build `source-only-unreleased`: this is a source fingerprint, **not a certified
EXE hash or release manifest**. If Git/build identity is unavailable the
source CLI rejects instead of inventing a hash. W-05 must supply a verified
packaged manifest and resource/binary integrity logic.

`capabilities` currently reports **all flags false**, zero supported
part kinds, and unverified Registry/baseline/policy (null resource hashes).
`prepare/export` validate schema and up to 20 items once in one Worker
process, then explicitly return `WHD_OPERATION_NOT_IMPLEMENTED` and
`manufacturing_verified=false`. There is no export, no Tk initialization,
no Registry initialization, no DXF write, and **no claim of working W-03/04**.
W-03 connects target Frame, canonical dimensions, policy and prepare tokens.
W-04 connects WHD FinalScene manufacturing, Save→Reload and export.
W-06 owns durable idempotency, job/output path locks, crash recovery and cancel.

## Output and failure semantics

- `stdout`: reserved/empty for these operations. The response JSON file is
  the only machine-readable payload; failures also print a short diagnostic
  to `stderr` only if no valid response can be written.
- Exit `0`: a capabilities response was written. **It does not mean
  manufacturing is supported.**
- Exit `2`: invalid UTF-8/JSON, unknown operation, protocol/schema/limit
  rejection.
- Exit `3`: request is valid but its manufacturing handler is not ready.
- Exit `4`: request or response path/build identity/IO cannot be trusted.
- A newly created `*.json` response is UTF-8, fully flushed and installed
  through same-directory hard-link atomic creation. An existing response
  file is **never overwritten**, including on retry; callers use a new
  response pathname and the original semantic job identity.
- Request JSON is size-bounded; duplicate JSON keys, NaN/Infinity, invalid
  Unicode, unsafe IDs and unsupported schema fields fail closed. Paths may
  contain Chinese and spaces; response targets inside the source/install
  tree are rejected. Customer `config.ini`, original DXF/CSV and all
  manufacturing outputs are untouched.

These are W-01 transport tests, not the Windows onedir EXE or Gate A.
W-05 must verify Windows hard-link semantics or provide an equally safe
no-clobber atomic method; W-07 separately validates real packaging/GUI.

## W-03 partial preflight (#2378, not a working prepare handler)

`prepare_evidence.py` is a **non-authorizing** building block. It hashes the
actual bytes of an explicitly selected Certified Registry and WHD-resolved
baseline list, locks the exact build/source hash, current
`manufacturing_api.resolve_policy` snapshot and item dimensions, and compares
those immutable inputs before a later export. It refuses missing, empty,
symlinked or escaping resources rather than replacing a missing source with
placeholder hashes. It must be given paths selected by WHD's
`expected_baseline_path_for`; it does **not** discover baseline filenames
from CADSplit source data. `resolve_authoritative_door_inputs` calls WHD's
own `door_finished_face_size` on a previously verified `DoorPartSpec`; it
does not infer `frame_edges`, original DXF coordinates, or a physical
part ID from source drawing names.

The `environment_fingerprint` here is an **internal resource-input evidence
digest**, not the RFC 8785 wire `request_digest`, a durable transaction or an
issued `prepare_token`. It is **not** an attestation of a Windows binary.
A real W-03 `prepare` response remains blocked on independently verified
per-face 3D frame origin/basis/normal and on durable token binding. The
existing `cadsplit_worker.py prepare` intentionally continues returning
`WHD_OPERATION_NOT_IMPLEMENTED` until that acceptance is implemented.
Neither this module nor its test cases enable manufacturing. Only W-06/04
can own export stale-revalidation and final commit.



## W-03 certified *local* Door frame and in-process prepare

The subsequent W-03 implementation now provides:

- `prepare_frame.resolve_door_finished_local_frame`: a Door **local**
  finished-face frame with bottom-left local origin, +X right and +Y up,
  checked against `ae_engine.sheetmetal_feature_core.feature_finished_point`.
  `origin_xyz_mm=[0,0,0]` and +Z are a right-handed **local plane
  embedding**, never an assembly-world position, installation orientation,
  mirror guess or proof of another physical face. The flattened DXF mapping
  remains owned by WHD's `build_finished_reference_guide`.
- `request_canonical`: RFC 8785 digest excluding exactly
  `request_id`/`request_digest`, so changing transport correlation cannot
  change job identity but changing material inputs does.
- `prepare_binding`: a worker-secret HMAC covering job, source identity,
  canonical physical-part identity, target Frame, locked dimensions and
  environment, including independent per-item preparation digests.
- `prepare_batch.prepare_trusted_door_batch`: in-process, schema-validated
  **Door-only** prepare: uses WHD `resolve_policy`, `door_finished_face_size`,
  `expected_baseline_path_for`, Verified Registry/baseline byte hashes, and
  four explicit Door layout `frame_edges` flags. It returns
  `manufacturing_verified=false`; never emits DXF or checks out a real EXE.

**Remaining acceptance boundary:** the public Worker CLI is still not
connected to this function; the trusted installation key's durable custody,
atomic journal, verified package resource manifest and no-clobber retries are
W-06/W-05, and Windows Gate A is W-07. W-03 cannot claim public `prepare`
support or a certified EXE until those verified dependencies are available.
The present local Door frame MUST NOT be silently reused for EndCap,
IndicatorBox, BoxBody or back/mirrored faces. The CADSplit-side original DXF
source frame/transform remains CADSplit's responsibility.


## W-03 versioned draft (not a public capability)

The **published/source-only W-01 CLI remains wire 1.0.0** and returns
`prepare/export` as unsupported. The W-03 Door frame evidence needs an
explicit `part.frame_edges` member not present in the immutable 1.0.0
contract. The in-process W-03 test boundary therefore uses the separate
`request_v1_1.schema.json` and `response_v1_1.schema.json`
(**protocol 1.1.0**, optional additive Door edges); it MUST NOT mutate
`request_v1.schema.json` or claim 1.1.0 public capabilities. A future
packaged Worker may only negotiate 1.1.0 after the W-04/W-06/W-05 gates.


## W-03 pre-export recomputation (internal, not public)

`prepare_recheck.recheck_trusted_door_export` is a pure fail-closed
pre-export guard. The **original prepare request and receipt must come
from a Worker-owned authenticated durable store**, not be supplied by the
external export body. It verifies separate RFC8785 request digests,
original physical item/source/Frame/dimension identity, target-frame
ownership and sealed token, then calls WHD's actual Door-only prepare
again against the **current Registry, baseline DXF, Factory Policy, build
and engine**. A change refuses the *entire batch* with
`WHD_PREPARE_STALE` before output staging.

This guard is not a transaction journal, geometry validator or DXF
exporter. W-04 must own feature/source geometry verification and
Save→Reload acceptance; W-06 must store the original authenticated
request/receipt, enforce idempotency and re-run this guard at the final
commit barrier (or prove an immutable snapshot). The W-01 public CLI
keeps all manufacturing capabilities disabled.

## W-04 internal real DXF Save→Reload batch

The manufacturing owner now exposes an internal
manufacturing_api.save_verified_final_scene_batch_dxf path for strictly
WHD-owned PartRenderData and physical identities (up to 20). It stages
actual DXF files and verifies each saved file with the independent
manufacturing_verification.verify_saved_part_render_data_dxf owner before
committing the entire set with existing atomic rename/rollback logic.
A mandatory pre_commit_guard runs twice, before staging and after all
Save→Reload checks but before committing, to permit W-03/W-06 trusted
snapshot revalidation.

This is a *real manufacturing DXF staging seam*, **not** a public CADSplit
export. W-03/W-06 still need a trusted persisted request, key custody and
path locking; W-04 must map wire features to canonical PartSpec/FinalScene,
enforce physical inventory and factory source provenance; no external NC sink,
Windows EXE, or official X is certified here.


## W-04 wire Feature preflight (internal and non-manufacturing)

`feature_preflight.validate_wire_features_against_prepared_frame` is now
called by W-03's trusted pre-export recheck. It rejects duplicate feature IDs,
non-finite/Boolean geometry, out-of-face circles/rectangles/profiles, invalid
closed profiles, target-dimension drift, inconsistent unit scale and explicit
rotation/mirror/2×2 matrix evidence before any render or DXF stage. The
WHD-issued Frame remains authoritative; no CADSplit assertion is trusted.

**Boundary:** This only checks the *claimed* feature envelope. It does not
reopen original CADSplit DXF entities or prove the matrix was applied once,
and cannot manufacture a source feature or enable public `prepare/export`.
The outstanding W-04/W-06 source verification, canonical PartSpec mapping,
worker-owned job custody/path locks and Windows Gate A are still mandatory.


## W-04 source DXF CIRCLE verification (internal, read-only)

`source_circle_verification.verify_trusted_original_dxf_circles` now reads
**one original DXF byte snapshot** from a **Worker-owned trusted path** and
checks the exact `source_document_sha256` bound at prepare. It parses that
same snapshot, resolves an original **modelspace CIRCLE handle**, verifies
DXF `$INSUNITS` (mm/inch only), checks the 2D plane, applies the explicit
2×2 matrix and unit conversion **exactly once**, and compares real center
and radius against the finished-face wire claim (1e-6 mm). A source handle
cannot be reused for another Feature in the same item. Altered bytes,
missing paths, symlinks, absent handles, wrong units and mismatched geometry
fail the **entire trusted W-03 export precommit recheck** with
`WHD_SOURCE_UNVERIFIED`. The source file path is supplied only through
the trusted internal `source_documents` map, never from CADSplit JSON.

**Explicit limits:** this evidence is CIRCLE-only and limited to direct
modelspace planar entities and text DXF readable as UTF-8; rectangles,
profiles, INSERT/transformed block contents and unknown source planes
remain fail-closed until their specific certified adapters exist.
The wire's `source_geometry_sha256` does **not** currently specify an
interoperable canonicalization recipe, so this gate does not claim that
digest is verified. The full original **document bytes** hash and actual
source entity geometry are checked; no source receipt is persisted by
this read-only helper. The public Worker/EXE remains disabled; W-06 must
own durable source/path/key custody and commit locking, and W-04 must map
verified Feature geometry to canonical WHD PartSpecs/FinalScene.


### W-04 WHD-native Door CircleFeature handoff (internal)

On successful source-byte/hash/CIRCLE-handle matching, the same verification
owner returns a tuple of **WHD `CircleFeature` instances**, each with
`FeatureAnchor.ABSOLUTE_FINISHED_FACE`, the source-attested mm center,
`diameter=2*verified_radius_mm` and WHD `CUTTING`. This only supports
`process=THROUGH_CUT`; `BLIND_HOLE` and `MARKING` deliberately fail closed
until their fabrication classification and source-layer acceptance exist.
WHD's existing `DoorPartSpec(features=..., feature_space="finished_face")`,
`_door_features_for_legacy_engine` and `manufacturing_api.generate_part`
remain the sole owner of finished-face → unfolded geometry and DXF output.
A permanent test uses a real original source DXF, W-03 recheck, this typed
handoff and a real WHD Door DXF reloaded with ezdxf. This is an internal
partial W-04 acceptance, **not** a packaged Worker or a production release.


**Vault baseline Door DXF coordinate acceptance (2026-10-29, #2379):**
`manufacturing_api.generate_part` delegates to WHD's
`ae.export_stretched_door_dxf`, which maps a verified finished-face
`CircleFeature` onto the unfolded Scene and **mirrors the entire Scene
on the unfolded X axis before serializing DXF**. The independent disk-DXF
regression therefore derives the authoritative unfolded width from WHD's
`get_stretched_door_data(...).params["total_width"]` and compares the
persisted circle at `x=total_width-pre_export_x`, while retaining the
original Y/radius. Comparing the unmirrored internal Feature coordinate
to the final DXF is a false RED. This does not change source geometry,
WHD's mirror policy, PartSpec, or any CNC/DXF manufacturing formula.
