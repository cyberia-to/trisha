# Changelog

## [unreleased]

### added
- `roadmap/` — individual proposal files replacing monolithic `reference/roadmap.md`
- `docs/explanation/` — architecture, GPU backend, proof file format, patching

## [0.1.0]

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
