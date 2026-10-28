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
