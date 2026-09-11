# Trisha

Trisha is the Triton VM warrior for Trident. It lowers typed Trident IR to TASM, executes programs, generates STARK proofs, and verifies them. Neptune modules and Triton hand baselines live here.

```text
Trident source -> resolved typed IR -> Trisha lowering -> Triton VM -> STARK proof
```

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

The CLI uses the CPU backend. The separate wgpu backend provides GPU acceleration hooks; enabling a mining GPU feature does not switch the proving backend. Neptune on-chain deployment is not implemented: `deploy` fails explicitly, while `deploy --dry-run` describes an artifact.

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

Benchmark fixtures contain independent expected outputs. Both classic and hand programs must match the same vector before a cycle ratio is printed; `--full` also proves and verifies both. Uncovered baselines are reported as `UNVERIFIED`, and incomplete coverage returns a failing exit status. Existing hand baselines still require reference fixtures before the whole collection can pass this gate.

Regression tests exercise source CLI run/prove/verify and tampered claims, wide stacks, imported structures, SHA-256 against the empty-message FIPS digest, malformed inputs, and colliding batch proof destinations.

## Workspace

- `cli/`: command-line interface and reference benchmark runner.
- `rs/`: CPU runtime, Triton lowering, AET cost model and neural target integration.
- `wgpu/`: GPU runtime backend and WGSL kernels.
- `honeycrisp/`: Apple Silicon mining integration.
- `os/neptune/`: Neptune source modules and network configurations.
- `baselines/triton/`: independent hand assembly and reference fixtures.
- `patches/`: reproducible overlay for pinned upstream Triton dependencies.

See [architecture](docs/explanation/architecture.md) and [roadmap](roadmap/README.md).

Cyber License: Don't trust. Don't fear. Don't beg.
