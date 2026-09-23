# Historical roadmap claims — retained 2026-09-12

The text below was copied from the earlier roadmap before correcting its
status assertions. It is historical material, not current release evidence.
The default CLI proves on CPU; real cycle/height metadata is implemented.
Claims of complete GPU proving, speedups and mining readiness below lack
current pinned end-to-end receipts. Current evidence belongs in this audit
directory and the coordinated Trident release ledger.

---

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
| miner (CPU) | done | `trisha mine --neptune` — rayon, 0.33 MH/s on M4 Max | — |
| miner (wgpu) | done | Mine.wgsl + Tip5.wgsl wired into wgpu accelerator | not connected to neptune_mine.rs |
| miner (honeycrisp) | done | MSL Tip5 kernel, 1.1 MH/s (3.3× CPU), `--features gpu` | NEON/unimem zero-copy (Phase 2/3) |
| GPU shaders | done | 7 WGSL shaders (goldilocks, ntt, tip5, fri, poseidon2, gemv, mine) | — |
| GPU proving | done | all 7 hot paths: hash, iNTT, NTT, Merkle, FRI fold, GEMV | — |
| GPU verify | done | FRI fold on GPU, parallel batch via scoped threads | double-buffering |
| kernel fusion | done | NTT + Merkle: single command encoder, zero per-layer sync | — |
| persistent bufs | done | twiddle cache, two_inverse, Tip5 constants | — |
| staging pool | done | acquire/release across all 7 readback sites | — |
| VRAM streaming | done | budget awareness, chunked hash/GEMV, CPU fallback guards | streaming NTT (four-step FFT) |

## what's real

full prover pipeline on GPU. 7 compute shaders dispatched to Metal/Vulkan/DX12 via wgpu. kernel fusion eliminates per-layer CPU↔GPU sync. VRAM budget auto-detected from adapter limits; oversized buffers gracefully fall back to CPU. dependency patching injects GPU hooks into triton-vm without maintaining a fork. 4.3× proving speedup on small programs.

neptune HardforkBeta CPU mining: 0.33 MH/s on M4 Max (rayon + triton-vm Tip5). honeycrisp GPU mining: 1.1 MH/s (39 Tip5 permutations per nonce; Metal MSL kernel; compute-bound at ~65% GPU utilization — practical ceiling for this algorithm on M4 Max). GPU path activated via `--features gpu`; `trisha mine --neptune --bench-gpu 10` benchmarks. CPU+GPU combined: ~1.43 MH/s. wgpu Tip5 + Mine.wgsl shaders exist and compile but not wired into neptune_mine.rs.

## what's scaffold

deploy (prints metadata, no blockchain interaction). honeycrisp Phase 2 (NEON Tip5 via acpu) and Phase 3 (unimem zero-copy IOSurface).

## proposals

| proposal | status | goal |
|----------|--------|------|
| [[honeycrisp-npt-mining]] | phase-1-done | MSL Tip5 kernel live (1.1 MH/s); Phase 2: NEON+AMX; Phase 3: unimem zero-copy |
| [[gpu-proving-at-scale]] | open | streaming NTT for 2^25+ row traces |
| [[mining-tree]] | open | M=29 neptune mining tree (obsolete for mainnet — HFB removed memory-hard PoW) |
| [[proof-merging]] | open | `trisha merge` — proof-that-verifies-proof |
| [[real-workload-benchmarks]] | open | actual speedup numbers across trace sizes |
| [[double-buffered-batch]] | open | pipelined GPU batch verification |
| [[deploy]] | open | neptune-core integration, on-chain programs |
| [[missing-metadata]] | open | cycle_count, padded_height in proof file |
| [[helical-parallelism]] | open | multi-strand coprocessor proving: GPU hash + AMX field + NEON bookkeeping in parallel; O(log N) sequential depth |

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
