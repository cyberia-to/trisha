# Trisha — Claude Code Instructions

Triton VM warrior. Execute, prove, verify, deploy Trident programs.

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
  cli.rs           CLI subcommands (run, prove, prove-batch, verify, deploy)
  error.rs         TrishaError enum
  compile.rs       Source -> ProgramBundle via trident API
  convert.rs       Vec<u64> <-> BFieldElement type conversion
  warrior.rs       TrishaWarrior: trait implementations via GPU backend
  proof_file.rs    TOML envelope + bincode proof bytes (base64)
  batch.rs         Batch/streaming prover (parallel across threads)
  gpu/
    mod.rs         GpuBackend trait (trace, prove, verify, verify_batch)
    cpu.rs         CPU fallback (delegates to triton-vm)
    wgpu_backend.rs  wgpu backend (Metal, Vulkan, DX12)
    shaders/
      goldilocks.wgsl  Field arithmetic (add, sub, mul, inv) via vec2<u32>
      ntt.wgsl         Radix-2 Cooley-Tukey butterfly NTT
      poseidon2.wgsl   Poseidon2 permutation for Merkle trees
      fri.wgsl         FRI query folding and verification
tests/
  integration.rs   12 end-to-end tests
```

## CLI Contract

```
trisha run <input.tri> [--input-values 1,2,3] [--secret 4,5,6]
trisha prove <input.tri> [--output path.proof.toml] [--input-values 1,2,3]
trisha prove-batch <input1.tri> <input2.tri> ... [--output dir/] [--max-parallel N]
trisha verify <proof.proof.toml>
trisha deploy <input.tri> [--state testnet] [--proof proof.toml] [--dry-run]
```

stdout = machine-readable output, stderr = progress/diagnostics.

## GPU Backend

wgpu auto-detects the best native API:
- Metal on macOS
- Vulkan on Linux/Windows
- DX12 on Windows

GPU enabled by default (`--features gpu`). CPU-only: `--no-default-features`.
WGSL shaders use `vec2<u32>` to emulate u64 (Goldilocks field).

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
cargo check
cargo test          # 12 integration tests
cargo install --path .
```

## Git Workflow

Atomic commits. Conventional prefixes: `feat:`, `fix:`, `refactor:`,
`test:`, `docs:`, `chore:`.
Rebuild after commit: `cargo install --path . --force`.

## License

Cyber License: Don't trust. Don't fear. Don't beg.
