# Trisha — Claude Code Instructions

Triton VM warrior. Execute, prove, verify, deploy Trident programs.

## Structure

```
roadmap/     — individual proposals (one file per feature/phase)
docs/
  explanation/ — architecture, GPU backend, proof format, patching
cli/         — trisha binary (Cargo crate: trisha)
rs/          — CPU backend (Cargo crate: trisha-rs)
wgpu/        — wgpu/Metal/Vulkan backend (Cargo crate: trisha-wgpu)
honeycrisp/  — Apple Silicon backend stub (Cargo crate: trisha-honeycrisp)
patches/     — vendor patching scripts
.claude/plans/ — agent state (persists across sessions)
```

## Source of Truth

`roadmap/README.md` — status overview and confidence milestone.
`roadmap/<feature>.md` — individual proposals (open/done).
`docs/explanation/` — design rationale.

Any change to architecture or scope MUST update the corresponding
reference doc first, then propagate to code.

## Dependency Patching

Trisha patches triton-vm at build time instead of maintaining a fork.
The patch adds GPU acceleration hooks (GpuAccelerator trait + 8
dispatch points) to upstream triton-vm from crates.io.

```
patches/
  gpu.rs     GpuAccelerator trait — the only new Rust file
  apply.nu   fetch upstream + overlay gpu.rs + str replace
```

The apply script works in 9 named layers (0–8):
0. Copy `gpu.rs` into vendor
1. Export `pub mod gpu` in lib.rs
2. Widen `pub(crate)` → `pub` on types we need
3. GPU dispatch for Tip5 batch hashing
4. GPU dispatch for iNTT (polynomial interpolation)
5. GPU dispatch for Merkle tree construction
6. GPU dispatch for FRI split-and-fold
7. GPU dispatch for forward NTT (restore original trace)
8. GPU dispatch for weighted_sum_of_columns (GEMV)

Also patches `twenty-first` (T0): adds `MerkleTree::from_nodes()`.

After cloning or when upgrading triton-vm:
```
nu patches/apply.nu
```

This fetches triton-vm and twenty-first from cargo registry, applies
patches, and places the result in `.vendor/`. Workspace Cargo.toml
patches them via `[patch.crates-io]`. The `.vendor/` directory is gitignored.

When upgrading triton-vm version: update `version` in `apply.nu`,
run the script, fix any patch conflicts.

## Workspace

This repo (`~/cyber/trisha`) is a Cargo workspace with 4 member crates.
It is a companion to `~/cyber/trident` (the compiler).

Members:
- `cli/` — binary crate `trisha` (the actual `trisha` command)
- `rs/` — lib crate `trisha-rs` (CPU backend, complete)
- `wgpu/` — lib crate `trisha-wgpu` (Metal/Vulkan/DX12, Tip5+NTT+FRI wired)
- `honeycrisp/` — lib crate `trisha-honeycrisp` (Apple Silicon, stub)

Each crate uses `[lib] path = "lib.rs"` or `[[bin]] path = "main.rs"` —
**no `src/` subdirectory anywhere**.

When both repos are in scope:
- **trident** = the compiler (source -> TASM). ~37k LOC Rust.
- **trisha** = the runtime warrior (execute, prove, verify, deploy). ~3k LOC Rust + WGSL.
- Trident's CLAUDE.md rules (forbidden patterns, review passes, git
  workflow) apply to trisha too.
- When referencing files, always use the repo-qualified path
  (e.g. `trisha/cli/prove.rs` vs `trident/src/cli/mod.rs`).
- Git operations: always `cd` to the correct repo before committing.
- After editing trident code that trisha depends on, rebuild both:
  `cd ~/cyber/trident && cargo install --path . --force &&
   cd ~/cyber/trisha && cargo install --path . --force`

## Architecture

Trisha implements trident's `Runner`, `Prover`, `Verifier`, `Deployer`
traits for Triton VM + Neptune. Standalone binary (`trisha`) discovered
by trident via `find_warrior()`.

The `cli/` crate is the interface — independent of backend choice.
Backend selection: change `trisha-rs` dep in `cli/Cargo.toml` to
`trisha-wgpu` or `trisha-honeycrisp` when those are ready.

```
cli/              Binary crate (package name: trisha)
  main.rs         Entry point + Cli/Command/NetworkArgs + shared helpers
  error.rs        TrishaError enum
  state.rs        State registry (STATES, resolve, default_state)
  neptune.rs      NeptuneClient + neuron file helpers
  compile.rs      Source -> ProgramBundle via trident API
  proof_file.rs   TOML envelope + bincode proof bytes (base64)
  batch.rs        Generic parallel executor (run_batch)
  run.rs          trisha run (single + batch)
  prove.rs        trisha prove (single + batch)
  verify.rs       trisha verify (single + batch)
  deploy.rs       trisha deploy (single + batch)
  mine.rs         trisha mine (PoW nonce search, all 3 backends)
  node.rs         trisha node status
  neuron.rs       trisha neuron (balance, address, boxes, create, import, remove)
  state_cmd.rs    trisha state (list, show)

rs/               CPU backend (crate: trisha-rs)
  lib.rs          pub mod convert; pub mod warrior; pub use warrior::Warrior
  convert.rs      Vec<u64> <-> BFieldElement type conversion
  warrior.rs      Warrior: Runner/Prover/Verifier/Deployer/Guesser via triton-vm
  tests/
    integration.rs  End-to-end run/prove/verify tests

wgpu/             wgpu backend (crate: trisha-wgpu)
  lib.rs          pub use warrior::Warrior
  convert.rs      (same as rs/convert.rs)
  warrior.rs      Warrior: GPU init + same CPU proving path + GPU mining
  backend.rs      WgpuBackend (compiled pipelines) + create_tip5_accelerator
  accelerator.rs  WgpuTip5Accelerator — implements triton_vm::gpu::GpuAccelerator
  shaders/
    goldilocks.wgsl  Field arithmetic via vec2<u32>
    ntt.wgsl         Radix-2 Cooley-Tukey butterfly NTT
    poseidon2.wgsl   Poseidon2 permutation for Merkle trees
    fri.wgsl         FRI query folding and verification
    tip5.wgsl        Tip5 permutation
    mine.wgsl        PoW mining kernel
    gemv.wgsl        BFE/XFE weighted sum (GEMV)

honeycrisp/       Apple Silicon stub (crate: trisha-honeycrisp)
  lib.rs          Warrior stub — all methods return Err("not yet implemented")
```

