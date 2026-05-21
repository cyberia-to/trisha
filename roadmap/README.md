---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
---
# trisha roadmap

trisha closes the loop: source → compile → run → prove → verify → deploy.

## status

| layer | status | what works | gap |
|-------|--------|------------|-----|
| runner | done | `trisha run` executes TASM via triton-vm | cycle count always 0 |
| prover | done | `trisha prove` generates real STARK proofs | cycle_count, padded_height metadata |
| verifier | done | `trisha verify` validates proofs | — |
| batch | done | `trisha <op> batch` for all operations | — |
| proof file | done | TOML + bincode, roundtrip tested | — |
| deploy | stub | prints digest, says "not yet available" | no neptune-core, no RPC |
| miner | done | `trisha mine` — gpu/honeycrisp/cpu backends, 24M H/s GPU | mining tree (M=29) |
| GPU shaders | done | 7 WGSL shaders (goldilocks, ntt, tip5, fri, poseidon2, gemv, mine) | — |
| GPU proving | done | all 7 hot paths: hash, iNTT, NTT, Merkle, FRI fold, GEMV | — |
| GPU verify | done | FRI fold on GPU, parallel batch via scoped threads | double-buffering |
| kernel fusion | done | NTT + Merkle: single command encoder, zero per-layer sync | — |
| persistent bufs | done | twiddle cache, two_inverse, Tip5 constants | — |
| staging pool | done | acquire/release across all 7 readback sites | — |
| VRAM streaming | done | budget awareness, chunked hash/GEMV, CPU fallback guards | streaming NTT (four-step FFT) |

## what's real

full prover pipeline on GPU. 7 compute shaders dispatched to Metal/Vulkan/DX12 via wgpu. kernel fusion eliminates per-layer CPU↔GPU sync. VRAM budget auto-detected from adapter limits; oversized buffers gracefully fall back to CPU. dependency patching injects GPU hooks into triton-vm without maintaining a fork. 4.3× proving speedup on small programs. mining at 24M H/s (M1 Max).

## what's scaffold

deploy (prints metadata, no blockchain interaction). mining tree (brute-force only, no tree structure).

## proposals

| proposal | status | goal |
|----------|--------|------|
| [[gpu-proving-at-scale]] | open | streaming NTT for 2^25+ row traces |
| [[mining-tree]] | open | M=29 neptune mining tree |
| [[proof-merging]] | open | `trisha merge` — proof-that-verifies-proof |
| [[real-workload-benchmarks]] | open | actual speedup numbers across trace sizes |
| [[double-buffered-batch]] | open | pipelined GPU batch verification |
| [[deploy]] | open | neptune-core integration, on-chain programs |
| [[missing-metadata]] | open | cycle_count, padded_height in proof file |

## confidence milestone

```bash
# cpu pipeline (passing)
trisha run /tmp/hello.tri
trisha prove /tmp/hello.tri --output /tmp/p.toml
trisha verify /tmp/p.toml

# batch (passing)
trisha run batch /tmp/a.tri /tmp/b.tri
trisha prove batch /tmp/a.tri /tmp/b.tri --output proofs/
trisha verify batch proofs/a.proof.toml proofs/b.proof.toml

# GPU (passing)
trisha prove /tmp/hello.tri  # dispatches NTT/Merkle/FRI/GEMV/Hash on GPU

# mining (passing)
trisha mine /tmp/hello.tri --difficulty 1000000000000000000

# not yet passing
trisha deploy /tmp/hello.tri --state testnet
trisha merge proof1.toml proof2.toml --output merged.proof.toml
```
