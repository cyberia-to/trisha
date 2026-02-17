# Trisha Roadmap

Trisha closes the loop: source → compile → run → prove → verify → deploy.

## Current Status

| Layer | Status | What works | What's missing |
|-------|--------|------------|----------------|
| Runner | DONE | `trisha run` executes TASM via triton-vm | cycle count always 0 |
| Prover | DONE | `trisha prove` generates real STARK proofs | cycle_count, padded_height metadata |
| Verifier | DONE | `trisha verify` validates proofs | — |
| Batch | DONE | `trisha <op> batch` for all operations | — |
| Proof file | DONE | TOML + bincode, roundtrip tested | — |
| Deploy | STUB | Prints digest, says "not yet available" | No neptune-core, no RPC |
| Guesser | DONE | `trisha guess` — GPU nonce search, 24M H/s | Guesser tree (M=29) |
| GPU shaders | DONE | 7 WGSL shaders (goldilocks, ntt, tip5, fri, poseidon2, gemv, mine) | — |
| GPU proving | DONE | All 7 hot paths: hash, iNTT, NTT, Merkle, FRI fold, GEMV | — |
| GPU verify | DONE | FRI fold on GPU, parallel batch via scoped threads | Double-buffering |
| Kernel fusion | DONE | NTT + Merkle: single command encoder, zero per-layer sync | — |
| Persistent bufs | DONE | Twiddle cache, two_inverse, Tip5 constants | — |
| Staging pool | DONE | acquire/release across all 7 readback sites | — |
| VRAM streaming | DONE | Budget awareness, chunked hash/GEMV, CPU fallback guards | Streaming NTT (four-step FFT) |

**What's real**: Full prover pipeline on GPU. 7 compute shaders
dispatched to Metal/Vulkan/DX12 via wgpu. Kernel fusion eliminates
per-layer CPU↔GPU sync. VRAM budget auto-detected from adapter
limits; oversized buffers gracefully fall back to CPU. Dependency
patching injects GPU hooks into triton-vm without maintaining a fork.
4.3x proving speedup on small programs. Mining at 24M H/s (M1 Max).

**What's scaffold**: Deploy (prints metadata but no blockchain
interaction). Guesser tree (brute-force only, no tree structure).

---

## Remaining GPU Work

### Phase G1: Recursive Proof Traces at Scale

Recursive proof traces (2^25+ rows) haven't been tested. The VRAM
guards fall back to CPU — for recursive proofs the GPU barely helps.
Real streaming NTT (four-step FFT) would keep large NTTs on GPU
instead of falling back.

```
G1.1 Build or find a program that generates 2^20+ cycle traces
G1.2 Profile: where does time go? NTT? Hash? Merkle? GEMV?
G1.3 Four-step FFT: decompose large NTT into GPU-sized sub-NTTs
     - Split n-point NTT into sqrt(n) × sqrt(n) smaller NTTs
     - Each sub-NTT fits in VRAM, twiddle multiply between stages
G1.4 Streaming Merkle: chunk leaf hashing on GPU, build tree levels
     - Bottom levels chunked, upper levels fit in single buffer
G1.5 Benchmark: GPU vs CPU at 2^20, 2^22, 2^25 trace sizes
```

### Phase G2: Guesser Tree (M=29)

Our `mine()` is brute-force flat search (256K nonces/batch). Neptune
mining needs a tree structure with ~40GB of intermediate state. The
tree enables pruning and checkpoint/resume for long searches.

```
G2.1 Study Neptune guesser tree spec (SWBF, M=29 parameters)
G2.2 Design GPU-friendly tree layout (breadth-first, level buffers)
G2.3 Implement tree node hashing shader (Tip5 over tree paths)
G2.4 Host-side tree management: allocate levels, stream to GPU
G2.5 Unified memory path (Apple) vs PCIe streaming (discrete GPU)
G2.6 Benchmark: flat search vs tree search at various difficulties
```

### Phase G3: Proof Merging Pipeline

`trisha merge` doesn't exist. The Trident programs
(`recursive_verifier.tri`, `proof_aggregator.tri`) compile but have
never been run end-to-end with actual inner proof data as secret input.
This is the largest single proof workload — proof-that-verifies-proof.

```
G3.1 Wire proof bytes into ProgramInput.secret for recursive verifier
G3.2 trisha merge <proof1> <proof2> → runs proof_aggregator, outputs outer proof
G3.3 Test: prove poseidon2.tri, then prove the verifier of that proof
G3.4 Profile the recursive proof: expected 2^25+ cycles
G3.5 Optimize: this is where G1 (streaming traces) pays off
```

### Phase G4: Real Workload Benchmarks

The 4.3x speedup was on poseidon2.tri (2 ops, trivial). We don't
know where time goes for large traces or how GPU/CPU split changes
with program complexity.

```
G4.1 Build benchmark suite: trivial (2 ops), medium (1K ops),
     heavy (10K+ ops), recursive (verify-a-proof)
G4.2 Profile each: wall time, GPU dispatch %, CPU fallback %
G4.3 Identify bottlenecks per program size
G4.4 Publish results: table of program × GPU speedup
```

### Phase G5: Double-Buffered Batch Verification

Current batch verification uses thread::scope — parallel but no GPU
overlap between proofs. Double-buffering would pipeline CPU decode of
proof N+1 while GPU folds proof N.

```
G5.1 Two sets of FRI fold buffers (ping-pong)
G5.2 Pipeline: CPU prepare → GPU fold → CPU verify, overlapped
G5.3 Benchmark: batch of 4, 8, 16 proofs, speedup vs sequential
```

---

## Deploy — Neptune Integration

Requires `neptune-core` as a dependency.

```
B1. Add neptune-core dependency, study its API
B2. Implement deploy/lockscript.rs — TASM → LockScript wrapping
B3. Implement deploy/neptune.rs — tarpc client, send_transaction
B4. Implement deploy/transaction.rs — UTXO construction
B5. Wire into cmd_deploy, test on testnet
```

## Missing Metadata

```
C1. Capture cycle_count from VM::trace_execution
C2. Capture padded_height from Stark internals
C3. Write to proof file metadata
```

## Confidence Milestone

All of these must pass:

```bash
# CPU pipeline
trisha run /tmp/hello.tri
trisha prove /tmp/hello.tri --output /tmp/p.toml
trisha verify /tmp/p.toml

# Batch
trisha run batch /tmp/a.tri /tmp/b.tri
trisha prove batch /tmp/a.tri /tmp/b.tri --output proofs/
trisha verify batch proofs/a.proof.toml proofs/b.proof.toml

# GPU (currently passing)
trisha prove /tmp/hello.tri  # GPU dispatches NTT/Merkle/FRI/GEMV/Hash

# Mining (currently passing)
trisha guess /tmp/hello.tri --difficulty 1000000000000000000

# Deploy (not passing)
trisha deploy /tmp/hello.tri --state testnet

# Proof merging (not passing)
trisha merge proof1.toml proof2.toml --output merged.proof.toml
```

Currently passing: CPU pipeline, batch, GPU proving, GPU verification,
GPU mining.
Not passing: deploy, proof merging, recursive proofs at scale.
