---
tags: trisha, docs
crystal-type: pattern
crystal-domain: cyber
alias: trisha architecture
---
# architecture

trisha is the runtime half of the soft3 proof stack.

```
trident (compiler)          trisha (runtime)
─────────────────           ─────────────────────────────────────
source .tri files           TrishaWarrior
      ↓                           ↓
 parse + type check          runner (execute)
      ↓                      prover (STARK prove)
 codegen → TASM              verifier (STARK verify)
      ↓                      deployer (neptune on-chain)
 ProgramBundle ──────────→  batch executor
                             GPU backend (7 shaders)
```

trident produces a `ProgramBundle` (TASM bytecode + type info + metadata). trisha takes that bundle and does the actual work: execution, proof generation, verification, deployment.

trisha implements trident's four runtime traits:

| trait | what it does |
|-------|-------------|
| `Runner` | execute the program, collect outputs |
| `Prover` | generate a STARK proof of execution |
| `Verifier` | verify a STARK proof |
| `Deployer` | package + submit to neptune (stub) |

`TrishaWarrior` in `warrior.rs` implements all four.

## stack position

```
neurons / apps
      ↓
  trident (compile)
      ↓
  trisha (execute + prove + verify)
      ↓
  triton-vm (STARK engine, vendored + patched)
      ↓
  GPU (Metal / Vulkan / DX12 via wgpu)
```

triton-vm is the STARK engine. trisha patches it at build time (via `patches/apply.nu`) to inject GPU acceleration hooks without maintaining a fork. the patch adds a `GpuAccelerator` trait with three dispatch points: Tip5 batch hashing, iNTT, and NTT.

## binary discovery

the `trisha` binary is discovered at runtime by trident's `find_warrior()`. trident delegates execution to whatever warrior binary is on `$PATH`. this keeps the compiler and runtime independently versioned.

## module map

```
src/
  lib.rs          re-exports all public modules
  main.rs         clap dispatch → cli commands
  cli.rs          five commands: run, prove, verify, deploy, guess
  warrior.rs      TrishaWarrior: implements Runner/Prover/Verifier/Deployer
  compile.rs      source → ProgramBundle via trident API
  error.rs        TrishaError enum (no unwrap in library code)
  proof_file.rs   TOML envelope + bincode proof bytes (base64)
  batch.rs        generic parallel executor (run_batch)
  convert.rs      Vec<u64> ↔ BFieldElement
  gpu/
    mod.rs          GpuBackend trait
    cpu.rs          CPU fallback via triton-vm
    wgpu_backend.rs wgpu backend (Metal/Vulkan/DX12)
    tip5_accel.rs   Tip5 GPU batch hashing
    shaders/
      goldilocks.wgsl  field arithmetic (vec2<u32> to emulate u64)
      ntt.wgsl         radix-2 Cooley-Tukey butterfly NTT
      poseidon2.wgsl   Poseidon2 permutation for Merkle trees
      fri.wgsl         FRI query folding and verification
      gemv.wgsl        matrix-vector multiply (polynomial evaluation)
      tip5.wgsl        Tip5 batch hashing
      mine.wgsl        nonce mining kernel (24M H/s on M1 Max)
```
