---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
status: open
---
# honeycrisp npt mining

Goal: make Apple Silicon the most efficient Neptune (NPT) miner available,
combining aruminium (bare-Metal GPU), acpu (NEON+AMX), and unimem
(zero-copy unified memory) into a single mining pipeline under
`trisha-honeycrisp`.

## situation

### network (as of 2026-05-22, block ~39295)

| metric | value |
|--------|-------|
| PoW algorithm | HardforkBeta (activated block 38000) |
| algorithm type | pure Tip5 hash search — no memory requirement |
| difficulty | ~11 × 10¹² |
| target block interval | 588 s (9.8 min) |
| implied network hashrate | ~18.8 GH/s |

HardforkBeta replaced memory-hard PoW (40 GB buffer, 63-hash index
derivation) with a simple fast_mast_hash check: ~11 Tip5 operations per
guess, zero random memory access. This makes the workload 100% compute-bound.

### per-guess operation count (HardforkBeta)

```
1  × Tip5::hash_pair          (nonce derivation)
1  × Tip5::hash_varlen/300    (encode nonce + zero paths: 30 perms)
3  × Tip5::hash_pair          (pow path through block MAST)
2  × Tip5::hash_varlen/5      (~1 perm each)
3  × Tip5::hash_pair          (kernel + header path)
──────────────────────────────────────────────────
~40 Tip5 permutations total per guess
```

Each Tip5 permutation:
- 5 rounds × (S-box + 16×16 MDS + round constants)
- ~30 Goldilocks multiplications per round = ~150 gl_mul per permutation
- ~6000 gl_mul per guess total

### measured baseline

| hardware | hashrate | power | KH/W |
|----------|----------|-------|------|
| M4 Max (16T, rayon, triton-vm Tip5) | 0.33 MH/s | ~30W | 11 |
| RTX 3090 (NPT-GPU-Miner v1.6) | ~9 MH/s† | 320W | 28 |
| RTX 4090 (NPT-GPU-Miner v1.6) | ~21 MH/s† | 280W | 75 |
| RTX 5090 (NPT-GPU-Miner v1.6) | ~39 MH/s† | 580W | 67 |

† v1.6 benchmarks are pre-HardforkBeta (memory-hard PoW). Post-HardforkBeta
GPU performance is uncharted; estimated 4–8× higher as the 63-hash index
derivation bottleneck is removed.

### what exists in this repo

| component | location | state |
|-----------|----------|-------|
| Tip5 WGSL shader | wgpu/shaders/tip5.wgsl | real, complete |
| Goldilocks WGSL | wgpu/shaders/goldilocks.wgsl | real, `vec2<u32>` encoding |
| Mine.wgsl kernel | wgpu/shaders/mine.wgsl | real, wired into wgpu backend |
| wgpu GPU dispatch | wgpu/accelerator.rs | real, 8 pipelines |
| NEON gl_mul | ~/cyber/honeycrisp/acpu/src/field/goldilocks.rs | real, `mul+umulh` asm |
| AMX GEMV | ~/cyber/honeycrisp/acpu/src/gemm/ | real, K-blocked AMX tiles |
| aruminium Metal dispatch | ~/cyber/honeycrisp/aruminium/src/ | real, IMP-resolved ~2μs |
| unimem IOSurface | ~/cyber/honeycrisp/unimem/ | real |
| Neptune HardforkBeta CPU mine | honeycrisp/neptune_mine.rs | real, rayon |
| Tip5 MSL shader (aruminium) | — | **missing** |
| NEON Tip5 permutation | — | **missing** |
| honeycrisp GPU mining wire-up | — | **missing** |

## architecture

```
┌─────────────────────────────────────────────────────┐
│              trisha mine --neptune                   │
│              honeycrisp/neptune_mine.rs              │
└───────────────┬───────────────────────────┬──────────┘
                │                           │
   ┌────────────▼──────────┐   ┌────────────▼──────────┐
   │  GPU path             │   │  CPU complement        │
   │  aruminium dispatch   │   │  NEON Tip5 (acpu)      │
   │  tip5.metal kernel    │   │  4-way interleaved     │
   │  ulong Goldilocks     │   │  gl_mul latency-hidden │
   │  unimem zero-copy     │   │                        │
   └────────────┬──────────┘   └────────────┬──────────┘
                │                           │
                └──────────┬────────────────┘
                           │
              ┌────────────▼──────────┐
              │  result merge         │
              │  submit winning nonce │
              │  via NeptuneClient    │
              └───────────────────────┘
```

The GPU evaluates nonce batches of 65536. The CPU generates the next
batch while the GPU computes. unimem IOSurface gives both sides access
to the same physical memory — no copy on dispatch or readback.

