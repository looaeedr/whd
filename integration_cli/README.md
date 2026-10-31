# CADSplit → WHD source-only Worker wire boundary

This directory keeps the WHD-owned external wire schemas and source-mode
protocol adapter. It is **not an installed Worker, not a WHD-Engine.exe
distribution, and not a manufacturing release**.

## Current public surface

Only these source-mode commands exist:

```text
python integration_cli/cadsplit_worker.py capabilities --response <response.json>
python integration_cli/cadsplit_worker.py prepare --request <request.json> --response <response.json>
python integration_cli/cadsplit_worker.py export --request <request.json> --response <response.json>
```

There is no public `verify`, no `--installation-id`, no
`_private_installed` command, and no packaged/frozen execution path.

`capabilities` is source-only and reports zero supported manufacturing kinds
with every capability flag false. `prepare` and `export` validate the
protocol and then fail closed with `WHD_OPERATION_NOT_IMPLEMENTED` and
`manufacturing_verified=false`; they do not write DXF.

## Retired installed Worker / EXE path

The Windows installed/packaged Worker path was retired by the 2026-11-01
architecture decision. The repository no longer owns an active
`WHD-Engine.exe` packaging workflow, packaged identity manifest,
DPAPI/HMAC installation custody, installed-job admission, or public installed
certification adapter.

Internal W-03/W-04/W-06 Python helpers may remain as non-public implementation
foundations. They are not reachable from `cadsplit_worker.main()` and their
unit tests do not constitute external manufacturing certification.

Future CADSplit integration must consume verified WHD Engine public APIs under
the current GUI → Engine ownership contract. Re-introducing an installed
Worker/EXE requires a new explicit architecture decision, a new authority
owner, and exact-SHA tests; old #2375/#2381/#2382 installed-path text is not
permission to restore it.

Wire reference: [CADSplit_WHD_Contract.md](../docs/integrations/CADSplit_WHD_Contract.md).
