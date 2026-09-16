**The Triton warrior owns the complete CPU execution and proof path.** Trisha 0.3 takes Trident's typed program through Triton code generation, execution, native and recursive proofs, and validated Neptune transaction preparation. It ships with Trident 0.3.0 and Joy 0.5.0 as one coordinated toolchain.

1. **Triton and Neptune implementation moves into Trisha.** Code generation, instruction costs, target-specific optimization hooks, Neptune runtime modules, network descriptions and all 43 hand-written baselines now live beside the warrior. Trident retains the shared compiler interfaces. This makes the ownership match the runtime that actually executes and proves the code.
2. **Native proofs move to pinned Triton 7.** Execution and proving share canonical input and claim validation, including field ranges, domain bounds and strict proof decoding. Older proof formats must be regenerated; malformed or trailing data cannot silently become an accepted proof.
3. **Recursive proofs check the statement the caller requested.** The recursive SDK binds the complete inner claim: program, public input and public output. Neptune transaction and native-currency policies also pin their canonical programs and full commitments. This prevents accepting a valid proof of a different statement.
4. **Neptune deployment becomes a validated transaction flow.** The new adapter builds canonical outputs for compiled locks, validates a complete SingleProof transaction intent and submits through an explicitly authenticated gateway. Program inspection remains offline. A compiled program alone is not treated as a deployable transaction; successful admission is checked against a pinned native Neptune node.
5. **Program execution and input handling are corrected.** Typed entry arguments, aggregate field order, terminal returns, field literals and spilled RAM values preserve source semantics. Independent vectors exercise compiler and standard-library behavior; negative vectors check rejection. Each full baseline proof records the exact program and public claim that was generated and verified.
6. **CLI and distribution work across native platforms.** Wallet operations respect the selected network, validate upstream command outcomes and import secrets through the interactive input path. File handling rejects invalid, oversized and linked inputs. The release includes native macOS, Linux and Windows archives for ARM64 and x64, with embedded runtime resources and deterministic packaging.

**Install:** extract the archive for your platform and add `cyber-tools/bin` to PATH. Each archive contains `trident`, `trident-lsp`, `trisha` and `joy`; keep them together. Windows binaries statically link the MSVC runtime. The coordinated source archive contains all 11 local repositories and the pinned patched Triton sources; Cargo still needs the locked upstream dependencies.

<!-- RELEASE_DOWNLOADS -->
| Platform | ARM64 | x64 |
|---|---|---|
| macOS | [Download](https://github.com/cyberia-to/trisha/releases/download/v0.3.0/cyber-tools-aarch64-apple-darwin.tar.gz) | [Download](https://github.com/cyberia-to/trisha/releases/download/v0.3.0/cyber-tools-x86_64-apple-darwin.tar.gz) |
| Linux (glibc) | [Download](https://github.com/cyberia-to/trisha/releases/download/v0.3.0/cyber-tools-aarch64-unknown-linux-gnu.tar.gz) | [Download](https://github.com/cyberia-to/trisha/releases/download/v0.3.0/cyber-tools-x86_64-unknown-linux-gnu.tar.gz) |
| Windows | [Download](https://github.com/cyberia-to/trisha/releases/download/v0.3.0/cyber-tools-aarch64-pc-windows-msvc.zip) | [Download](https://github.com/cyberia-to/trisha/releases/download/v0.3.0/cyber-tools-x86_64-pc-windows-msvc.zip) |
<!-- /RELEASE_DOWNLOADS -->

**Upgrade:** use Trident 0.3.0 and compiler API 3. Regenerate earlier native and recursive proofs for `stark-triton-v7` / native claim version 5. Triton baselines and Neptune resources now belong to this repository. Neptune wallet commands need the upstream Neptune CLI; actual submission requires the configured authenticated gateway/node.

**Scope:** the shipped prover is the CPU backend. GPU mining and a complete GPU prover are separate capabilities; this release does not certify the latter. Neptune validation uses a real-proof isolated node and does not claim public-network block confirmation.

<!-- RELEASE_VALIDATION -->
**Validation:** all six native targets pass the CPU suites, all 133 execution fixtures, installed proof/certificate smoke and native process/file probes. Every producer's corpus verifies on every consumer: **36 platform pairs, 1,692 checks**, including rejected mutations. The final macOS ARM64 binaries additionally generated and verified **198 fresh baseline proofs**, covering all 43 hand-written programs; this full proof run was measured once on the dedicated 48 GiB worker. The exact released Linux ARM64 client passed admission and rejection checks against the isolated pinned Neptune node.

See [native builds](https://github.com/cyberia-to/trisha/actions/runs/35116488433), [cross-platform verification](https://github.com/cyberia-to/trisha/actions/runs/35125655070), the [validation summary](https://github.com/cyberia-to/trisha/releases/download/v0.3.0/release-validation.json), [complete logs, receipts and proof corpora](https://github.com/cyberia-to/trisha/releases/download/v0.3.0/release-validation.tar.gz), and [SHA-256 checksums](https://github.com/cyberia-to/trisha/releases/download/v0.3.0/SHA256SUMS). These records bind validation to the released source and binary hashes.
<!-- /RELEASE_VALIDATION -->

Source commit: `ba5fca686c81dbf4c5cd1970b309553b0d875b14`.