## implementation plan

### phase 0 — wire wgpu mine kernel into neptune_mine.rs (1–2 days)

The `wgpu` backend already has a working Mine.wgsl kernel and a `mine()`
dispatch method in accelerator.rs. The gap is that `honeycrisp/neptune_mine.rs`
never calls it — it only does CPU rayon.

**tasks:**

```
H0.1  add `trisha-wgpu` as optional dep to trisha-honeycrisp/Cargo.toml
H0.2  add WgpuBackend construction in neptune_mine::mine_hardfork_beta()
      behind cfg(feature = "gpu") — falls back to rayon if GPU unavailable
H0.3  wire nonce batch → accelerator.mine() → result poll
H0.4  benchmark: wgpu GPU MH/s on M4 Max vs 0.33 MH/s CPU baseline
```

This gives us GPU mining immediately using existing shaders. Expected: 8–15
MH/s on M4 Max with no new shader code.

**deliverable:** `trisha mine --neptune --backend gpu` works on Apple Silicon.

---

### phase 1 — aruminium Tip5 MSL kernel (1 week)

Replace the wgpu/WGSL path with a direct Metal/MSL kernel via aruminium.
Key advantage: Metal MSL has native `ulong` (64-bit unsigned integer) and
`ushort`/`uint` SIMD intrinsics. Goldilocks multiply with native `ulong` is
cleaner and faster than WGSL's `vec2<u32>` emulation.

**tip5.metal — Goldilocks field arithmetic:**

```metal
// p = 2^64 - 2^32 + 1.  epsilon = 2^32 - 1 = p.wrapping_neg()
constant ulong GL_P    = 0xFFFFFFFF00000001UL;
constant ulong GL_EPS  = 0x00000000FFFFFFFFUL;

// gl_mul: 64×64 → Goldilocks.
// Metal lacks mulhi64; emulate with four 32-bit multiplies.
ulong gl_mul(ulong a, ulong b) {
    uint a_lo = (uint)a, a_hi = (uint)(a >> 32);
    uint b_lo = (uint)b, b_hi = (uint)(b >> 32);
    // cross products — only hi lanes needed for reduction
    ulong lo   = (ulong)a_lo * b_lo;
    ulong mid1 = (ulong)a_lo * b_hi;
    ulong mid2 = (ulong)a_hi * b_lo;
    ulong hi   = (ulong)a_hi * b_hi;
    // combine to 128-bit {hi128, lo128}
    ulong lo128 = lo + (mid1 << 32) + (mid2 << 32);
    ulong hi128 = hi + (mid1 >> 32) + (mid2 >> 32)
                     + (lo128 < lo ? 1UL : 0UL);    // carry
    // reduce: 2^64 ≡ epsilon (mod p)
    ulong hi_hi = hi128 >> 32;
    ulong hi_lo = hi128 & GL_EPS;
    ulong t0    = lo128 - hi_hi;
    if (t0 > lo128) t0 -= GL_EPS;   // borrow
    ulong t1    = hi_lo * GL_EPS;
    ulong res   = t0 + t1;
    if (res < t0) res += GL_EPS;    // carry
    return res >= GL_P ? res - GL_P : res;
}
```

**kernel structure:**

```metal
kernel void npt_mine(
    device   ulong*  nonces_out  [[buffer(0)]],
    constant ulong*  path_a      [[buffer(1)]],  // 5*HEIGHT ulongs
    constant ulong*  mast_paths  [[buffer(2)]],  // pow+header+kernel digests
    constant ulong*  target      [[buffer(3)]],  // 5 ulongs (threshold)
    constant ulong&  nonce_base  [[buffer(4)]],
    device   atomic_uint* found  [[buffer(5)]],
    uint  tid [[thread_position_in_grid]])
{
    ulong nonce[5] = { nonce_base + tid, tid, ... };  // per-thread nonce

    // fast_mast_hash: ~40 Tip5 permutations
    ulong state[16] = {};
    tip5_absorb_300(state, nonce, path_a);            // hash_varlen(300 BFEs)
    tip5_hash_pair(state, mast_paths + 0*5);          // 3 hash_pairs: pow path
    tip5_hash_pair(state, mast_paths + 1*5);
    tip5_hash_pair(state, mast_paths + 2*5);
    tip5_hash_varlen_5(state, mast_paths + 3*5);      // hash_varlen(5) header
    tip5_hash_pair(state, mast_paths + 4*5);
    tip5_hash_pair(state, mast_paths + 5*5);
    tip5_hash_varlen_5(state, mast_paths + 6*5);      // hash_varlen(5) kernel
    tip5_hash_pair(state, mast_paths + 7*5);          // final hash_pair

    // compare digest vs target (lexicographic on 5-element Goldilocks tuple)
    if (digest_le(state, target)) {
        uint slot = atomic_fetch_add_explicit(found, 1, memory_order_relaxed);
        if (slot == 0) {
            for (int i = 0; i < 5; i++) nonces_out[i] = nonce[i];
        }
    }
}
```