## What Works vs What's Scaffold

**Working**: Runner, Prover, Verifier, Batch, Proof files (with real
`cycle_count` and `padded_height`), neuron balance/address/boxes/create,
node status, multi-state network selection, GPU acceleration (Tip5
batch hashing, BFE/XFE iNTT on Metal/Vulkan/DX12).

**Scaffold**: GPU Merkle tree, GPU FRI, GPU NTT wiring (shaders compile,
not connected to proving path). Deploy (computes and prints digest,
no Neptune transaction construction yet). honeycrisp backend.

See `roadmap/README.md` for completion plan.

## Multi-State Architecture

Trisha follows trident's union/state vocabulary:
- **union** = OS/network (e.g. `neptune`)
- **state** = chain instance (e.g. `mainnet`, `testnet`)

Known states live in `cli/state.rs`. All network-touching commands
(`neuron`, `node`, `deploy`) accept `--union` and `--state` flags via
the shared `NetworkArgs` struct (flattened into each command's args).
`--rpc-port` is an escape hatch that overrides the state's default port.

```
trisha neuron balance                          # neptune/mainnet (default)
trisha neuron balance --state testnet          # neptune/testnet
trisha node status --union neptune --state mainnet
trisha state list                              # show all known states
trisha state show neptune testnet
```

Adding a new state: append an entry to `STATES` in `cli/state.rs`.
No other files need to change.

## CLI Contract

```
trisha run <input.tri> [--input-values 1,2,3] [--secret 4,5,6]
trisha run batch <files...> [--max-parallel 4]

trisha prove <input.tri> [--output path.proof.toml] [--input-values 1,2,3]
trisha prove batch <files...> [--output dir/] [--max-parallel 4]

trisha verify <proof.proof.toml>
trisha verify batch <files...> [--max-parallel 4]

trisha deploy <input.tri> [--union neptune] [--state mainnet] [--dry-run]
trisha deploy batch <files...> [--max-parallel 4] [--dry-run]

trisha neuron balance [--union neptune] [--state mainnet]
trisha neuron address add [--key-type generation] [--index N]
trisha neuron address hide <address>
trisha neuron address show <address>
trisha neuron address list [--all]
trisha neuron boxes
trisha neuron create
trisha neuron import <word1> ... <word24>
trisha neuron remove [--confirm]

trisha node status [--union neptune] [--state mainnet]

trisha state list
trisha state show <union> <name>
```

stdout = machine-readable output, stderr = progress/diagnostics.

## Batch Executor

`batch::run_batch(jobs, max_parallel, closure)` is generic — any
operation can use it. Takes a `Vec<J>`, concurrency limit, and a
`Fn(J) -> T` closure. Returns `Vec<BatchResult<T>>` preserving
input order with per-job timing.

## Backends

Three independent implementations — no shared code between them:

- **rs** (`rs/`) — pure Rust via triton-vm. `Warrior::new()` prints `Backend: cpu`. Complete.
- **wgpu** (`wgpu/`) — cross-platform GPU (Metal/Vulkan/DX12). `Warrior::new()` inits GPU,
  registers Tip5 accelerator with triton-vm's prover, falls back to CPU gracefully.
  Shaders and pipelines compile; full NTT/Merkle/FRI dispatch pending.
- **honeycrisp** (`honeycrisp/`) — Apple Silicon bare-metal (aruminium Metal + acpu AMX/NEON).
  Not yet implemented. Will use MSL shaders and IOSurface zero-copy.

The `cli/` crate currently depends on `trisha-rs`. Switch to `trisha-wgpu` by
changing the dep in `cli/Cargo.toml` and updating `use trisha_rs::Warrior` →
`use trisha_wgpu::Warrior` in each CLI command file.

## Proof File Format (.proof.toml)

```toml
[proof]
format = "stark-triton-v2"
program_name = "hello"
cycle_count = 42317        # real value from aet.processor_trace.nrows()
padded_height = 65536      # real value from aet.padded_height()
proving_time_ms = 8240

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
cargo test -p trisha-rs  # runs rs/tests/integration.rs
cargo install --path cli --force
```

## Git Workflow

Atomic commits. Conventional prefixes: `feat:`, `fix:`, `refactor:`,
`test:`, `docs:`, `chore:`.
Rebuild after commit: `cargo install --path cli --force`.

## License

Cyber License: Don't trust. Don't fear. Don't beg.
