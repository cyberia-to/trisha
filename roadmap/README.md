# Trisha roadmap

The release contract is the complete source → compile → run → prove → verify
path, with explicitly selected Neptune transaction and mining operations.
Current measurements and gate results live in [audit](../audit/README.md),
not in this specification. The coordinated release remains unpublished.

## Acceptance gates

| Component | Required evidence | Contract |
|---|---|---|
| Compiler and CPU warrior | Real source/import/profile/target tests, canonical input and fresh proof verification, tamper rejection | [architecture](../docs/explanation/architecture.md) |
| Metadata and artifact transport | Actual cycles/heights, native format7/version5, bounded canonical encodings | [proof file](../docs/explanation/proof-file-format.md) |
| Baselines | All43 independent hand algorithms; positive and rejection vectors; fresh source and hand proofs | [baseline contract](../baselines/triton/README.md) |
| Recursive SDK | Full authorized native claim, actual official verifier, compiled outer STARK | [recursive proof](../docs/reference/recursive-proof.md) |
| Neptune policy | Canonical0.15.1 SingleProof and NativeCurrency graph, complete kernel/UTXO binding | [recursive proof](../docs/reference/recursive-proof.md) |
| Neptune deployment | Explicit transaction intent, custom lock/output commitments, exact proof and transaction, network-bound transport and admission | [deployment](deploy.md) |
| Neptune mining | Correct consensus schedule, native hash/codec, bounded attempts, safe worker publication and template refresh | [mining review](../audit/neptune-mining-compatibility.md) |
| Optional GPU backends | Actual device/kernel equality and complete verified proof receipts for each advertised backend | [GPU architecture](../docs/explanation/gpu-backend.md) |
| Distribution | Committed source closure, pinned dependencies, tested installed binaries outside checkouts, platform receipts and hashes | [release scripts](../scripts/README.md) |

The default CLI proves with CPU. `--features gpu` selects Apple mining support.
Shader inventory, a successful adapter initialization or a nonce benchmark
cannot establish complete GPU proving. Retained older status claims and
unverified timings are in [historical roadmap claims](../audit/legacy-roadmap-claims.md).

## Further proposals

Streaming proofs, helical parallelism, proof merging, double-buffered batches
and alternate hardware backends retain their individual proposal files.
They require their own acceptance evidence before runtime capabilities advertise
them. The production recursive SDK already has an explicit witness/outer-proof
contract; that does not imply a separate `trisha merge` command exists.