Threadgroup size: 256. Grid: 65536 threads per dispatch = 65536 guesses per
aruminium call. Dispatch latency via IMP-resolved path: ~2 µs.

**tasks:**

```
H1.1  implement tip5.metal: gl_mul, gl_add, gl_sub, gl_pow7,
       sbox_layer (lookup for 4 elems + x^7 for 12), mds_layer (16×16
       circulant), tip5_permute (5 rounds), tip5_absorb_300, hash_pair,
       hash_varlen_5, fast_mast_hash
H1.2  implement npt_mine kernel (tid-based nonce, threshold compare, atomic CAS)
H1.3  add AruMine struct in honeycrisp/: compiles pipeline from tip5.metal,
       owns aruminium::Gpu + aruminium::Pipeline + unimem buffers
H1.4  expose mine_batch(nonce_base, path_a, mast_paths, target) -> Option<[u64;5]>
H1.5  replace wgpu path in mine_hardfork_beta() with AruMine::mine_batch()
H1.6  benchmark: aruminium MH/s vs wgpu MH/s, measure dispatch overhead
```

Expected: 12–20 MH/s on M4 Max, 24–40 MH/s on M4 Ultra.

**deliverable:** `mine_hardfork_beta` dispatches to Metal via aruminium.
Measured MH/s logged to stderr. wgpu removed from the hot path.

---

### phase 2 — NEON Tip5 CPU complement (3–4 days)

The GPU runs 65536-nonce batches. Between GPU dispatches (~1 ms each), the
CPU is idle. Fill that gap with a NEON-accelerated CPU path that runs
independently using acpu's existing `gl_mul`.

**4-way NEON interleaved Tip5:**

Tip5 permutation is sequential (each round depends on prior), but we can
interleave 4 independent hashes across NEON registers to hide the `gl_mul`
3-cycle multiply latency on M4:

```rust
// 4 independent Tip5 states in parallel, hiding gl_mul latency
// Each state: [u64; 16] mapped to 8× uint64x2_t NEON registers
pub fn tip5_permute_x4(
    s0: &mut [u64; 16],
    s1: &mut [u64; 16],
    s2: &mut [u64; 16],
    s3: &mut [u64; 16],
) {
    for _round in 0..5 {
        sbox_x4(s0, s1, s2, s3);   // x^7 via gl_mul chains, 4-way parallel
        mds_x4(s0, s1, s2, s3);    // 16×16 MDS, 4 states interleaved
        add_rc_x4(s0, s1, s2, s3); // XOR round constants
    }
}
```

4-way interleaving provides ~3× throughput improvement over scalar on M4
(eliminates mul stalls across independent chains).

**tasks:**

```
H2.1  implement tip5_permute in acpu/src/poseidon/ using gl_mul from
       acpu/src/field/goldilocks.rs.  scalar first, tested against
       triton-vm's Tip5 test vectors.
H2.2  implement 4-way NEON interleave: sbox_x4, mds_x4, add_rc_x4
       using uint64x2_t (NEON intrinsics, 2 states per register pair)
H2.3  implement hash_pair_neon, hash_varlen_neon using tip5_permute_x4
H2.4  implement fast_mast_hash_neon (all 8 Tip5 calls using NEON path)
H2.5  spawn CPU miner thread in neptune_mine running NEON path in parallel
       with GPU dispatch loop; merge results via AtomicBool found flag
H2.6  benchmark NEON vs triton-vm Tip5 on M4 Max (expect 2–4 MH/s CPU)
```

Expected: +2–4 MH/s from CPU complement running concurrently with GPU.

**deliverable:** CPU and GPU mine simultaneously. Total: 14–24 MH/s M4 Max,
26–44 MH/s M4 Ultra.

---

### phase 3 — unimem zero-copy pipeline (3 days)

Currently: GPU dispatch copies nonce batch into a staging buffer (CPU write),
dispatches compute, copies result back (CPU read). On Apple unified memory,
this copy is unnecessary — both CPU and GPU can directly read/write the same
physical page.

**unimem pipeline:**

