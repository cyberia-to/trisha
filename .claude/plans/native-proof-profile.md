# Native public-proof profile gate

Status: implemented and independently reviewed; clean-origin local macOS ARM64
gates passed. Six hosted native receipts remain pending. Scope is the newly
integrated Joy/Zheng/Nox public structured certificate profile on release/0.4.

1. Add a dedicated six-platform hosted workflow and a small Python driver.
   Select ordinary public runners for macOS/Linux/Windows, each ARM64 and x64.
   Pin checkout/setup-python/upload-artifact actions and Rust 1.89.0.
2. Fetch twelve exact public origin commits into fresh sibling repositories;
   never use a working tree or the older frozen distribution archive as input.
   Joy's pushed production commit is pinned; its exact tree is merged into 0.4.
   Zheng's workspace also resolves its CLI's tade manifest, so tade is included
   beyond the eleven repositories in the distribution/Joy-only closure.
3. Record complete file SHA-256 inventories, clean Git state, source commits,
   bootstrap identity, native host/toolchain output and resolved path closure.
   No GitHub/auth token is passed to source builds or tests.
4. Fetch locked Cargo dependencies, then run locked/offline gates: Joy full
   workspace release tests (including fresh-process structured CLI tests),
   Zheng disclosed tests/default+serde and all three real-allocation tests,
   Nox observer v1/v2 tests, Joy foreign-backend boundary, zero-warning checks.
   Do not run Trident's full suite, Trisha CPU proofs or distribution packaging.
5. Retain commands, UTC times, outputs, hashes, native Joy executable identity,
   source before/after checks and a receipt, including partial failure evidence.
   Upload normal Actions artifacts only; no release assets, tags or publication.
6. Test selector/closure/host/log validation locally, review with root, then
   commit and push a ready PR. Actual native dispatch follows only pushed pins.
   Seven guard tests and actionlint 1.7.12 pass. The initial bootstrap failure
   and corrected complete local run are retained in audit/native-proof-profile/.

Acceptance is six independently passing native receipts. It supplements the
older distribution rehearsal and establishes neither a distribution replacement
nor whole-compiler SH7/SH8 capacity. Runner choices follow the current official
GitHub hosted-runner reference; real host/toolchain checks reject emulation or
an accidentally selected architecture.
