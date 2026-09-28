# Native soft3 release coordination

Status: component checks passed; complete coordinated rehearsal pending.
These local feature-branch measurements establish neither a release candidate
from default branches, native platform acceptance nor SH6/SH7/SH8 closure.
The subsequent archive build and stale imported-field fixture repair are
retained in [the follow-up](import-visibility/README.md), including its original
failed smoke and independent checks.

Trisha `8f4a2d883a47df4bfeab0f880ee7f6adba55c7e1` makes candidate preparation
check Joy's own soft3 dependency boundary and installed proof smoke. Triton
dependency checks apply to Trisha. Private Joy proof assertions use `JOYZH001`.
The root lockfile adds the two missing Zheng dependency references while
preserving every existing package/version/source record.

## Component validation

The commands and logs are retained under `release-warrior-boundaries/` in
`raw-evidence.tar.gz`. `build-inputs-before.json` records the initial feature
worktree and clean sibling inputs; `precommit-final.json` binds the final eight
changed files to their exact committed bytes at `8f4a2d8`. The measurements
preceded that commit. Source packaging later checks the committed closure.

- `cargo check --release --locked --offline --all-targets` and `cargo test
  --release --locked --offline`, selecting `trisha`, `trisha-rs`,
  `trisha-neptune` and `trisha-honeycrisp`, passed. The test command additionally
  uses `-- --test-threads=4`: 429 passed, zero failed and six existing ignored
  across 64 result summaries. These totals were recounted from the raw log.
  `cargo build --release --locked --offline -p trisha` also passed.
- `python3 -B -W error scripts/test_{snapshot_source,archive_source,
  verify_source,package_binaries}.py`, each invoked separately, passed
  1 + 2 + 10 + 3 distinct packaging guards. The final ten source guards ran
  again after the final source-packaging edit; that rerun adds no unique tests.
- `nu --no-config-file -c 'nu-check PATH'` accepted `build-candidate.nu`,
  `package-source.nu` and `smoke-release.nu`. Python syntax and `git diff
  --check` also passed. Cargo checks, tests, build and isolated post-commit
  installation emitted zero warnings.

`cargo-gates.json`, `packaging-gates.json` and `precommit-final.json` contain
the actual expanded argument lists, working directories and log/source hashes.
The original root-lock `--locked` failure and original lockfile remain in the
archive alongside the corrected component checks.

## First complete archive attempt

The strict export at `8f4a2d8` used eleven committed, pushed, clean repositories.
`first-export/prepare.json` records every revision, actual tool paths, export
command and matching before/after source snapshots. The source archive was
113613446 bytes, SHA256
`e62c62421fe3ab93d69722891cf187c83568ef074cade921b8eda0f3de9af30f`.
Its inventory is retained as `first-export/sources.json`; the large source
archive itself remains at the original local path recorded in the receipt.

`rustup run 1.89.0 nu --no-config-file ARCHIVED/build-candidate.nu SOURCE
DESTINATION` stopped after building Trident, Trisha and Joy. The standalone
state-fixture helper's lockfile was stale, so its `cargo run --release --locked
--offline` correctly failed. The build published no candidate and its own
cleanup removed staging. The exact outer command, stdout, stderr, failure
receipt and successful source guards before/after execution are retained in
`first-export/`; removed intermediate build logs are not claimed as evidence.
Dependent installed smoke and corpus gates did not run in this attempt.

## Fixture lock repair

Commit `4f7074bbc61b86fd2355c542e0fffa2c823af755` changes only
`scripts/fixtures/Cargo.lock`. It adds seven absent package records, each
exactly matching the existing Joy lockfile, and the Zheng `getrandom`/`zeroize`
references. All other pre-existing records remain unchanged.

`release-fixture-lock/` retains the original lock, offline resolver output,
comparison, commands and generated files. The initial resolution selected a
newer `cfg-if`; `cargo update --offline -p cfg-if --precise 1.0.4` selected the
version already used by Joy. The original resolver output is preserved.

On actual Rust 1.89.0, `cargo check --manifest-path scripts/fixtures/Cargo.toml
--release --locked --offline --all-targets`, the corresponding `cargo test`,
and `cargo run --manifest-path scripts/fixtures/Cargo.toml --release --locked
--offline -- FRESH_OUTPUT` all passed without warnings. The helper contains
zero Rust tests; its real generation produced the three public state
certificates, whose bytes and hashes are retained. Isolated post-commit Trisha
installation also passed without warnings. A fresh complete export/build is
required to accept the repaired coordinated path.

## Retained bytes

`receipt.json` binds the two implementation commits, source identities,
original failed export and archive. `files.json` indexes all 86 raw files:
5729371 uncompressed bytes, retained in the 712999-byte archive with SHA256
`d64e466de8f3966c63dcf7e6f9af84c1c3e87ae5e65a969e9a7aa8f1e0479d02`.
Every archived member was compared byte for byte with its original.
`retain-local.py` records the exact local retention command and checks; its
absolute paths identify that measurement environment.
