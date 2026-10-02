# Issue #440 remediation — Assembly content height

After removing the fixed outer wrapper, the Assembly panel collapsed to 44 px because its internal native Canvas still declared `height=1`.

Exact production census on `2b9aeccee2c91446ca02cbfe9fdcefee587ba29e`:

```text
ASSEMBLY_HOST_REQHEIGHT=44
ASSEMBLY_HOST_HEIGHT=44
ASSEMBLY_CANVAS_REQHEIGHT=1
ASSEMBLY_CANVAS_HEIGHT=32
ASSEMBLY_CONTENT_REQHEIGHT=170
ASSEMBLY_CONTENT_HEIGHT=170
ASSEMBLY_SECTION_COUNT=5
```

The remediation keeps the no-wrapper/direct-slot layout and changes only Assembly presentation sizing: `Phase6AssemblyPanel._on_content_configure()` synchronizes Canvas requested height to the current content requested height. Expand/collapse rebuilds already pass through this seam, so the surface grows and shrinks with actual content.

Accepted result:

```text
ASSEMBLY_CONTENT_REQHEIGHT=170
ASSEMBLY_CANVAS_REQHEIGHT=170
ASSEMBLY_SURFACE_HEIGHT=182
ASSEMBLY_SURFACE_COLLAPSED_44=0
ASSEMBLY_SURFACE_FOLLOWS_CONTENT_HEIGHT=1
```

Focused GREEN RUN `35512254763`:
- 39 PASS / 0 FAIL / 0 ERROR / 0 SKIP.

Final acceptance RUN `35512341955`:
- visual SUCCESS
- protected SUCCESS
- target-drift SUCCESS
- accepted SUCCESS
- protected: 26 PASS / 1 SKIP
- `GEOMETRY_DRIFT=0`
- `PERSISTENCE_DRIFT=0`
- `CALLBACK_SEMANTIC_DRIFT=0`
- `CONFIG_INVARIANT=1`
- `FORCE_PUSH=0`

Visual artifact:
- ID `10605323623`
- SHA256 `904c22cb6689b72758399fdbb32ac1f8c96096815270f26039a5f36c02cf821b`

Manual screenshot review confirms all five Assembly rows are visible and the panel is content-sized rather than an empty fixed shell.
