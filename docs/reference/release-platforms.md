# Coordinated release platforms

Status: release acceptance contract, 2026-09-16. Windows is an explicit owner
requirement alongside macOS and Linux. The six CPU/ABI targets below define the
release matrix; completion is recorded separately in the native release audit.

These gates cover the implemented, documented Trident/Trisha/Joy CPU surface.
Trident 0.4 additionally requires SH6 reproducible native self-hosting under its
[delivery policy](../../../trident/reference/self-hosting.md#release-04-delivery-policy).
SH7/SH8 compilation proofs have separate acceptance criteria. Tagged-protocol
integration, live state databases, further language expansion and secure FHE
remain separate roadmap work. Defects in supported behavior and missing
validation for a promised release platform block release acceptance.

Source inventories encode relative paths and symbolic link targets with POSIX
separators. Native Windows link spellings are normalized to that same relative
target before hashing; target resolution must still remain inside the archive.
File contents and link-vs-file identity remain exact on every platform.

## Native artifacts

| Host platform | Rust target | Binary archive |
|---|---|---|
| macOS Apple Silicon | `aarch64-apple-darwin` | `.tar.gz` |
| macOS Intel | `x86_64-apple-darwin` | `.tar.gz` |
| Linux ARM64, glibc | `aarch64-unknown-linux-gnu` | `.tar.gz` |
| Linux x86_64, glibc | `x86_64-unknown-linux-gnu` | `.tar.gz` |
| Windows ARM64, MSVC | `aarch64-pc-windows-msvc` | `.zip` |
| Windows x86_64, MSVC | `x86_64-pc-windows-msvc` | `.zip` |

Each coordinated archive must carry `trident`, `trident-lsp`, `trisha` and
`joy`, with `.exe` on Windows, embedded target/SDK data, licenses, version and
source identities, checksums and the exact validation receipts. LSP is an
existing compiler binary and requires its own installed protocol smoke.
Standalone nox/Zheng developer CLIs are separate artifacts if
requested; their libraries remain in the coordinated source closure.

### Portable self-hosted compiler kit

The coordinated 0.4 binary archive additionally carries
`share/trident-selfhost/`: the accepted portable C2 `compiler.dag`, its original
`inventory.json`, and `sample.tri`, `package.json`, `zero.dag` guide inputs.
`kit.json` hashes every payload file and binds the original producer C2 role,
fixed-point source map, native phase acceptance and compiler particle. This is
data alongside the same four binaries; the existing proof corpus is unchanged.

Assemble this kit once with `scripts/selfhost-kit.py assemble`. Acceptance is
delegated to the exact Trident final 36-phase validator from commit
`8576570d745139b733bb7dec090035dca938abe1`, SHA256
`72cd11ec62e410e908590a785c79011989ea2c6c32872c5db31d72a62947c0ec`.
The explicit configuration supplies its original ZIP/API downloads, three
stores, restored trees, pinned indices, frozen runner/expected contract, final
run and aggregate job. The assembler runs it into fresh retained evidence;
an earlier local result or producer-only receipt cannot replace that check.
The kit retains the raw selected producer, manifest, fixed-point and aggregate
receipts plus the validator's full provenance report. Original archive/store
identities remain references to the durable Trident audit; the compact kit does
not duplicate every native corpus. `rehearse` creates an explicitly unaccepted
kit from historical actual C2 evidence. Production packaging rejects it.

The candidate selector pins a separately downloaded kit archive SHA256. Before
packaging, compare all 94 compiler source bytes in the verified Trident source
archive against the accepted fixed-point map. Validate the complete kit file
set, lengths and hashes. Inputs are ordinary files, bounded to 32 files and
128 MiB total; archives have a single fixed prefix, no links, aliases or special
entries. Staging/output directories must be fresh and separate from inputs.
Archives use deterministic metadata and exclusive creation.

Both installed and unpacked native Joy binaries run the supplied kit through
`pack-job`, `run-artifact --emit program`, and `run-artifact`, obtaining the
canonical atom 13. A rejected source must leave an existing output unchanged.
The smoke binds actual Joy/compiler bytes, kit manifest and the unchanged guide
options/limits. It never builds Joy, invokes a host compiler, or substitutes a
seed. The smoke establishes distribution compatibility with the shipped Joy;
original native bootstrap pins and current package pins remain distinct.
These checks do not establish SH7/SH8 compilation proofs or a new SH6 run.

Use default CPU features, portable target CPU settings and pinned toolchain,
lockfiles and vendor inputs. Do not build public binaries with
`target-cpu=native`. Neural training and GPU acceleration need separate feature
and device evidence; they do not multiply the default release matrix.
Trisha owns the pinned Triton/tasm-lib dependency family. Joy owns the native
soft3 proof path and passes its archived `scripts/check-soft3-boundary.py`
before any candidate binary is built. That check rejects foreign VM packages
and external compiler resources in Joy's resolved feature graph. Current Joy
private execution and private state proofs use `JOYZH001`; public execution and
authenticated public state retain `JOYEXEC2` and `JOYST001` respectively.
Each root workspace and the fixture helper require separate Cargo output
directories. Their independent lockfiles can select distinct dependencies;
upstream cdylib/rlib outputs must not overwrite another workspace's artifacts.

Formal audit integration tests require an actual Z3 executable. The native CI
bootstrap pins Z3 4.15.3 assets by SHA-256 and records its version before tests.
Z3 is an optional runtime dependency for `trident audit --z3`, not part of the
four-binary archive or the proving engine.

Initial OS-floor candidates are macOS 14, Windows 11 and Linux glibc 2.35
(Ubuntu 22.04 baseline). These are proposed compatibility policies, not observed
minimum requirements. Finalize them through dependency/link inspection and
execution on the oldest claimed OS, including ARM64. A build on a newer Linux
distribution alone cannot establish the older glibc floor. Record the MSVC
runtime linkage: release Windows binaries statically link the CRT so users do
not need a separate Visual C++ redistributable. Verify the actual PE imports.

## Acceptance on each supported target

1. Build from one verified source closure, without sibling checkout leakage.
   Record target triple, actual OS/architecture, Rust/linker versions, features,
   deployment/runtime floor, and binary/source hashes.
2. Run applicable workspace tests and the installed compiler/warrior suite on
   the actual OS and architecture. Cross-compilation, Wine, Rosetta and WSL
   cannot substitute for validation of a claimed native target. Native-ISA VMs
   are suitable. Report platform-specific exclusions and cover equivalent
   contracts on Windows rather than silently dropping Unix-only suites.
3. Generate and verify fresh Triton, recursive and Joy public/private/state
   proofs, including malformed artifacts, changed claims and the RAM repairs.
   Execute all133 baseline fixtures (99 positive,34 rejection vectors covering
   all43 hand programs) on every native target. Separately, the same committed
   source must pass the full198-proof baseline gate on the dedicated proof
   worker. Record that worker's platform and exact binary identity; this does
   not claim198 generated proofs on every desktop. Timeouts or memory
   exhaustion are incomplete gates, never passes.
4. Collect a compact proof corpus from every target. Every target verifies the
   corpus from every other target, with expected program/input/output/state
   pinned, and rejects corresponding tampering. Proof bytes need not match.
5. Unpack the final archive into a clean directory, test the actual shipped
   binaries, and bind receipts to their hashes. Include spaces/non-ASCII paths,
   executable discovery, LSP initialization, config/temp paths and overwrite
   behavior. Package with deterministic archive metadata.

Neptune adapter validation must cover each shipped client platform. A pinned
node may run on a validated server platform for RPC integration. Bundling or
promising a native Neptune node/wallet helper on every desktop target requires
separate upstream compatibility and process tests; a warrior archive alone
does not establish that claim. No live-public-network action is implied.

## Build infrastructure

Use native macOS hosts, Linux hosts/VMs and Windows MSVC hosts/VMs. Pin runner
labels/toolchain versions instead of relying on moving `latest` labels.
GitHub currently lists native hosted runners for all six combinations;
availability does not establish sufficient memory/disk for these workloads.
See [GitHub runner resources](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
and [Rust Windows targets](https://doc.rust-lang.org/stable/rustc/platform-support/windows-msvc.html).
The latter describes current Rust, not a compatibility receipt for our pinned
toolchain or dependencies.

Budget dedicated proof workers initially at 32 GiB RAM or more, then enforce
limits based on measurements for the final candidate. Historical full baseline
proving reached about 19.2 GB process-tree RSS; installed smoke reached about
9.9 GB. Serialize large proofs and reserve OS headroom. Standard macOS ARM
hosted runners currently have 7 GB, so they cannot cover that observed smoke
workload without changing resources. Provision disk for source, vendor, Cargo
outputs and proof artifacts as well. Purchasing or launching paid runners is
not part of this proposal.

## Additional distribution options

- Linux OCI images for `linux/amd64` and `linux/arm64` can package already tested
  binaries for servers. Validate image startup and runtime dependencies. They
  add a distribution format rather than a new language or execution backend.
- Linux musl/static archives are a follow-up portability option, subject to
  native dependency, TLS and proof-performance checks; GNU receipts do not
  establish musl support.
- Homebrew, winget/Scoop and native installers can consume the same release
  archives after the core matrix passes. They are distribution work.
- Web/WASM, Android/iOS, FreeBSD, RISC-V and 32-bit hosts remain separate ports.
  Browser/mobile constraints and prover memory require their own product scope;
they are not implied by producing the six desktop/server artifacts.

Observed gaps and historical evidence are in
[the platform review](../../audit/platform-scope-review.md).
