# Native Linux release validation

Status (2026-09-12): **native build, full installed proof smoke and reproducible
Linux ARM64 binary packaging passed** for the identified rehearsal archive.
Final post-commit source validation remains separate; nothing was published.

## Isolation and resources

Local Lima instance `cyber-release-check`, Ubuntu 26.04 LTS ARM64, Linux
`7.0.0-28-generic`; native target `aarch64-unknown-linux-gnu`. Configuration:
`/tmp/cyber-release-linux.yaml` on the host. VZ virtualization, 4 CPUs, 8 GiB RAM,
30 GiB guest disk. `mounts: []`; inspection found no virtiofs/9p/NFS host mounts.
Application port forwarding is disabled by the Lima configuration; Lima retains
its loopback-only management SSH endpoint. No host home or
checkout is mounted; source must be copied as an explicit archive.

The pinned Ubuntu cloud image is dated 2026-07-17, SHA-256
`a8ef92cccd88427e74655cef83ac4ab72f64e961788fef4eae6a365975fe03ad`.
Preparation initially used 8 GiB and performed only tool installation. The
subsequent isolated node admission belongs to its separate owner and receipt;
after confirmed cleanup, this task resized the guest to 16 GiB and performed
the full proof smoke described below. No public network service was exposed.

## Installed tools and provenance

