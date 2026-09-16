# FINAL4 coordinated candidate — 2026-09-12

Status: both native archive builds pass, but the Darwin installed smoke fails
on static-loop array indexing in the new imported-generic case. Linux reproduces
the same failure. No binary archives are packaged and no release is published.
This candidate includes the compiler API3 typed-entry adapters,
concrete generic checking/ownership, ordinary return validation, terminal and
intermediate branch semantics, declaration-order structs and canonical Field
literal emission. FINAL3 remains an unchanged earlier checkpoint.

## Frozen source

- Archive: `/tmp/cyber-release-source-v7-20260912-final4.tar.gz`.
- SHA-256: `28baabd0f50c0bacc52adde9c7a0188fa5f261d50defd570bf22cf82a766236f`.
- Size:29,379,900 bytes;11 repositories,2493 source entries,557 vendor entries.
- Source manifest SHA-256:
  `283aa90798a041915fa458af93402e6ceb7521eceb2489241efecf6ad71ddc91`.
- Source receipt: `/tmp/cyber-final4-source-receipt.json`.

This is an explicitly labelled working-tree snapshot. The strict committed
packager has its separate fixture rehearsal; production release commits have
not been created from this snapshot.

## Pre-build checks

- Trident:884 tests, including49 real nox source tests; zero failed/ignored.
- Trisha:448 all-feature workspace tests pass; five explicit proof/transaction
  tests remain ignored in this ordinary run and have separate proof gates.
- Joy:67 workspace tests pass, zero failed/ignored, including genuine private
  execution, typed-entry, terminal-return and state proofs.
- All-target/all-feature locked checks pass for all three workspaces; zero
  Rust warnings in checks and suites.
- Release tooling:23 Python tests pass in3.478s; Nushell smoke syntax validates.
- Current native baseline execution:133/133 fixtures,43/43 manual baselines.
  This execution-only run generates no proofs and is not the198-proof gate.

Exact logs: `/tmp/trident-final4-workspace-reviewed.log`,
`/tmp/trisha-final4-workspace-reviewed.log`, `/tmp/joy-final4-workspace.log`,
`/tmp/{trident,trisha,joy}-final4-check.log`,
`/tmp/trisha-final4-tooling-tests.log`,
`/tmp/trisha-final4-baseline-execution.log`.

## Artifact gates

Darwin source extraction:
`/tmp/cyber-release-extracted-v7-final4/cyber-source`.
Native build destination: `/tmp/cyber-release-installed-v7-darwin-final4`.
Host compiler:rustc1.95.0. Linux VM uses native aarch64 Rust1.89 with the exact
same archive in `/home/master.guest/release-validation/final4-20260912`.
Candidate binary identities and actual gate results will be recorded after each
completes. A started build or resource monitor is not a passing receipt.

Darwin build passes in325.71s with maximum RSS5,032,673,280bytes, zero swaps and
zero warnings. Its installed smoke fails after189.806s, peak process-group
RSS11,424,923,648bytes, without a memory stop. The preceding recursive,
public/private/state and typed-entry checks ran successfully, but no `smoke.json`
was created. Failure: `words[i]` inside the generic function's statically unrolled
`for i in 0..N` loses the known constant index during nox lowering.

Linux native build passes in8m01.05s, maximum RSS4,953,200KiB, zero warnings.
The Linux smoke was explicitly interrupted after90.214s when the identical-source
Darwin failure was known, then a cheap native run reproduced the same rejection.
The interrupted proof run is not a proof success or memory-guard failure.
No node gate or binary packaging ran for FINAL4. All owned processes terminated.

Darwin failure receipt:
`/tmp/cyber-release-smoke-v7-darwin-final4-receipt.json`.
Linux build/interruption/reproducer evidence: `/tmp/cyber-final4-linux/` and
`/tmp/cyber-final4-linux-imported-failure.log`. A subsequent source candidate must
include the scoped loop-index correction and rerun the installed gates.

The archived installed suite includes typed inputs, generic imports, terminal
branches, named-field order, canonical Field literals and rejection of invalid
returns, alongside recursive/public/private/state proof paths. The complete
baseline checker now requires explicit verified classic/hand proof events with
native program and public-claim binding, exact frozen inventories and resource
guards. Historical proof logs cannot supply missing events for this run.

The broader general nox, formal, self-hosting, FHE, external assurance and
publication obligations remain tracked in
`trident/audit/full-release-preparation.md`. This candidate is not a full release
readiness assertion.
