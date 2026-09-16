# Fresh Triton 7 recursive proofs — 2026-09-12

All six heavy baseline programs pass execution, fresh source and independent
hand-assembly proof generation, and fresh verification. This is **12 verified
outer STARKs for six positive fixtures**, not all 43 baselines. The separate
compiled SDK outer-proof test also passes. Historical Triton 2 receipts do not
establish these results.

The backend is pinned Triton/tasm-lib 7.0.0 with native claim version 5, four
Rayon threads and `TVM_LDE_TRACE=no_cache`. Runs were sequential on macOS arm64.
The memory setting changes caching, not the claim or security parameters.

| Baseline | Source cycles | Hand cycles | Padded height, each | Pair wall time (s) | Maximum RSS (bytes) | OS peak footprint (bytes) |
|---|---:|---:|---:|---:|---:|---:|
| recursive-proof | 430449 | 430441 | 524288 | 207.04 | 9945300992 | 9858932368 |
| recursive-verifier | 430449 | 430442 | 524288 | 206.47 | 9967484928 | 9864437368 |
| recursive-relay | 430463 | 430450 | 524288 | 206.20 | 9857236992 | 10973864264 |
| recursive-aggregate-two | 862385 | 862330 | 1048576 | 483.84 | 19554041856 | 19528906984 |
| neptune-transaction | 833066 | 833060 | 1048576 | 489.17 | 17617944576 | 19553335576 |
| native-currency | 578365 | 578310 | 1048576 | 418.78 | 19423707136 | 19489814928 |

Times and memory above are the direct `/usr/bin/time -l` observations for each
two-proof baseline process. RSS and OS footprint are different measurements;
neither is silently substituted for the other. Logs are
`/tmp/trisha-v7-full-<baseline>.log`; the extracted receipt is
`/tmp/trisha-v7-recursive-receipts.json`. Process-tree monitors are
`/tmp/trisha-v7-release-proof-memory.log` and
`/tmp/trisha-v7-native-proof-memory.log`.

The transaction run also passes four changed-claim rejection fixtures, for
5/5 fixtures in that selected directory. The six heavy programs have 18
fixtures in the complete inventory: six positives and twelve rejections.
Eight further rejection vectors were checked in the complete execution suite,
not in these selected full-proof runs. Rejected executions do not produce
proofs and are never counted as verified positive proofs.

## Compiled SDK release gate

`outer_proof_binds_compiled_recursive_sdk_to_public_claim` was explicitly run
with `--ignored`; it passes on Triton 7. The compiled recursive trace has
430989 cycles, padded height 524288. Proof generation took 130.946770958 s and
produced 130415 encoded fields. The test gate took 131.518268958 s; the Cargo
command including compilation took 169.55 s. The test verifies the fresh outer
proof and rejects a changed public claim.

The time command reports 9844441088 bytes maximum RSS. The process-tree monitor
observed 9871163392 bytes peak RSS. Its 108692056-byte OS footprint line refers
to the Cargo parent and **is not the outer prover's memory requirement**.
Log: `/tmp/trisha-v7-full-outer-sdk.log`.

## Bound statement and remaining gates

The generic SDK authenticates the expected complete native claim: program
digest, native version, full public input and output, and lengths. Neptune
transaction and native-currency policies additionally fix the canonical
upstream program and authorized commitment layout. An arbitrary prover-chosen
expected hash is not authorization for a caller's transaction.

The full inventory is now complete: **43 manual programs, 99 positive fixtures,
198 fresh verified source/hand STARKs and 34 rejected execution cases**. The
other 37 programs pass all 186 required proofs and 115/115 selected fixtures
(93 positives, 22 rejections); their command exited 0 with no resource-guard
stop. Wall time was 3057.42 s, maximum RSS 19177963520 bytes, monitored process
tree peak 19178422272 bytes and OS peak footprint 19321927936 bytes, zero swaps.
The frozen binary hash and exact receipt are preserved in
[full inventory](full-baseline-proof-coverage.json), including each fixture's
source/hand cycles and padding and hashes of the logs.

All 133 execution fixtures pass (`/tmp/h0003-bench.log`). Of the 34 rejection
vectors, 26 also ran in the selected `--full` groups; eight ran in the complete
execution suite. Rejection behavior does not generate proofs in either mode.
These proof receipts
do not demonstrate authenticated RPC submission, node mempool admission,
mining/finality, or complete GPU proving.