- Rust **1.89.0**, commit `29483883eed69d5fb4db01964cdf2af4d86e9cb2`, native
  `aarch64-unknown-linux-gnu`; Cargo **1.89.0** (`c24e10642`). Minimal toolchain
  installed through the [official rustup installer](https://rust-lang.org/tools/install/)
  with `--profile minimal --default-toolchain 1.89.0 --no-modify-path`.
- Nushell **0.112.2**, matching the host. Official
  [Nushell 0.112.2 release](https://github.com/nushell/nushell/releases/tag/0.112.2),
  asset `nu-0.112.2-aarch64-unknown-linux-gnu.tar.gz`; SHA-256 verified against
  the release asset metadata:
  `c25a713f4c10bd886162c62c278db6cf8a657754be53d33379af70fbadab07b8`.
- Ubuntu package prerequisites: build-essential, pkg-config, libssl-dev, clang,
  cmake, git, curl, ca-certificates, Python 3, xz-utils, zstd and unzip.
- Observed versions: GCC **15.2.0**, Clang **21.1.8**, CMake **4.2.3**,
  OpenSSL **3.5.5**, Python **3.14.4**. At preparation completion the guest had
  approximately 26 GiB free disk, no swap, and 7.1 GiB available memory.

Receipts on the host: `/tmp/cyber-linux-environment.log`,
`/tmp/cyber-linux-prerequisites.log`, `/tmp/cyber-linux-rust-install.log`,
`/tmp/cyber-linux-nushell-install.log`. Guest environment receipt:
`/home/master.guest/release-validation/environment.txt`. Downloaded installer,
release metadata and verified Nushell archive are retained under guest
`/tmp/release-tools/`.

## Acceptance sequence (completed for this rehearsal)

1. Receive the fresh deterministic archive with `cyber-source/` prefix; record
   its SHA-256 and `sources.json` identity. Copy via Lima transport, not a mount.
2. Extract in a new guest directory and run the archived
   `trisha/scripts/build-candidate.nu`, using explicit guest Cargo/Nushell PATH,
   `CARGO_BUILD_JOBS=2` and the script's shared isolated target directory.
   No production source edits or host binaries may substitute for that build.
3. Inspect native ELF identities and execute the three installed version/help
   commands plus bounded compile/run checks from an empty guest directory.
4. Coordinate proof-memory availability before the full archived
   `smoke-release.nu` execution. It performs real recursive/private proofs and
   must not be launched casually under the current 8 GiB/host-heavy-proof limit.
5. Record actual completed gates and remaining failures. No publication follows
   automatically from a successful local build or smoke run.

The toolchain was additionally checked with a temporary Rust program compiled
inside the guest: `file` identified an ARM aarch64 GNU/Linux ELF, direct execution
returned `linux aarch64`, and Nushell's `complete`/JSON path successfully checked
its result. Receipt: `/tmp/cyber-linux-native-probe.log`. This verifies the
prerequisite compiler/linker/shell path only, not any release binary. The Ubuntu
`file` package was added for subsequent installed ELF inspection.

## Fresh rehearsal archive received

Copied using `limactl copy` and extracted at guest
`/home/master.guest/release-validation/rehearsal-20260912/cyber-source`.
Archive: `/tmp/cyber-release-source-v7-20260912.tar.gz` on the host, SHA-256
`9bce1a685bc5568277f01865c505008c43e733e1d242611ca047a228f0ae1961`.
All **2336** manifest entries independently verified after transfer: 2328 regular
files and 8 symlinks; every symlink resolves within the extracted source tree.
`sources.json` SHA-256:
`6837745f8669d541a559f3d502d5cac978afbd8832dda4548892aa4b0d2190fd`.

Guest Rust1.89 `cargo metadata --all-features --locked` succeeded for all three
roots. Local package counts: Trident9, Trisha36, Joy32, union40. The packager's
Trisha+Joy-only union39 excludes the additional `trident-silicon0.1.0` workspace
member reached from the Trident root; its complete sources are already archived.
The host and guest all-three-root union lists match exactly (name/version/path).
This is a difference in counted roots, not a missing dependency or resolve drift.
All local paths canonicalize inside the archive and all seven Triton/tasm owner
packages resolve to exactly7.0.0.

Receipts: `/tmp/cyber-linux-source-provenance.log`,
`/tmp/cyber-linux-metadata-closure.log`, `/tmp/cyber-linux-package-union.json`.
The native candidate build is serialized after the independent pinned-node
build in the same 8 GiB guest. This is a working-tree rehearsal snapshot; final
post-commit archive validation remains a separate release gate.


## Native candidate and bounded installed smoke passed

The **archived** `trisha/scripts/build-candidate.nu` completed with exit0 using
Rust1.89.0, native GCC, jobs2, and a shared target directory inside the candidate
prefix. It built Trident, Trisha, Joy and the archived locked state-fixture
helper. All four build logs have zero compiler warnings/errors. Elapsed time:
**7m26.49s**; GNU time reports maximum process RSS **4,910,168 KiB**, zero swaps.
This is not a measurement of aggregate VM peak RSS.

Guest candidate prefix:
`/home/master.guest/release-validation/rehearsal-20260912/candidate`.
Host review copy (independently checked against candidate.json hashes):
`/tmp/cyber-native-linux-rehearsal-20260912/bin`.

| Native binary | Version | SHA-256 |
|---|---|---|
| trident | 0.4.0 | 2903760f6c8bdcf6bcd5158f7727907d289cdc70a82a63d15ba8600fa99dd660 |
| trisha | 0.3.0 | 83e31b2ed475fa00bc681dd76e1f5bf8cee6eb5798b1fe0bc47868cb46bc220b |
| joy | 0.5.0 | f6326f1d0a2f0b7fb0e56e3b20756697737899ac4d7ffa8e174c807c181cf5b8 |

All three are native ARM aarch64 ELF PIE executables using
`/lib/ld-linux-aarch64.so.1`, with libgcc_s/libm/libc resolved in the guest.
Observed imported glibc symbol versions reach **GLIBC_2.39** for Trident/Trisha
and **GLIBC_2.34** for Joy. This Ubuntu26.04 run does not establish compatibility
with every Linux distribution, older glibc, or x86_64.

A separate **no-proof** installed smoke ran from a fresh guest directory with
PATH restricted to the three candidate binaries and target-library overrides
removed. It passed:

- installed versions/help and compiler API2/target schema1 provider contracts;
- nox source checking/building/execution and Joy bundle execution (result38);
- real Triton VM execution via both Trident delegation and Trisha (result38);
- imported helper execution through the actual `#[test]` runner, with
  1passed/0failed/1skipped, plus release-profile failure and unknown-target refusal.

Installed `trisha state show neptune local-testnet1` reports chainID4,
network flag`testnet-1`, RPC29799, defaultfalse. The node integration owner was
given this exact candidate path; no public testnet was relabeled.

Receipts: `/tmp/cyber-linux-native-candidate-build.log`,
`/tmp/cyber-linux-native-{trident,trisha,joy,fixture}-build.log`,
`/tmp/cyber-linux-native-candidate.json`, `/tmp/cyber-linux-native-artifacts.log`,
`/tmp/cyber-linux-installed-small.log`, `/tmp/cyber-linux-installed-state.log`.
The bounded smoke source is retained at
`/tmp/cyber-linux-installed-small.nu` on the host and
`/home/master.guest/release-validation/installed-small.nu` in the guest.

Guest compile resources were released to the node owner after the candidate
build. Full proof smoke and the separately owned loopback-node admission later
passed. Native x86_64 execution and the final post-commit source archive/candidate
rerun remain outside this receipt; no binaries were published.

## Full smoke resource preparation

After the node integration owner explicitly confirmed successful admission and
cleanup (no node or harness process remained), the VM was gracefully stopped,
resized to **16 GiB** with `--mount-none`, and restarted. Candidate/source hashes
were unchanged; no host filesystem mounts were introduced. Guest memory was
approximately15GiB available after reboot, with no swap. The separate node
receipt is `/tmp/neptune-node-admission-receipt.json` and remains the node owner's
validation scope.

A current smoke harness is staged separately under guest
`release-validation/smoke-tools-20260912/`, preserving the archived source tree.
The execution wrapper records the exact script hash and limits summed process-
group RSS to14GiB while requiring at least1GiB `MemAvailable`; it runs four Rayon
threads with `TVM_LDE_TRACE=no_cache`. A guard stop is failure, never a reduced
PASS. The full suite's own `smoke.json` is required for success.

The root handed off the exclusive heavy slot after the corrected Mac smoke
passed. The harness explicitly selects nox for Joy source calls under the
deliberately present Neptune project manifest; no production binary rebuild was
needed.


## Full installed proof smoke passed

The current harness was copied separately without modifying the archived source:
`smoke-release.nu` SHA-256
`c2b3627e97c8ef99561c78fbfd2e71930dacf5f468ee8af7ba2d380e1086504b`.
The real suite exited **0** and wrote `all_checks_passed: true` to `smoke.json`.
Elapsed **142.342 seconds**, peak summed process-group RSS **7,818,088,448 bytes**,
minimum guest `MemAvailable` **8,459,444,224 bytes**, 704 samples; no guard stop.

The installed binaries completed real recursive Triton outer proving and
verification, expected inner-claim binding and tamper rejection; Joy source and
bundle execution; public `JOYEXEC2`, private `JOYZK003`, and authenticated public
state `JOYST001` workflows, including hidden queries over authenticated public
tables. Wrong claims, inputs, state and missing secrets were rejected. Delegated
tests, target/artifact contracts and offline program inspection also passed.
This smoke makes no private-database claim and does not substitute for node
admission.

The harness checks binary and fixture hashes before and after execution. Fixture
SHA-256 identities in the genuine receipt:

| Fixture | SHA-256 |
|---|---|
| state.json | 8953a46858800afc0b9e9cd3a2a9869efec0f3fea1177c2b63c4180458b3b2e8 |
| other-state.json | 16b1bab42e8f64781c9723cc1b5122ea43690b98eda5673e2dfddd97eb72ab5f |
| state-all.json | 2a0e6d0d29ab36f8259dc3512e9db0b05fb1ea7f62a780a274c36df9d864b02c |

Durable host receipts under `/tmp/cyber-native-linux-rehearsal-20260912/`:
`full-smoke.log`, `full-smoke-memory.json`, and `smoke.json`. The guest work is
`release-validation/rehearsal-20260912/installed-full`. The heavy slot was released
after completion.

## Native binary archive passed

The current `package-binaries.nu` (SHA-256
`34ca5ea88a0659474ffd711c3c895324aede34e07a554705175bb919fe2e13ac`)
packaged the unchanged candidate using its actual `candidate.source`, the genuine
full smoke receipt and checked fixture hashes. Licenses came from that source;
the shipped candidate metadata omits its machine-specific absolute source path.
No production Rust rebuild occurred.

Host archive:
`/tmp/cyber-native-linux-rehearsal-20260912/cyber-tools-linux-aarch64-rehearsal.tar.gz`.
Size **10,747,124 bytes**, SHA-256
**`bc0178a663d372420a2713b4aa7f8a9355d1c60e80c206b9ab88a1618234bd1d`**.
The 18 tar entries use the fixed `cyber-tools/` prefix. Independent host archive
inspection verified all three binary hashes, ARM64 ELF identities and executable
modes, all fixture hashes, the exact smoke receipt and harness hash, source
provenance identity, and all three licenses. Repackaging identical inputs produced
a byte-for-byte identical archive (`cmp` exit0).

Receipts: `/tmp/cyber-linux-package.log` and
`/tmp/cyber-native-linux-rehearsal-20260912/archive-reproducibility.log`.
This is explicitly a working-tree rehearsal derived from source archive
`9bce1a685bc5568277f01865c505008c43e733e1d242611ca047a228f0ae1961`,
not a published or post-commit release. Ubuntu 26.04 ARM64 was executed natively;
older glibc distributions and native x86_64 are not covered by this receipt.
