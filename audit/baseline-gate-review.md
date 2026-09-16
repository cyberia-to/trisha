# Complete baseline gate review — 2026-09-12

The gate now requires explicit fresh-generation-and-verification events for each
classic/hand pair. The former script inferred proof count from ordinary `PASS`
rows and could accept an execution-only log. That defect is fixed.

## Acceptance contract

`check-baselines.py` verifies the candidate executable hashes and the complete
source/vendor inventories before and after running the archived candidate's
`trisha bench ... --full`. The inventory must contain exactly43 hand baselines,
99 positive and34 negative fixtures; positive fixtures cover every hand baseline.
Source, hand, witness and linked-library paths must resolve inside that verified
source inventory. Work remains outside source and candidate.

For every positive fixture, bench actually generates each proof, compares its
public input to the exact implementation input, compares its public output to
the independent fixture, compares its program digest to a separately parsed
`Program::from_code(bundle.assembly).hash()`, and verifies it. Only afterward it
emits `TRISHA_PROOF_VERIFIED` JSON with fixture path, classic/hand identity,
program digest, public input/output, native proof format, proof byte length and
Hemera proof-content digest. Execution-only mode emits no such event.

The gate requires exactly one matching event per implementation and positive
fixture, before its successful fixture row:198 events total. Missing, duplicate,
late, negative-fixture or unknown-identity events fail; changed public claims,
invalid digest shapes/field values and malformed proof metadata fail. It also
requires exact fixture rows and exactly one complete summary. Negative fixtures
must reject both executions and produce zero proof events. A count of generation
messages or ordinary PASS rows cannot satisfy proof acceptance.

## Cleanup and smoke review

Memory sampling now sums the owned process group by PGID rather than following a
fixed-depth parent tree. Cleanup signals and reaps the owned group even when the
direct parent already exited, so surviving group children are terminated. Memory
limits, nonzero exit, artifact mutation or incomplete evidence prevent a passing
receipt. An exception can leave diagnostic work files, but never a PASS receipt.

`smoke-release.nu` was read without edits: proof commands and fresh verification
must succeed, exact claim checks and negative mutations follow, binary/fixture/
source-verification/harness hashes are rechecked, and the sole passing receipt is
written at the end. It is a separate installed smoke scope, not a replacement for
the complete133-fixture/198-proof gate. Resource monitoring of smoke belongs to
its external process-group wrapper.

## Validation performed

- `python3 -B scripts/test_check_baselines.py`:9 tests passed. Includes a
  99-positive/34-negative synthetic inventory requiring198 explicit events and
  rejecting197, execution-only/generation-only refusal, duplicates, missing and
  mismatched claims, ordering, and cleanup of an actual owned process.
- Default Trisha CLI build passed, zero warnings.
- Real `bench fixtures/assert --full`:2 fresh default-security proofs generated
  and verified; both256-row programs. Their explicit events passed the real gate
  parser. Repeating ordinary execution-only bench produced no proof events and
  was correctly rejected by that parser.

Logs: `/tmp/baseline-gate-script-tests.log`, `/tmp/baseline-gate-cli-build.log`,
`/tmp/baseline-gate-real-pair.log`, `/tmp/baseline-gate-real-pair-receipt.json`,
`/tmp/baseline-gate-execution-only.log`.

The full198-proof gate has **not** been run by this review. It must execute against
the next frozen candidate; the new receipt format does not retrofit missing input
provenance onto historical proof logs. No proof bytes are published by this task.

## Default Python startup source mutation — corrected live checker

The frozen FINAL5 preflight exposed a separate real tool defect: plain `python3`
loaded `verify-source.py` through importlib and wrote
`__pycache__/verify-source.cpython-314.pyc` inside the source archive before
checking its exact inventory. The verifier correctly rejected that mutation.
The preserved failure receipt is
`/tmp/cyber-final5-baseline-startup-bytecode-failure.log`; this failed preflight
is not a passing baseline run.

The live `scripts/check-baselines.py` now sets `sys.dont_write_bytecode = True`
before dynamically importing the archived verifier. The documented default
invocation needs neither `-B` nor an environment workaround. Test-module imports
also disable bytecode writes so the test runner itself does not dirty the source.

A new real subprocess regression creates a temporary exact source/vendor
inventory, genuine verifier receipt and matching candidate/binary hashes. It
invokes the checker using plain Python, explicitly removing
`PYTHONDONTWRITEBYTECODE` and `PYTHONPYCACHEPREFIX`. The real verifier succeeds,
and preflight then rejects the intentionally empty baseline set at the expected
43/99/34 gate. No child binary is executed, no work directory is created, no
`__pycache__` appears, and every inventoried file byte is unchanged. The test does
not mock the verifier or require a read-only filesystem to hide the bug.

All nine existing tests plus this regression pass:10 tests,0 failures,0.094 s,
`/tmp/trisha-baseline-bytecode-regression.log`. A separate temporary control with
only the production bytecode-disable line removed fails this regression on the
unexpected `__pycache__` inventory entry:
`/tmp/trisha-baseline-bytecode-before-control.log`.

No frozen FINAL5 file was edited by this correction. Root removed only its
accidentally generated bytecode and restarted the exact frozen checker with
`python3 -B`; that ongoing198-proof run uses the frozen script and its recorded
hash. It must not be described as a run of this new live checker. This audit
records the startup fix and regression only, not the completion of that proof run.
