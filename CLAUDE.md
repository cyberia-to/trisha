# Trisha — Claude Code Instructions

Triton VM warrior. Execute, prove, verify, deploy Trident programs.

## Source of Truth

`reference/` is the canonical reference for Trisha design decisions:

- `roadmap.md` — honest status, completion plan, confidence milestone

Any change to architecture or scope MUST update the corresponding
reference doc first, then propagate to code.

## Dependency Patching

Trisha patches triton-vm at build time instead of maintaining a fork.
The patch adds GPU acceleration hooks (GpuAccelerator trait + 3
dispatch points) to upstream triton-vm from crates.io.

```
patches/
  00-visibility.patch     Open internal types for external integration
  01-gpu-trait.patch      GpuAccelerator trait + global registration
  02-hash-dispatch.patch  GPU dispatch for Tip5 batch hashing
  03-intt-dispatch.patch  GPU dispatch for inverse NTT
  apply.nu                nushell script: fetch + apply all in order
```

After cloning or when upgrading triton-vm:
```
nu patches/apply.nu
```

This fetches triton-vm from cargo registry, applies the patch, and
places the result in `.vendor/triton-vm/`. Cargo.toml points to it
via `path = ".vendor/triton-vm"`. The `.vendor/` directory is
gitignored.

When upgrading triton-vm version: update `version` in `apply.nu`,
run the script, fix any patch conflicts, regenerate the patch file.

## Workspace

This repo (`~/git/trisha`) is a companion to `~/git/trident` (the
compiler). Trisha depends on trident via `path = "../trident"`.

When both repos are in scope:
- **trident** = the compiler (source -> TASM). ~37k LOC Rust.
- **trisha** = the runtime warrior (execute, prove, verify, deploy). ~2k LOC Rust + WGSL.
- Trident's CLAUDE.md rules (forbidden patterns, review passes, git
  workflow) apply to trisha too.
- When referencing files, always use the repo-qualified path
  (e.g. `trisha/src/cli.rs` vs `trident/src/cli/mod.rs`).
- Git operations: always `cd` to the correct repo before committing.
- After editing trident code that trisha depends on, rebuild both:
  `cd ~/git/trident && cargo install --path . --force &&
   cd ~/git/trisha && cargo install --path . --force`

## Architecture

Trisha implements trident's `Runner`, `Prover`, `Verifier`, `Deployer`
traits for Triton VM + Neptune. Standalone binary (`trisha`) discovered
by trident via `find_warrior()`.

```
src/
  lib.rs           Public API (re-exports modules for tests)
  main.rs          Entry point, clap dispatch
  cli.rs           CLI subcommands (run, prove, verify, deploy — each with batch)
  error.rs         TrishaError enum
  compile.rs       Source -> ProgramBundle via trident API
  convert.rs       Vec<u64> <-> BFieldElement type conversion
  warrior.rs       TrishaWarrior: trait implementations via GPU backend
  proof_file.rs    TOML envelope + bincode proof bytes (base64)
  batch.rs         Generic parallel executor (run_batch)
  gpu/
    mod.rs         GpuBackend trait (trace, prove, verify, verify_batch)
    cpu.rs         CPU fallback (delegates to triton-vm)
    wgpu_backend.rs  wgpu backend (Metal, Vulkan, DX12) — scaffolded, not wired
    shaders/
      goldilocks.wgsl  Field arithmetic (add, sub, mul, inv) via vec2<u32>
      ntt.wgsl         Radix-2 Cooley-Tukey butterfly NTT
      poseidon2.wgsl   Poseidon2 permutation for Merkle trees
      fri.wgsl         FRI query folding and verification
tests/
  integration.rs   12 end-to-end tests
```

## What Works vs What's Scaffold

**Working**: Runner, Prover, Verifier, Batch, Proof files, GPU
acceleration (Tip5 batch hashing, BFE/XFE iNTT on Metal/Vulkan/DX12).
Real STARK proofs generated and verified by triton-vm.

**Scaffold**: GPU Merkle tree, GPU FRI (shaders compile, not wired).
Deploy (prints digest, no Neptune integration).

See `reference/roadmap.md` for completion plan.

## CLI Contract

Every command supports single-file and batch modes:

```
trisha run <input.tri> [--input-values 1,2,3] [--secret 4,5,6]
trisha run batch <files...> [--max-parallel 4]

trisha prove <input.tri> [--output path.proof.toml] [--input-values 1,2,3]
trisha prove batch <files...> [--output dir/] [--max-parallel 4]

trisha verify <proof.proof.toml>
trisha verify batch <files...> [--max-parallel 4]

trisha deploy <input.tri> [--state testnet] [--proof proof.toml] [--dry-run]
trisha deploy batch <files...> [--max-parallel 4] [--dry-run]
```

stdout = machine-readable output, stderr = progress/diagnostics.

## Batch Executor

`batch::run_batch(jobs, max_parallel, closure)` is generic — any
operation can use it. Takes a `Vec<J>`, concurrency limit, and a
`Fn(J) -> T` closure. Returns `Vec<BatchResult<T>>` preserving
input order with per-job timing.

## GPU Backend

wgpu auto-detects the best native API:
- Metal on macOS
- Vulkan on Linux/Windows
- DX12 on Windows

GPU enabled by default (`--features gpu`). CPU-only: `--no-default-features`.
WGSL shaders use `vec2<u32>` to emulate u64 (Goldilocks field).

Currently: GPU is detected and shaders compile, but all computation
falls back to CPU. See `reference/roadmap.md` Phase A for wiring plan.

## Proof File Format (.proof.toml)

```toml
[proof]
format = "stark-triton-v2"
program_name = "hello"
cycle_count = 0
padded_height = 0
proving_time_ms = 40

[claim]
program_hash = ["1460305242624279511", "5843494972284683383", ...]
public_input = []
public_output = ["42"]

[data]
proof = "base64-encoded-bincode-bytes..."
```

Field elements serialized as strings (Goldilocks values exceed i64 range).

## Forbidden Patterns

- No `HashMap` — use `BTreeMap`
- No `.unwrap()` outside tests
- No `println!` in library code — stderr for progress, stdout for output
- No floating point
- No file > 500 lines

## Estimation Model

- **Pomodoro** = 30 minutes of focused work
- **Session** = 3 focused hours (6 pomodoros)

## Build & Test

```
nu patches/apply.nu  # first time only, or after version bump
cargo check
cargo test          # 15 integration tests
cargo install --path .
```

## Git Workflow

Atomic commits. Conventional prefixes: `feat:`, `fix:`, `refactor:`,
`test:`, `docs:`, `chore:`.
Rebuild after commit: `cargo install --path . --force`.

## License

Cyber License: Don't trust. Don't fear. Don't beg.
