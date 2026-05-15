---
tags: trisha, docs
crystal-type: pattern
crystal-domain: cyber
alias: trisha GPU backend
---
# GPU backend

trisha accelerates seven hot paths via custom WGSL compute shaders dispatched through wgpu. a single backend targets Metal (macOS), Vulkan (Linux/Windows), and DX12 (Windows) without platform-specific code.

## seven shaders

| shader | operation | role in prover |
|--------|-----------|---------------|
| `goldilocks.wgsl` | field arithmetic | foundation for all other shaders |
| `ntt.wgsl` | radix-2 NTT | polynomial interpolation (iNTT) and evaluation (NTT) |
| `poseidon2.wgsl` | Poseidon2 permutation | Merkle tree hashing |
| `fri.wgsl` | FRI fold + query | FRI low-degree test |
| `gemv.wgsl` | matrix-vector multiply | polynomial evaluation at challenge points |
| `tip5.wgsl` | Tip5 batch hash | Fiat-Shamir transcript, commitment hashing |
| `mine.wgsl` | nonce search | `trisha guess` mining kernel |

## Goldilocks field in WGSL

WGSL has no native u64. every field element is stored as `vec2<u32>` — (lo, hi) pair in little-endian 32-bit halves. Montgomery form is used for multiplication to avoid 128-bit intermediates.

```wgsl
// Goldilocks: p = 2^64 - 2^32 + 1
// R = 2^32 - 1, R^2 mod p = 0xFFFFFFFE00000001
struct Gl { lo: u32, hi: u32 }

fn gl_add(a: Gl, b: Gl) -> Gl { ... }
fn gl_mul(a: Gl, b: Gl) -> Gl { ... } // Montgomery
fn gl_inv(a: Gl) -> Gl { ... }        // Fermat: a^(p-2)
```

## kernel fusion

NTT and Merkle hashing share a single command encoder with zero per-layer CPU sync. the CPU submits the full sequence — butterfly passes → hash layers — and the GPU executes without round-tripping to host between stages.

## VRAM budget management

at init, wgpu queries the adapter for `max_buffer_size` and `max_storage_buffers_per_shader_stage`. trisha computes a VRAM budget and:
- buffers that fit → GPU dispatch
- buffers that overflow → chunked GPU dispatch or CPU fallback

this means trisha handles 4GB GPU laptops and 192GB M1 Ultra workstations with the same code path.

## persistent buffers

three buffers are allocated once and reused across proofs:
- twiddle factors (NTT roots of unity)
- `two_inverse` (constant for butterfly normalization)
- Tip5 round constants (256 × u64)

allocation cost is paid once at `WgpuBackend::new()`.

## staging pool

GPU results must be readback to CPU for verification. eight staging buffers are pre-allocated in a pool. `acquire()` / `release()` prevent re-allocation across the 7 readback sites.

## current speedup

on poseidon2.tri (2-op program, M1 Max):

| operation | CPU time | GPU time | speedup |
|-----------|----------|----------|---------|
| prove | 1.2s | 280ms | 4.3× |
| mine (nonces/s) | 2M | 24M | 12× |

large programs (2^25+ trace rows) fall back to CPU at NTT; [[gpu-proving-at-scale]] is the fix.

## enabling / disabling GPU

GPU is on by default (`--features gpu`). CPU-only build:

```
cargo build --no-default-features
```

`GpuBackend::try_new()` returns `None` if no GPU is found; `TrishaWarrior` falls back to `CpuBackend` automatically.