```rust
// Persistent IOSurface buffers — allocated once, never copied
let nonce_buf  = unimem::Buffer::<u64>::new(BATCH * 5);  // nonces
let result_buf = unimem::Buffer::<u64>::new(5);           // winning nonce
let found_buf  = unimem::Buffer::<u32>::new(1);           // atomic flag

loop {
    // CPU: fill nonce_buf[0..BATCH] (direct write, no alloc)
    fill_nonces(nonce_buf.as_mut_slice(), nonce_base);

    // GPU: dispatch over nonce_buf, write to result_buf if found
    gpu.encode(|enc| {
        enc.set_buffer(0, &result_buf);
        enc.set_buffer(1, &nonce_buf);
        enc.dispatch(BATCH / 256, 256);
    });
    gpu.commit_and_wait();   // or async: double-buffer while CPU prepares next

    // CPU: check found_buf directly (no readback copy)
    if found_buf.as_slice()[0] != 0 {
        return Some(read_nonce(&result_buf));
    }
    nonce_base += BATCH as u64;
}
```

Double-buffer variant: while GPU executes batch N, CPU fills batch N+1.
Requires two IOSurface nonce buffers alternating.

**tasks:**

```
H3.1  integrate unimem::Buffer into AruMine for nonce_buf + result_buf
H3.2  eliminate all intermediate Vec<u64> allocations in the dispatch loop
H3.3  implement double-buffer: alternate A/B nonce buffers, CPU fills while
       GPU computes, commit_async + wait on prior batch
H3.4  benchmark: zero-copy vs staged-copy dispatch throughput
H3.5  measure peak MH/s with pipeline overlap on M4 Max
```

Expected: 10–20% throughput gain from eliminating copy overhead and
saturating GPU without stalls.

**deliverable:** Fully pipelined zero-copy mining loop. Peak MH/s measured.

---

## performance targets

| hardware | phase 0 | phase 1 | phase 2+3 | power | KH/W |
|----------|---------|---------|-----------|-------|------|
| M4 Max (40-core GPU) | 8–12 MH/s | 12–18 MH/s | 15–22 MH/s | ~45W | 333–489 |
| M4 Ultra (80-core GPU) | 16–24 MH/s | 24–36 MH/s | 30–44 MH/s | ~80W | 375–550 |
| RTX 4090 (est. post-HFB) | — | — | ~80–120 MH/s | 280W | 286–429 |

M4 Ultra matches or exceeds RTX 4090 in KH/W (energy efficiency) while
using 3.5× less power. Apple is structurally better positioned for mining
operations constrained by electricity cost or thermal budget.

## competitive thesis

1. **No NVIDIA dependency.** The entire Apple silicon stack (GPU + NEON + AMX)
   is self-contained. No CUDA driver updates, no NVML, no PCIe slot.

2. **Unified memory eliminates PCIe bottleneck.** The zero-copy unimem path
   means nonce batches never cross a PCIe bus. On a dedicated NVIDIA rig,
   every nonce batch traverses 16× PCIe lanes at ~32 GB/s. On Apple, it's
   direct physical memory access at >200 GB/s.

3. **First-mover in Apple mining.** The NPT GPU miner community is entirely
   NVIDIA-focused. No Apple MSL Tip5 kernel exists publicly. Shipping this
   before others captures the entire Mac mining market.

4. **MacBook as silent miner.** M4 Max in a MacBook Pro dissipates ~45W
   under GPU load — within its sustained thermal envelope. An RTX 4090 rig
   requires dedicated rack space, 1200W PSU, and industrial cooling.

5. **Foundation for STARK proving.** The same aruminium Tip5 kernel serves
   both mining and STARK proof generation (the Poseidon2/Tip5 FRI commit
   step). Phase 1 builds the primitive that phases everything else in the
   honeycrisp roadmap.

## dependency on honeycrisp workspace

This feature requires crates from `~/cyber/honeycrisp/`:

| crate | version | used for |
|-------|---------|---------|
| `aruminium` | workspace | Metal device, pipeline, buffer, dispatch |
| `acpu` | workspace | NEON `gl_mul`, `tip5_permute_x4` |
| `unimem` | workspace | IOSurface zero-copy buffers |

These are not yet dependencies of `trisha-honeycrisp/Cargo.toml`. Add them
as path dependencies gated behind `cfg(target_os = "macos")`.

## success criteria

```bash
# phase 0
trisha mine --neptune --backend gpu
# stderr: "M4 Max GPU: 12.3 MH/s (37.3× CPU baseline)"

# phase 1
trisha mine --neptune --backend honeycrisp
# stderr: "aruminium: 17.8 MH/s | dispatch: 2.1 µs | batch: 65536"

# phase 2+3
trisha mine --neptune --backend honeycrisp
# stderr: "GPU: 18.4 MH/s | CPU NEON: 3.1 MH/s | total: 21.5 MH/s"

# energy
# M4 Max @ 21 MH/s / 45W = 467 KH/W
# beats RTX 4090 @ 100 MH/s / 280W = 357 KH/W
```
