# Coordinated source candidate FINAL3 — 2026-09-12

This working-tree candidate includes the bounded nox loop-return/scope repairs,
BBG's dependency-free neuron-id integration, checksum-pinned vendor bootstrap,
and complete source/fixture/script provenance checks. It has not been committed,
tagged or published as a coordinated release. Broader unimplemented language,
protocol and formal-verification requirements remain in the
[release ledger](../../trident/audit/full-release-preparation.md).

## Frozen source

Archive: `/tmp/cyber-release-source-v7-20260912-final3.tar.gz`, 29,276,242 bytes.
SHA-256: `515cf5a8d5565ad5f2551533c76847c0052c65c6510f4bd449189d341b28dc9b`.
Source inventory: `cc831a7da282d7998eb63756e96fc56915a8c1fa0c23f24daac06cb840a88a87`.
Vendor inventory: `c80346aea2594e3a51a6ed3f2fc78f0421ebc25601e7cbaaf99efd745f9fdcbf`.

The archive contains 11 repositories and 2442 repository entries, plus 557
patched vendor files. Neuron is included because current BBG imports its
dependency-free 32-byte identity alias. This does not add the rest of Neuron's
runtime to the compiler/warrior build closure. Complete current BBG public
certificate bytes match the earlier fixtures exactly; storage migration
compatibility is recorded in [the BBG audit](../../bbg/audit/release-dependency-continuation.md).

Extraction into a new directory preserves all inventory identities. Repacking
that extracted tree with its actual archive epoch, 1789204783, produces the
same archive SHA-256. An initial comparison used rehearsal1's older epoch and
correctly produced different metadata/bytes; it was not an archive defect.

Both hosts build from independently extracted copies using the archived
builder. It requires full source/vendor verification before and after Cargo,
publishes only a completed staging directory, and binds its verification
receipt in candidate.json. Smoke binds that receipt, its own script bytes,
all three binary hashes and all three state fixture hashes. Binary packaging
rechecks those identities and the source tree and ships the tested script
from the verified archive. Synthetic packaging tests are separate evidence.

## Validation entering this candidate

| Gate | Actual result |
|---|---|
| Trident workspace, neural | 858 passed, no failures/ignored/warnings |
| Joy complete workspace | 62 passed, no failures/ignored/warnings |
| Trisha all-features workspace | 428 passed, 3 explicit heavy tests ignored in ordinary suite |
| Trisha default CLI | 33 passed, 1 explicit heavy test ignored in ordinary suite |
| Explicit recursive/deployment tests | All 3 separately invoked and passed |
| Triton baselines | 43 programs, 99 positive fixtures, 198 fresh verified proofs; all 34 negative fixtures reject |
| Zheng / Lens / nox | 190 / 129 / 175 all-feature tests passed |
| Current BBG | 82 default tests without warnings; 152 all-feature tests with 3 existing Fjall warnings |
| Source verifier/builder | 9 tests pass on macOS and Linux Nu 0.112.2 |
| Binary packager | 3 synthetic boundary/reproducibility tests pass |

The newer nox changes affect its tree lowering and scope resolution; they do
not change Triton lowering or its pinned proof verifier. Baseline receipts
retain their original binary identities rather than being attributed to a
binary built later. Fresh installed smoke and node receipts for FINAL3 are
required separately. The earlier two-platform full smoke and real local node
admission belong to rehearsal1.

FINAL2's Linux builder failure occurred before Cargo because a captured mktemp
result was checked through an absent ambient LAST_EXIT_CODE. FINAL3 captures
the explicit process result and cleans owned staging on failure. The exact
failure and later Linux regression are retained in
[FINAL2 Linux validation](final2-linux-validation.md) and
[source verification](source-provenance-validation.md).

## Completed native validation

Both native candidates pass the archived full smoke, including actual recursive
outer proofs and public/private/authenticated-state Joy proofs with rejection
checks. Darwin build:368.78s, peakRSS5,006,589,952 bytes, zero warnings/swaps.
Darwin smoke:138.77s command time, peakRSS9,096,413,184 bytes, zero swaps; process
group monitor140.633s and9,120,186,368 bytes. Extra installed loop checks pass
34 commands, with12 paired executions, six public certificates and one private
proof. [Exact Darwin receipt](final3-darwin-receipt.json).

Darwin archive `/tmp/cyber-tools-final3-darwin-aarch64.tar.gz` has SHA256
`7d7ab29ad6c35cf69a41277e7535daa55fbe796c0594fc8c0797836abac29d47`.
A second packaging is byte-identical. Fresh extraction outside checkouts verifies
all binary/fixture/script/receipt hashes and modes; eight new version/proof
verification commands pass using only the extracted binaries on PATH.

Linux native build, full smoke, reproducible binary packaging and actual new
Trisha submission to a freshly isolated pinned Neptune node all pass. The exact
kernel enters its mempool; changed kernel and unauthorized submission reject;
node cleanup is confirmed. [Exact Linux evidence](final3-linux-validation.md).

## Superseding correctness repair

Additional accepted-source tests discovered that typed Triton `main` parameters
read initial stack registers instead of the public input stream. This candidate
therefore remains a historical validation checkpoint, not a release-ready final
artifact. The live typed-entry adapter and compiler API3 fix that defect; FINAL3
is deliberately unchanged. A fresh source/binary candidate must run the expanded
installed smoke, including typed parameter layout/ranges, genuine entry proofs
and claim mutations. [Finding and real-proof remediation](entry-abi-review.md).

