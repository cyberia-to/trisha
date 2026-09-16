# Trisha validation records

The full release is still being prepared. The coordinated work ledger is
`trident/audit/full-release-preparation.md` in the complete source tree.
These reports distinguish local runtime/node evidence from publication and
public-network operation. No release has been published.

- [Native release execution](native-release-20260916.md): current native builds,
  Windows fixes, installed proofs and exact CI/source identities.
- [Release platform review](platform-scope-review.md): Windows requirement,
  proposed six-target matrix, native validation coverage and portability gaps.

- [Compiler scratch/RAM blocker](ram-scratch-review.md): two confirmed source
  memory corruptions, preservation design and repair status. FINAL6 is blocked.
- [RAM preservation repair](ram-scratch-repair.md): stack cleanup, deep access
  and assembly repairs; complete execution baselines, eight fresh CLI proofs and
  exact before/after receipts. Fresh frozen-platform proof gates remain open.

- [FINAL6 coordinated candidate](final6-release-candidate.md): next exact source
  snapshot after ownership, file-reader, formal and dependency changes;
  native build and proof gates are tracked individually.
- [FINAL5 coordinated candidate](final5-release-candidate.md): current frozen
  native builds, installed proofs, reproducible archives and bidirectional
  proof verification; complete baseline gate status is recorded separately.
- [FINAL5 Linux evidence](final5-linux-validation.md): native installed/node
  admission and freshly unpacked cross-platform verification receipts.
- [Complete baseline gate](baseline-gate-review.md): exact candidate/input
  inventories, actual verified proof events and the corrected Python startup.
- [Current release tooling](current-release-tooling.json):24 actual packaging,
  source-inventory and proof-event gate tests.
- [Experimental tagged CCS proofs](tagged-ccs-validation.md): two real proofs
  with topology/input/cost binding; no production protocol integration claim.
- [Failed FINAL4 candidate](final4-release-candidate.md): preserved static
  loop-index failure, diagnosis and the correction included in FINAL5.
- [Workspace and CLI validation](final-workspace-validation.md): exact test
  totals, repaired PLUMB checks and separately invoked expensive proof gate.
- [Platform checks](platform-validation.md): Rust1.89 CPU and Linux cross-checks,
  with compilation distinguished from execution.
- [Recursive proofs](recursive-release.md): fresh Triton 7 source/hand STARKs,
  complete inventory accounting and actual prover memory observations.
- [Linux runtime validation](linux-runtime-validation.md): isolated native
  toolchain, source archive builds and installed runtime gates.
- [Source rehearsal](source-candidate-rehearsal.md): deterministic archive,
  exact provenance and native candidate binary hashes.
- [Source verification](source-provenance-validation.md): full source/vendor
  inventories, symlink boundaries and failure cleanup around candidate builds.
- [Installed smoke](installed-smoke-validation.md): complete macOS proof and
  rejection checks bound to installed binary and public-fixture hashes.
- [Binary packaging](binary-packaging.md): deterministic archives restricted to
  the exact installed binaries and fixtures that passed the full smoke.
- [Local Neptune node](neptune-local-node-validation.md): genuine SingleProof,
  actual authenticated CLI submission, exact mempool admission and cleanup.
- [Neptune adapter review](neptune-adapter-independent-review.md): independent
  intent, output, canonical JSON and authenticated transport inspection.
- [Native proof inputs](proof-input-review.md): canonical wire/claim/input
  validation, resource limits, malformed transcripts and remediation.
- [Neptune CLI](neptune-cli-release.md): selected network and wallet/node
  process behavior with isolated fixtures.
- [Mining compatibility](neptune-mining-compatibility.md): pinned consensus
  oracle, race/budget/template findings and subsequent repair receipts.
- [GPU claims](gpu-claims.md) and [older roadmap](legacy-roadmap-claims.md):
  unverified historical performance/status claims, retained as history.

Baseline fixtures and their oracle provenance are described in
[baselines/triton](../baselines/triton/README.md). Execution and full source/hand
proof coverage are separate gates. New evidence must preserve the43-file
inventory and disclose any implementation-specific public statements.
