# Changelog

## [unreleased]

Coordinated candidate: **Trisha 0.3.0**, with Trident 0.3.0/compiler API 3 and
Joy 0.5.0. Final artifact gates and publication remain pending.

- Own Triton lowering/emission, cost and neural target integration, Neptune
  runtime modules/network states and all 43 independent manual baselines.
- Upgrade the native and recursive proof backend to pinned Triton/tasm-lib
  7.0.0, native claim version 5 and `stark-triton-v7`. Regenerate older proofs.
  Shared CPU/wgpu validation rejects noncanonical inputs, oversized domains,
  trailing proof items and malformed binary encodings.
- Verify complete expected native claims in the production recursive SDK.
  Fixed Neptune transaction/native-currency policies bind canonical programs
  and the caller's full commitments. File witnesses use private, new files.
- Add the pinned `trisha-neptune` adapter: construct canonical compiled-lock
  outputs, prepare complete SingleProof transaction intents, and submit through
  an explicitly authenticated gateway. Program inspection remains offline;
  generic deployment without transaction intent remains unsupported.
- Repair pinned Neptune mining fork/hash layouts, portable CPU hashing,
  CPU/GPU ownership, bounded nonce reservation and template refresh. Wallet
  import is interactive; selected network and wallet command outcomes are
  checked. Add the explicitly local `local-testnet1` state for real-proof tests.
- Correct compiler/stdlib behavior against independent execution and negative
  vectors. Fresh full proofs, device tests, formal analysis and node admission
  are recorded separately in [validation records](audit/README.md).
- Marshal typed source entry parameters from public input and constrain Bool/U32
  values. Preserve declaration-order struct fields and terminal return values;
  emit canonical native Field literals. Reject unresolved TIR diagnostics.
- Record each freshly verified classic/hand baseline proof with its exact
  program and public claim; installed gates require the complete proof pairs.
- Add deterministic source archives, locked fixture generation and isolated
  installed compiler/warrior smoke checks on coordinated source candidates.

The default prover is the CPU backend. Shader inventory and historical mining
numbers do not establish a complete GPU prover; current boundaries are in
[GPU architecture](docs/explanation/gpu-backend.md).

## [0.1.0]

Historical development notes. Performance claims below were not reproduced by
the current release review; see [archived GPU claims](audit/gpu-claims.md).

### added
- `trisha run` — execute Trident programs on Triton VM
- `trisha prove` — generate STARK proofs of execution
- `trisha verify` — verify STARK proofs
- `trisha deploy` — stub (prints digest, no neptune-core)
- `trisha guess` — GPU nonce mining, 24M H/s on M1 Max
- batch mode for all commands (`trisha <op> batch`)
- GPU backend: 7 WGSL shaders (goldilocks, ntt, tip5, fri, poseidon2, gemv, mine)
- kernel fusion: NTT + Merkle in single command encoder
- VRAM budget management with CPU fallback
- persistent buffers: twiddle cache, two_inverse, Tip5 constants
- staging pool: 8 pre-allocated readback buffers
- proof file format: `.proof.toml` (TOML envelope + bincode + base64)
- vendor patching: `patches/apply.nu` injects GPU hooks into triton-vm
- 4.3× proving speedup on small programs (M1 Max)
