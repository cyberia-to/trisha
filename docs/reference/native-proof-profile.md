# Native public-proof profile validation

Status: implemented. Per-selector native results belong in
`audit/native-proof-profile/` and the workflow's retained artifacts.

This gate checks the changed public structured proof profile through native
Joy, Zheng and Nox builds. Each source repository is an exact committed origin
revision selected before execution. The gate is a branch validation receipt;
release packaging and promotion retain their separate contracts.

## Inputs and isolation

The selector pins Rust 1.89.0 and twelve public repositories: bbg, hemera,
honeycrisp, joy, lens, neuron, nox, strata, tade, trident, trisha and zheng. Zheng's
workspace resolves the tade CLI dependency even for package-filtered tests. The driver
fetches each commit by its complete hash from its fixed cyberia-to origin into
an empty sibling directory, checks HEAD and clean state, and records a complete
tracked-file SHA-256 inventory. Git line-ending conversion is disabled. Symbolic
links retain their actual link semantics. No working-tree snapshot is accepted.

Cargo metadata must resolve every local package beneath these pinned siblings.
Registry/git dependency identities come from the committed Cargo locks and
resolved metadata. Locked dependency fetching precedes offline build/test gates.
The toolchain version and native host triple must match the selected target.
The driver resolves rustc, cargo and rustdoc with `rustup which --toolchain`,
records their absolute paths and executable hashes, and invokes those tools.
Their directory leads PATH, RUSTC/RUSTDOC are explicit, and inherited compiler
wrappers/overrides are removed. Rustup uses its original manager storage only
for installation and path resolution; source gates use an isolated Cargo home.

The workflow has read-only repository permission, no supplied secret inputs,
and no persisted checkout credentials. The driver strips authentication and
Git configuration overrides from the environment passed to fetched code.
Actions are pinned by full commit. Ordinary public hosted runners are used:

| Target | Hosted label |
| --- | --- |
| `aarch64-apple-darwin` | `macos-15` |
| `x86_64-apple-darwin` | `macos-15-intel` |
| `aarch64-unknown-linux-gnu` | `ubuntu-24.04-arm` |
| `x86_64-unknown-linux-gnu` | `ubuntu-24.04` |
| `aarch64-pc-windows-msvc` | `windows-11-arm` |
| `x86_64-pc-windows-msvc` | `windows-2022` |

These are standard runner labels in the
[GitHub hosted-runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
The runner image itself may evolve; receipts identify the observed OS, machine,
image metadata, rustc/cargo versions and actual compiler host.

## Required checks

Joy runs its full workspace release tests, including the compiled
`prove-artifact` / `verify-artifact` integration tests that spawn fresh command
processes, compiler JOB1/RES1 admission and failure/publication checks. Three
portable test names are mandatory everywhere; the Unix-only links/pipes test is
also mandatory on Linux and macOS. Receipts list the required names. An empty
filter cannot satisfy this gate.

Zheng runs disclosed noun-memory, finite-DAG and bounded semantic-stream tests
with default and all features, plus the three isolated real-allocation test
binaries in both configurations. Nox runs observer v1/v2 tests with the native
sequential implementation. All affected packages run all-target checks with
compiler warnings denied, and captured compiler/Cargo warning lines also fail
the gate. Joy's resolved dependency/feature boundary must pass.

After the gates, source Git state and complete inventories must remain equal to
the pre-build snapshots. Target/build outputs live outside source repositories.
Every command retains exact arguments, selected environment, UTC start, duration,
exit status and output hash. Receipts also retain the built Joy binary hash.
Failures preserve available evidence and remain failures; no manually repaired
artifact is accepted. Actions artifact upload runs after either outcome.

## Acceptance boundary

All six native jobs must pass for one exact selector before claiming native
coverage of this profile. Cross-compilation does not satisfy a native result.
The older frozen distribution rehearsal keeps its own source pins and scope.
This gate supplies no new Trisha/Triton full-proof, distribution, physical
LIM1/GC, privacy, succinctness or whole-compiler SH7/SH8 acceptance claim.
