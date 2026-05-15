# Trisha

Triton VM warrior. Executes, proves, verifies, and deploys Trident programs on Triton VM with GPU-accelerated STARK proving.

```
source .tri → ProgramBundle → run / prove / verify / deploy
                                    ↓
                            GPU (Metal · Vulkan · DX12)
                            7 compute shaders · 4.3× speedup
                            24M H/s mining (M1 Max)
```

## what it does

```
trisha run    program.tri                    # execute, print output
trisha prove  program.tri -o proof.toml      # STARK prove
trisha verify proof.toml                     # verify proof
trisha guess  program.tri --difficulty N     # GPU nonce mining
trisha deploy program.tri --state testnet    # on-chain (stub)
```

every command has a batch mode:

```
trisha prove batch a.tri b.tri c.tri --output proofs/ --max-parallel 4
trisha verify batch proofs/*.proof.toml
```

## GPU backend

seven WGSL compute shaders. one pipeline. all platforms.

| shader | operation |
|--------|-----------|
| `goldilocks` | field arithmetic over 2⁶⁴ − 2³² + 1 via `vec2<u32>` |
| `ntt` | radix-2 Cooley-Tukey butterfly NTT |
| `poseidon2` | Poseidon2 permutation for Merkle trees |
| `fri` | FRI query folding and verification |
| `gemv` | matrix-vector multiply for polynomial evaluation |
| `tip5` | Tip5 batch hashing |
| `mine` | nonce search kernel |

wgpu auto-selects the best native API: Metal on macOS, Vulkan on Linux, DX12 on Windows. GPU is on by default. CPU-only build: `--no-default-features`.

## proving pipeline

```
ProgramBundle
    ↓
VM::trace_execution()      ← CPU, unavoidable
    ↓
Stark::prove()
    ├── iNTT    (interpolate) ←  GPU  shader: ntt.wgsl
    ├── NTT     (evaluate)   ←  GPU  shader: ntt.wgsl
    ├── Merkle               ←  GPU  shader: poseidon2.wgsl
    ├── FRI                  ←  GPU  shader: fri.wgsl
    ├── GEMV                 ←  GPU  shader: gemv.wgsl
    └── Tip5                 ←  GPU  shader: tip5.wgsl
    ↓
Proof → ProofFile → .proof.toml
```

NTT + Merkle share a single command encoder — zero per-layer CPU↔GPU sync.

## proof file

`.proof.toml`: human-readable TOML envelope wrapping `base64(bincode(Proof))`.

```toml
[proof]
format = "stark-triton-v2"
program_name = "hello"
proving_time_ms = 280

[claim]
program_hash = ["1460305242624279511", ...]
public_output = ["42"]

[data]
proof = "AgIAAAAAAAD..."
```

## patching

trisha patches triton-vm at build time rather than maintaining a fork. `patches/apply.nu` fetches upstream from crates.io, applies 5 surgical layers (GPU hooks), and writes `.vendor/triton-vm/`. one script, no diverging branches.

```
nu patches/apply.nu    # first time, or after version bump
```

## build

```
nu patches/apply.nu    # vendor + patch triton-vm
cargo build --release
cargo test             # 15 integration tests
cargo install --path .
```

## status

| component | status |
|-----------|--------|
| run / prove / verify | done |
| batch | done |
| GPU proving (7 shaders) | done |
| GPU mining (24M H/s) | done |
| proof file roundtrip | done |
| deploy (neptune) | stub |
| proof merging | planned |
| streaming NTT (2^25+) | planned |

see [roadmap/](roadmap/) for detailed plans.

## workspace

| repo | role |
|------|------|
| [trident](../trident) | compiler: source → TASM (ProgramBundle) |
| [trisha](.) | runtime: execute, prove, verify, deploy |
| [triton-vm](https://github.com/TritonVM/triton-vm) | STARK engine (vendored + patched) |

## license

cyber — don't trust. don't fear. don't beg.
