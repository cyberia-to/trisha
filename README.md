# Trisha

Trisha is the Triton VM warrior for Trident. It lowers typed Trident IR to TASM, executes programs, generates STARK proofs, and verifies them. Neptune modules and Triton hand baselines live here.

```text
Trident source -> resolved typed IR -> Trisha lowering -> Triton VM -> STARK proof
```

Current CPU release: **Trisha 0.3.0**, with Trident 0.3.0 and Joy 0.5.0.
[Download native archives](https://github.com/cyberia-to/trisha/releases/tag/v0.3.0)
for macOS, Linux or Windows on ARM64/x64, or use the coordinated source archive.
See [release notes](audit/release-notes-v0.3.0.md) and [validation](audit/release-2026-09-16.md).

## Commands

```sh
trisha build program.tri -o program.tasm
trisha run program.tri --input-values 5
trisha prove program.tri --input-values 5 --output program.proof.toml
trisha verify program.proof.toml
trisha run --tasm program.tasm --input-values 5
trisha prove batch a.tri b.tri --output proofs/
trisha verify batch proofs/*.proof.toml
```

Source commands accept project directories and named compilation profiles. The default terrain is Triton; `--target neptune` selects the same VM. Unsupported targets fail. Library builds retain their function definitions; execution and proving require a program entry.

The CLI uses the CPU backend. The separate wgpu backend provides GPU acceleration hooks; enabling a mining GPU feature does not switch the proving backend. Program inspection verifies the native hash and any attached proof. Neptune's separate [transaction interface](docs/reference/neptune-submission.md) constructs outputs, validates complete caller-authorized transaction intent and submits through an authenticated gateway. A genuine SingleProof transaction passed [isolated node admission](audit/neptune-local-node-validation.md); funded wallet construction, public-network operation and block confirmation remain separate requirements. Release evidence is recorded in [audit](audit/README.md).

## Building

The development workspace uses sibling Trident and hardware-library checkouts. Bootstrap the pinned Triton vendor patches before building:

```sh
nu patches/apply.nu
cargo build --release -p trisha
cargo test -p trisha-rs
cargo test -p trisha --test source_pipeline
cargo install --path cli --locked
```

The compiled warrior embeds its Neptune modules; the compiler dependency embeds standard libraries. Programs can import those modules when invoked outside the source checkout.

## Verification and benchmarks

```sh
trisha bench baselines/triton/reference --full --skip-neural
trisha bench baselines/triton --full --skip-neural
```

Benchmark fixtures contain independent expected outputs. Both classic and hand programs must match independent expected outputs before a cycle ratio is printed. Self-identifying type scripts disclose the implementation-specific program hashes and derived authenticated inputs used for the same semantic transaction; `--full` also proves and verifies both. Uncovered baselines are reported as `UNVERIFIED`, and incomplete coverage returns a failing exit status. Every one of the43 hand baselines has explicit positive reference fixtures, with rejection vectors where applicable. Current execution and full-proof receipts are recorded separately in the [release ledger](../trident/audit/full-release-preparation.md).

Regression tests exercise source CLI run/prove/verify and tampered claims, wide stacks, imported structures, SHA-256 against the empty-message FIPS digest, malformed inputs, and colliding batch proof destinations.

## Workspace

- `cli/`: command-line interface and reference benchmark runner.
- `rs/`: CPU runtime, Triton lowering, AET cost model and neural target integration.
- `wgpu/`: GPU runtime backend and WGSL kernels.
- `honeycrisp/`: portable CPU mining and optional Apple acceleration.
- `neptune/`: pinned consensus/RPC transaction intent and submission adapter.
- `lib/os/neptune/`: Neptune source modules.
- `targets/triton/`: authoritative Triton machine manifest.
- `networks/neptune/`: Neptune network and state manifests.
- `baselines/triton/`: independent hand assembly and reference fixtures.
- `patches/`: reproducible overlay for pinned upstream Triton dependencies.

See [architecture](docs/explanation/architecture.md) and [roadmap](roadmap/README.md).

Cyber License: Don't trust. Don't fear. Don't beg.

Inspect the installed target package without compiling or running a program:

```sh
trisha describe --target triton
trisha describe --target neptune
```

The JSON includes compiler API compatibility, the machine ABI, content hashes for embedded SDK modules, network/state descriptors, and supported proof formats. Neptune state commands consume the same owned state manifests. Fixed ABI libraries use `vm.triton.hash`, `vm.triton.merkle`, `vm.triton.merkle_proof`, and `os.neptune.auth`; they are not portable compiler libraries.

The retired handwritten `os.neptune.proof` module remains excluded; its FRI/OOD/constraint checks were incomplete. Historical prototypes are preserved under `examples/experimental/neptune`. The production replacement is `vm.triton.proof.verify`, which invokes the official Triton7 verifier with a complete caller-authorized claim. Neptune exports fixed canonical0.15.1 policies through `os.neptune.transaction.verify` and `os.neptune.native_currency.verify`. See the [recursive proof contract](docs/reference/recursive-proof.md) for witness preparation and the distinction between consensus proof verification and network admission.
