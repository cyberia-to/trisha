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
honeycrisp/  — portable/Apple mining; separate Warrior proving API remains a stub
neptune/     — pinned consensus/RPC transaction intent adapter (trisha-neptune)
patches/     — vendor patching scripts
lib/os/neptune/ — Neptune runtime modules, embedded at build time
examples/experimental/neptune/ — unimplemented recursive proof prototypes, excluded from packages
baselines/triton/ — hand TASM and explicit execution fixtures
scripts/     — reproducible source release packaging
.claude/plans/ — agent state (persists across sessions)
```

## Source of Truth

`roadmap/README.md` — acceptance gates and proposal index.
`roadmap/<feature>.md` — individual contracts/proposals.
`docs/explanation/` and `docs/reference/` — architecture and API contracts.
`audit/` — measured results, review findings and release evidence.
`../trident/audit/full-release-preparation.md` — coordinated active ledger.

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

This fetches the eight pinned upstream crates through `patches/fetch.py`,
verifies their archive SHA-256 values against `patches/upstream.json`, applies
patches, and places the result in `.vendor/`. Cached `.crate` bytes are verified
before extraction; unpacked Cargo source directories are not trusted inputs.
Workspace Cargo.toml patches them via `[patch.crates-io]`. The `.vendor/`
directory is gitignored.

When upgrading Triton: update the coordinated versions and verified checksums
in `upstream.json` and both patch scripts, run the scripts, resolve patch
conflicts and repeat native/recursive proof acceptance gates.

## Workspace

This repo (`~/cyber/trisha`) is a Cargo workspace with 5 member crates.
It is a companion to `~/cyber/trident` (the compiler).

Members:
- `cli/` — binary crate `trisha` (the actual `trisha` command)
- `rs/` — lib crate `trisha-rs` (CPU backend, complete)
- `wgpu/` — lib crate `trisha-wgpu` (Metal/Vulkan/DX12, Tip5+NTT+FRI wired)
- `honeycrisp/` — lib crate `trisha-honeycrisp` (CPU/Apple mining; standalone proving Warrior remains a stub)
- `neptune/` — lib crate `trisha-neptune` (pinned consensus/RPC intent validation and submission adapter)

Each crate uses `[lib] path = "lib.rs"` or `[[bin]] path = "main.rs"` —
**no `src/` subdirectory anywhere**.

When both repos are in scope:
- **trident** = shared frontend, TIR, nox lowering and generic neural harness.
- **trisha** = Triton lowering/emission, runtime warrior, Neptune libraries and baselines.
- Trident's CLAUDE.md rules (forbidden patterns, review passes, git
  workflow) apply to trisha too.
- When referencing files, always use the repo-qualified path
  (e.g. `trisha/cli/prove.rs` vs `trident/src/cli/mod.rs`).
- Git operations: always `cd` to the correct repo before committing.
- After editing trident code that trisha depends on, rebuild both:
  `cd ~/cyber/trident && cargo install --path . --force &&
   cd ~/cyber/trisha && cargo install --path cli --locked --force`

## Architecture

Trisha implements trident's `Runner`, `Prover`, `Verifier`, `Deployer`
traits for Triton VM + Neptune. Standalone binary (`trisha`) discovered
by trident via `find_warrior()`.

The `cli/` crate is the interface — independent of backend choice.
The CLI uses `trisha-rs` for execution/proving. Mining backend selection is
separate; a GPU mining feature never silently switches the prover. Neptune
transaction dependencies belong in `neptune/`, outside the CPU engine/compiler.

```
cli/              Binary crate (package name: trisha)
  main.rs         Entry point + Cli/Command/NetworkArgs + shared helpers
  error.rs        TrishaError enum
  state.rs        State registry (STATES, resolve, default_state)
  neptune.rs      NeptuneClient + neuron file helpers
  compile.rs      Source -> shared TIR -> Trisha TASM -> core bundle metadata
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

honeycrisp/       CPU/Apple mining (crate: trisha-honeycrisp)
  cpu.rs          raw Montgomery Tip5 facade; portable fallback/Apple acpu
  warrior.rs      separate non-default proving API remains unimplemented
neptune/          pinned consensus/RPC transaction adapter
  lib.rs          canonical intent and SingleProof/output binding
  transport.rs    explicit local/gateway submission transport
```

## Release claims

Runtime capabilities and the audit receipts govern supported behavior. The
default CPU source/run/prove/verify path uses native Triton7/version5 and real
cycle/height metadata. Production recursive SDK claims are separate from
Neptune transaction admission. Keep execution, full proof, GPU device and live
network evidence distinct. The standalone Honeycrisp proving Warrior remains a
stub; the implemented mining API is separate. No shader inventory or historical
throughput number establishes a complete GPU prover.

Full baseline coverage retains all43 independent manual programs. See
`audit/README.md`, `baselines/triton/README.md` and the coordinated ledger for
current receipts and open gates.

## Multi-State Architecture

Trisha follows trident's union/state vocabulary:
- **union** = OS/network (e.g. `neptune`)
- **state** = chain instance (e.g. `mainnet`, `testnet`)

Known states live in `networks/neptune/states/*.toml`; the CLI registry is generated at build time. All network-touching commands
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

Adding a new state: add a manifest in `networks/neptune/states/`, including its `[node]` RPC port and network flag. Rebuild to embed it.

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
trisha neuron import  # upstream interactive import; no seed words in argv
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

Three backend crates share the canonical input/claim/proof boundary and bundle validation. Execution acceleration remains backend-owned:

- **rs** (`rs/`) — pure Rust via triton-vm. `Warrior::new()` prints `Backend: cpu`. Complete.
- **wgpu** (`wgpu/`) — cross-platform GPU (Metal/Vulkan/DX12). `Warrior::new()` inits GPU,
  registers Tip5 accelerator with triton-vm's prover, falls back to CPU gracefully.
  Shaders and pipelines compile; full NTT/Merkle/FRI dispatch pending.
- **honeycrisp** (`honeycrisp/`) — portable CPU mining plus optional Apple
  acpu/aruminium acceleration. The separate proving Warrior remains a stub.
  Apple dependencies and GPU exports are guarded by macOS/aarch64.

The `cli/` crate uses `trisha-rs` for the CPU warrior. Changes to proving backend
selection require an explicit interface contract and complete proof verification
receipts, including malformed claims and CPU/GPU equivalence.

## Proof File Format (.proof.toml)

```toml
[proof]
format = "stark-triton-v7"
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
