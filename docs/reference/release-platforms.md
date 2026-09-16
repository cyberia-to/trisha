# Coordinated release platforms

Status: release acceptance contract, 2026-09-16. Windows is an explicit owner
requirement alongside macOS and Linux. The six CPU/ABI targets below define the
release matrix; completion is recorded separately in the native release audit.

The release covers the implemented, documented Trident/Trisha/Joy CPU surface.
Dynamic nox continuations, tagged-protocol integration, live state databases,
language expansion, full compiler self-hosting and secure FHE remain roadmap
work. They do not block this release. Defects in supported behavior and missing
validation for a promised release platform do block it.

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

Use default CPU features, portable target CPU settings and pinned toolchain,
lockfiles and vendor inputs. Do not build public binaries with
`target-cpu=native`. Neural training and GPU acceleration need separate feature
and device evidence; they do not multiply the default release matrix.

Formal audit integration tests require an actual Z3 executable. The native CI
bootstrap pins Z3 4.15.3 assets by SHA-256 and records its version before tests.
Z3 is an optional runtime dependency for `trident audit --z3`, not part of the
four-binary archive or the proving engine.

Initial OS-floor candidates are macOS 14, Windows 11 and Linux glibc 2.35
(Ubuntu 22.04 baseline). These are proposed compatibility policies, not observed
minimum requirements. Finalize them through dependency/link inspection and
execution on the oldest claimed OS, including ARM64. A build on a newer Linux
distribution alone cannot establish the older glibc floor. Record the MSVC
runtime linkage and any required redistributable; test on a clean Windows host.

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
   Retain the full baseline proof gate, with platform and fixture accounting.
   Timeouts or memory exhaustion are incomplete gates, never passes.
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
