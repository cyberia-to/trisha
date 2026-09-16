# FINAL5 coordinated candidate — 2026-09-12

Status: native macOS and Linux builds and full installed proof smoke pass.
Linux Neptune admission and Mac→Linux proof verification also pass. Both native
binary archives reproduce byte-for-byte. The complete198-proof baseline gate
was started against the exact frozen macOS candidate. Its final receipt was not
recovered on2026-09-16 after the temporary work directory became unavailable;
completion remains unconfirmed. The later [RAM review](ram-scratch-review.md)
also identifies a source-correctness defect in the legacy scratch strategy.
No release has been published.

FINAL5 corrects the scoped nox loop-index defect that stopped FINAL4 and the
smoke script's access to nested proof claim fields. It retains the actual
imported-generic scenario that exposed the defect. All other production source
and dependency repositories match FINAL4.

- Source archive: `/tmp/cyber-release-source-v7-20260912-final5.tar.gz`.
- SHA-256: `7c63fcad9d12a220036b531f85eacc1a91984ff87c18687703aeeac57b3df415`.
- Size:29,383,684 bytes;11 repositories,2497 source entries,557 vendor entries.
- Source manifest SHA-256:
  `41c924603d1ed20b78844a4a5cc1aa78e3dff759349d98f1713015e5cfb124a0`.
- Source receipt: `/tmp/cyber-final5-source-receipt.json`.

Before freezing, the complete Trident neural workspace passes888 tests, zero
failed/ignored/warnings (`/tmp/trident-loop-index-workspace.log`), including53
real nox source tests. Four new tests cover nested indexed reads/writes, bounded
loop returns, constant shadowing and U32 index limits. Independent Joy tests
cover the exact failed source in both profiles and both input cases, eight
public certificates and four genuine private STARKs, with input/output mutations
rejected. See `joy/audit/loop-index-smoke-review.md`.

A separate development CLI replay of the installed-smoke remainder passes,
including all sixteen generic/struct/terminal native routes, actual source/claim
proof verification and expected type errors. This replay first found the script's
incorrect top-level proof field access; the corrected script reads `claim` and
rejects a mutated generic proof. Receipt:
`/tmp/cyber-loop-index-postcheck-receipt.json`. It is a targeted CLI regression,
not the complete installed gate. The unchanged Triton branch has its FINAL4
448-test all-feature workspace receipt; the prior complete Joy suite passes67.

Both platforms built from the same extracted archive and verified its complete
source/vendor inventory before and after compilation. Darwin uses native
rustc1.95.0; the Linux aarch64 VM uses Rust1.89. The quick installed imported-loop
case passed before each full proof smoke. Source extraction/repacking also
produced byte-identical archives at epoch1789211405:
`/tmp/cyber-final5-source-repack.json`.

Darwin destination: `/tmp/cyber-release-installed-v7-darwin-final5`.
Linux workspace: `/home/master.guest/release-validation/final5-20260912`.
Build logs: `/tmp/cyber-release-build-v7-darwin-final5.log` and
`/tmp/cyber-final5-linux-build.log`.

## Native build and installed proof results

| Gate | macOS aarch64 | Linux aarch64 |
|---|---|---|
| Native build | PASS336.05s; peak process RSS4,983,504,896bytes; zero warnings/swaps | PASS499.55s; peak process RSS4,977,308KiB; zero warnings |
| Complete installed smoke | PASS195.525s; peak group RSS9,872,900,096bytes; zero swaps | PASS222.810s; peak group RSS7,822,966,784bytes; no swap configured |
| Memory guard | No stop; minimum free76% | No stop; minimum available8,408,342,528bytes |

