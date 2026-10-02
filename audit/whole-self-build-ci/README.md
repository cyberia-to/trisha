# Whole self-build CI preparation checks

This audit covers the new orchestration source only. No hosted workflow, asset
upload, full self-build or execution-proof verification ran during these checks.

`final/checks.json` records the exact Python executable, input archive identity,
commands, source hashes and output hashes. Six tests passed under
`python3 -B scripts/test_whole_self_build.py`, with `WHOLE_SELF_INPUT_ARCHIVE` set
to the immutable compact export recorded there. The tests admitted all 111 frozen
files, checked the complete 94-module/370,544-byte source inventory, exercised the
historical receipt field mapping, bounded chunk reconstruction, path validation,
local cleanup refusal and build-environment sanitization. The mapping test is
explicitly a test of recorded coordinates, not a new proof result.

Actionlint 1.7.12 accepted `.github/workflows/whole-self-build.yml` with empty
diagnostic output. Its exact executable SHA256 and command are recorded in both
check receipts. Python AST parsing passed for every new script and the copied
input helper. `checks.json` retains the earlier check round. The first shell probe
passed all tests but then exited 1 because `actionlint` was not on PATH; subsequent
checks use the reviewed absolute executable and retain that probe explanation.

The input helper is byte-identical to the approved helper merged in Trisha
`191c6e03fa855be3b70b5aa5e4ee78be1ebffe91`, SHA256
`081cb35ba78abda71b1c86f6755dbb635672ca090dddbd0a1ff176959d58653b`.
The whole workflow's committed source selectors pin production Joy
`6e0ec4d8440e2521df08f442d64f54e667044716`, Nox
`2f09ca3c3f18ae470365310cca8db5208eda75c6` and Zheng
`0d7ba6d422d9b825f9685e903e55252f88ebecd9`, together with their complete approved
12-repository source closure. The input asset is pinned by ID 604704433 and exact
size, SHA256 and manifest identity in `.github/whole-self-build-input.json`.

Runtime capacity and durable retention remain unmeasured until the reviewed
manual hosted jobs complete. The original 48 GiB free-start guard may reject a
runner after allowlisted SDK cleanup; this preparation audit does not predict
that the guard will pass.
