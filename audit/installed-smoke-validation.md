# Installed compiler and warrior smoke — 2026-09-12

The macOS arm64 full installed smoke passes for the three native binaries built
from [source rehearsal 1](source-candidate-rehearsal.md). The
[machine-readable receipt](installed-smoke-darwin-receipt.json) binds source
provenance, all three binaries, public state fixtures and the exact harness by
SHA-256. This is a local working-tree candidate, before final coordinated
commits and publication.

Command:

```sh
RAYON_NUM_THREADS=4 TVM_LDE_TRACE=no_cache nu trisha/scripts/smoke-release.nu \
  /tmp/cyber-release-installed-v7-darwin/bin \
  /tmp/cyber-release-smoke-v7-darwin-final
```

The smoke runs outside the checkouts with TRIDENT_* overrides removed. It
exercises direct and compiler-delegated source/build/run/prove/verify, imports,
project targets/profiles, owned network states, installed test execution,
batch proofs, program inspection, a genuine recursive Triton outer proof and
public JOYEXEC2, private JOYZK003 and authenticated-public-state JOYST001
artifacts. It checks changed claims, proof/compiled identities, target/state
selection, expected roots, missing secrets and changed state certificates.
Private queries use bounded fully public state tables.

The receipt is written only after all assertions pass. Binary and fixture
hashes are checked before and after the run. Exit 0; command wall time 141.50 s,
maximum RSS 9,278,767,104 bytes, swaps 0. The process-tree guard measured
9,351,577,600 bytes and elapsed 145.634 s including sampling overhead. Its
40 GiB / 8% free-memory stop conditions did not trigger. The `time` parent
footprint of 50,184,768 bytes is not the recursive prover's footprint.

Two earlier attempts are retained as harness failures, not product passes.
The first generated and verified its outer proof, then a Joy source check
inherited the temporary project's Neptune target and correctly rejected it.
Explicit `--target nox` fixes that selection. A fast replay then exposed a
debug/release compilation identity mismatch for the private source proof;
`--profile release` now matches its proving command. The intermediate rerun
was stopped before starting the final corrected run. All final checks passed
together; negative checks no longer succeed merely because of wrong target
selection.

Local logs: `/tmp/cyber-release-smoke-v7-darwin-final.log`,
`/tmp/cyber-release-smoke-v7-darwin-final-memory.log`. The preserved work directory
contains the genuine generated proofs and rejection fixtures.

The resulting Darwin binary archive is
`/tmp/cyber-tools-v7-darwin-aarch64-20260912-rehearsal.tar.gz`, SHA-256
`3bc8a02090bd91e80364e0368f65a945391889c2ade078776dd7b96b0ca1d544`.
A second independent packaging invocation produced identical archive bytes.
After extraction into another outside-checkout directory, all three binary
hashes, executable modes and all public fixture hashes matched. Fresh processes
from the unpacked archive verified the recursive proof and all four Joy
public/private/state artifacts; all eight version/verification commands exited 0.
Packaging rechecks all tested binary/fixture bytes and source provenance. See
[binary packaging](binary-packaging.md) for the archive layout and limitations.
Linux native proof execution is recorded separately in
[Linux runtime validation](linux-runtime-validation.md).

This smoke does not establish universal formal verification, dynamic nox
continuations, a private state database, GPU proving or public-network operation.
Actual isolated Neptune node admission has its own completed
[receipt](neptune-local-node-validation.md).
