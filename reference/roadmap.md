# Trisha Roadmap

Trisha closes the loop: source → compile → run → prove → verify → deploy.

## Current Status (honest)

| Layer | Status | What works | What's missing |
|-------|--------|------------|----------------|
| Runner | DONE | `trisha run` executes TASM via triton-vm | cycle count always 0 (VM::run doesn't expose it) |
| Prover | DONE | `trisha prove` generates real STARK proofs | cycle_count, padded_height metadata not captured |
| Verifier | DONE | `trisha verify` validates proofs | — |
| Batch | DONE | `trisha <op> batch` for all operations | — |
| Proof file | DONE | TOML + bincode, roundtrip tested | — |
| Deploy | STUB | Prints digest, says "not yet available" | No neptune-core dep, no RPC, no LockScript, no UTXO |
| GPU trait | DONE | GpuBackend trait, CPU fallback, wgpu init | — |
| WGSL shaders | DONE | 5 shaders (goldilocks, ntt, poseidon2, fri, tip5) | — |
| GPU Tip5 hash | DONE | Tip5 batch hashing on GPU via GpuAccelerator | — |
| GPU NTT | DONE | iNTT on BFE + XFE columns via ntt.wgsl | — |
| GPU Merkle | DONE | Tip5 hash_pair shader, level-by-level GPU build | — |
| GPU FRI fold | DONE | XFE arithmetic shader, split-and-fold on GPU | — |
| GPU forward NTT | DONE | Forward NTT on BFE + XFE columns, same butterfly shader | — |
| GPU GEMV | DONE | Weighted column sums: BFE×XFE and XFE×XFE via compute shader | — |
| GPU proving | DONE | All 7 hot paths dispatched: hash, iNTT, NTT, Merkle, FRI fold, GEMV | — |
| GPU verify | NOT STARTED | wgpu backend falls back to CPU | Verifier FRI fold smaller workload |

**What's real**: Runner, Prover, Verifier work end-to-end. 22 tests
pass. Proofs are genuine STARK proofs verified by triton-vm. GPU
accelerates seven proving hot paths: Tip5 leaf hashing, iNTT on
main table columns (BFE), iNTT on aux table columns (XFE via
coefficient deinterleaving), forward NTT (restore original trace),
Merkle tree construction (Tip5 hash_pair), FRI split-and-fold
(XFieldElement arithmetic), and GEMV weighted column sums (linear
combination). All dispatched to Metal/Vulkan/DX12 via wgpu.
Dependency patching injects GPU hooks into triton-vm without
maintaining a fork.

**What's scaffold**: Deploy (prints metadata but no blockchain
interaction).

## Completion Plan

### Phase A: GPU Wiring (~8 pomodoros, 2 sessions)

The hard problem: triton-vm does NTT, Merkle trees, and FRI internally.
To GPU-accelerate, we need to either:

1. **Fork triton-vm** and replace internal NTT/Merkle/FRI with trait
   objects that dispatch to our GPU backend. Invasive but correct.

2. **Pre/post GPU**: run the full trace on CPU, then do NTT and Merkle
   tree construction on GPU before feeding back into triton-vm's
   prover. Requires understanding triton-vm's internal data flow.

3. **Wait for triton-vm GPU support**: the triton-vm project may add
   GPU support natively. Monitor their roadmap.

Option 2 is the pragmatic path:

```
A1. Extract trace data from triton-vm's prove_program internals
    - Use VM::trace_execution to get AET
    - Feed AET columns into GPU NTT
A2. GPU NTT: upload twiddle factors + columns, dispatch ntt_butterfly
    - Buffer management, download results
A3. GPU Merkle: Poseidon2 hash pairs on GPU for tree construction
    - Level-by-level dispatch
A4. Integrate GPU NTT/Merkle into proving pipeline
    - Replace triton-vm's internal calls with GPU results
A5. GPU FRI: fold queries on GPU during verification
A6. Benchmark CPU vs GPU, validate proof equivalence
```

### Phase B: Deploy — Neptune Integration (~6 pomodoros, 1 session)

Requires `neptune-core` as a dependency.

```
B1. Add neptune-core dependency, study its API
    - tarpc RPC interface, port 9799
    - LockScript, TypeScript types
    - UTXO, Transaction, Coin types
B2. Implement deploy/lockscript.rs
    - TASM -> LockScript wrapping
    - Compute lock_script_hash (Tip5 digest)
B3. Implement deploy/neptune.rs
    - tarpc client connecting to running Neptune node
    - send_transaction, wait_confirmation
B4. Implement deploy/transaction.rs
    - UTXO construction with lock script
    - Transaction building
B5. Wire into cmd_deploy, test on testnet
```

### Phase C: Missing Metadata (~1 pomodoro)

```
C1. Capture cycle_count from VM::trace_execution
    - Use AET processor_trace.nrows() for cycle count
C2. Capture padded_height from Stark internals
C3. Write to proof file metadata
```

### Phase D: Tests + Polish (~2 pomodoros)

```
D1. GPU benchmark tests (CPU vs wgpu, same program)
D2. Deploy integration test (against Neptune testnet)
D3. Batch stress test (10+ programs in parallel)
```

## Estimation

| Phase | Pomodoros | Sessions | Prerequisite |
|-------|----------|----------|--------------|
| A. GPU wiring | 8 | 1.3 | Understanding triton-vm internals |
| B. Neptune deploy | 6 | 1.0 | Running Neptune node |
| C. Metadata | 1 | 0.2 | — |
| D. Tests | 2 | 0.3 | A + B |
| **Total** | **17** | **2.8** | |

## Confidence Milestone (unchanged)

All of these must pass:

```bash
# CPU pipeline
trisha run /tmp/hello.tri                          # stdout: 42
trisha prove /tmp/hello.tri --output /tmp/p.toml   # proof written
trisha verify /tmp/p.toml                          # PASS

# Batch
trisha run batch /tmp/a.tri /tmp/b.tri             # parallel execution
trisha prove batch /tmp/a.tri /tmp/b.tri --output proofs/
trisha verify batch proofs/a.proof.toml proofs/b.proof.toml

# GPU
trisha prove /tmp/hello.tri  # stderr: "GPU: Apple M1 Max (Metal)"
                              # GPU actually does NTT/Merkle, not just detect

# Deploy
trisha deploy /tmp/hello.tri --state testnet       # tx_hash returned

# Tampered proof
# Flip byte -> FAIL
```

Currently passing: CPU pipeline, batch, GPU detection.
Not passing: GPU computation, deploy.

## Dependencies

```toml
# Current
trident-lang = { path = "../trident" }
triton-vm = "2"
twenty-first = "1"
wgpu = "24"

# Phase B (not yet added)
neptune-core = { git = "..." }   # for deploy
tokio = { version = "1", features = ["rt", "net"] }  # for tarpc
tarpc = "0.34"
```
