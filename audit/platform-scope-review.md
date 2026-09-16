# Release platform review — 2026-09-16

Read-only source/dependency/tooling review accompanying the
[six-target proposal](../docs/reference/release-platforms.md).
No new platform was compiled, executed or certified in this review.

## Existing evidence

- Historical FINAL5 installed build/smoke receipts cover macOS ARM64 and Linux
  ARM64. The Linux guest was Ubuntu 26.04 ARM64; these receipts do not establish
  Linux x86_64 execution or an older glibc compatibility floor.
- [Earlier checks](platform-validation.md) include Linux x86_64 compilation
  checks. A check does not link or run a release executable.
- No Windows or macOS Intel native acceptance receipt was identified in the
  inspected release records. All final targets need fresh frozen-source gates
  after the RAM repairs, including previously tested ARM64 platforms.
- No coordinated release workflow was found under Trident/Trisha/Joy
  `.github/workflows`; Trident currently has a notification workflow.

## Concrete portability work

- `scripts/build-candidate.nu`, `smoke-release.nu` and `package-binaries.nu`
  assume extensionless binary filenames. Build/package staging invokes `mktemp`
  and `chmod`; the dependency containment check uses a literal slash prefix.
  Windows needs native executable names, path containment and staging/packaging.
- `scripts/check-baselines.py` uses POSIX process groups, `os.killpg`, signals
  and `/bin/ps`. Port process-tree termination and memory accounting before
  claiming a full native Windows baseline gate.
- `cli/neptune.rs::trisha_config_dir` uses HOME with a `/tmp` fallback and only
  distinguishes macOS from other systems. Define and test native Windows config
  paths. Explicit overrides must keep their existing semantics.
- Compiler/warrior process tests, node/wallet tests and artifact reader tests
  contain Unix-only suites and shell fixtures. Supply Windows equivalents for
  the shared contracts; retain honestly platform-specific file tests.
- `trident/src/config/target/discover.rs::warrior_path` already uses
  `std::env::split_paths` and `EXE_SUFFIX`. The core discovery algorithm is not
  missing `.exe` handling; installed Windows coverage remains necessary.
- Apple acpu/aruminium dependencies and exports are already guarded by
  macOS/aarch64. Other CPU targets have portable hashing paths; that source
  structure alone does not certify the Windows dependency/link closure.
- Source inventories include symlinks. Windows extraction must preserve the
  recorded source identity or use an explicitly inventoried source variant;
  silently materializing links would invalidate current verification.
- Current binary packaging carries exactly three executables and omits the
  existing `trident-lsp`. The proposal adds LSP plus an initialization test;
  candidate/smoke schemas and packaging inventories must change consistently.

Historical resource observations: [recursive/full baseline proving](recursive-release.md)
records about 19.2 GB process-tree RSS; [FINAL5](final5-release-candidate.md)
records about 9.9 GB for macOS installed smoke. These measurements inform worker
provisioning, not a universal end-user memory minimum.