Both smoke runs use4 Rayon threads and `TVM_LDE_TRACE=no_cache`. Exact harness
SHA-256: `73c48275e69574eabfe3c99f1009e05617ab7532449ecab04f3cf5bd229fd988`.
They include genuine recursive Triton outer proofs, public/private/state Joy
paths, typed entries, imported generics, terminal branches, named struct fields,
loop-index scope, source checking and altered-claim/input rejection.
Darwin monitor receipt: `/tmp/cyber-release-smoke-v7-darwin-final5-receipt.json`;
full script receipt: `/tmp/cyber-release-smoke-v7-darwin-final5/smoke.json`.
Linux details and exact node/cross-platform receipts:
[native Linux validation](final5-linux-validation.md).

| Darwin binary | SHA-256 |
|---|---|
| trident | 287d643dbb92467ac5e1bdc572b9e2f04949779b0fe7e022e86d84cc506e3ea7 |
| trisha | 9265f599c5200f330d29da19f1fccfeb18d5b9cdd905ba713bd15a068532d47b |
| joy | 331a9ce3aa373bcb3d3c32331a5bdbb30d31de45be9e9b92574c7058930aafa5 |

Binary archives:

- Darwin: `/tmp/cyber-tools-final5-darwin-aarch64.tar.gz`, SHA-256
  `72152fb93cb6e5d1aa7dd6a6cc46282d0070479896d2299711a25b88e4885f19`.
- Linux: `/tmp/cyber-final5-linux/cyber-tools-linux-aarch64-final5.tar.gz`, SHA-256
  `de77709b3d46d312e9f04ef28d4d1747d8b3634668a5b1db0d70c2c1166368c5`.

Each archive was made twice by the archived packager from the actual full smoke
receipt and compared byte-for-byte. Their different platform hashes are expected;
the source provenance and verification identities are the same.

Freshly unpacked Darwin binaries also pass16 original proof verifications:
eight generated on Darwin and eight on Linux. Native claims match across both
platforms; Joy verification pins expected public inputs/output and state fixtures.
Ten wrong-output checks reject. Fresh source compilation, nox assembly/bundle
execution, Triton assembly execution and a newly generated native proof of
input35→output42 pass outside the checkouts with only the unpacked binaries on
PATH. All19 archive entries, binary executable modes, fixtures, harness and
verification identities were checked. Receipt:
`/tmp/cyber-final5-darwin-artifact-gate/receipt.json`, retained with build/smoke
evidence in [Darwin receipt](final5-darwin-receipt.json).

Earlier temporary unpack-check harness attempts used an incorrect CLI contract
(assembly named as JSON, a nonexistent Trident `--emit`, bracketed stdout or
positional TASM). They stopped and have no success receipt. The complete check
uses `joy build` for JSON bundles, `trident build` for assembly and Trisha's
explicit `--tasm`; the logs are preserved under `/tmp/cyber-final5-darwin-*`.

## Complete baseline gate and tooling correction

The frozen complete checker was started with this exact command:

```sh
python3 -B /tmp/cyber-release-extracted-v7-final5/cyber-source/trisha/scripts/check-baselines.py /tmp/cyber-release-installed-v7-darwin-final5 /tmp/cyber-final5-baseline-proof-gate
```

It requires99 positive fixtures with198 freshly generated and verified proof
events,34 actual rejection vectors and all43 independent manual programs, with
complete unchanged source/vendor/binary inventories before and after. The work
directory retains `started.json`, `bench.log`, `memory.jsonl` and, only after the
run finishes, its result receipt. Older proof events are not reused.

The initial default-Python preflight created importlib bytecode inside the
source tree and correctly failed inventory verification before any baseline
proof started. Failure: `/tmp/cyber-final5-baseline-startup-bytecode-failure.log`.
Only the generated bytecode was removed; all archived bytes remain unchanged.
The `-B` run above is the actual FINAL5 proof invocation. The live checker now
prevents bytecode writes itself;10 tests pass including a genuine subprocess
inventory regression and a removed-fix control. This later live tooling change
is absent from FINAL5. [Tooling evidence](baseline-gate-review.md).

This remains a working-tree source rehearsal. The full release ledger retains
the broader general nox/formal/self-hosting/FHE/assurance and final publication
obligations. FINAL4's failure and interrupted Linux proof run are preserved.
