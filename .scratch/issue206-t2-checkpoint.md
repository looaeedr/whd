# #206 / T2 Checkpoint

- Parent: #203
- Depends on: #205 CLOSED / completed
- Current role: T2 實作者
- Baseline: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
- Branch: `test/issue206-characterization-20260914`

## Approved seams
- `_corner_preview_canvas_point`
- `_corner_preview_flip_y_for_target`
- `_project_toolbar_presentation`
- `render_drawing_scene`

## Completed
- fresh branch from exact production baseline;
- Python測試實務 and tdd reread;
- global pitfall + skill rules references reread;
- primitive public contract in `ae_engine.sheetmetal_drawing` reread;
- T2 preflight evidence recorded.

## Pending
1. remote Phase6 preflight GREEN for known changed-file scope;
2. add isolated characterization test file only;
3. run focused tests remotely with config/protected invariants;
4. cleanup temporary workflow and tested→cleaned drift audit;
5. close T2 only if production source drift remains zero.

## No-go
- no production code modification;
- no expected value fed back into production;
- no mock of manufacturing geometry; renderer characterization uses explicit public primitives and a recording Canvas boundary;
- no HOLD candidates included.
