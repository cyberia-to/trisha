# Native public-proof profile preparation — 2026-10-02

The clean-origin local macOS ARM64 gate passes. The six hosted native jobs are
pending at this commit. This validates the changed Joy/Zheng/Nox public proof
profile; it is not a distribution candidate or whole-compiler SH7/SH8 receipt.

Source revisions are the twelve complete origin hashes in
`../../.github/native-proof-profile.json`, including Joy
`6e0ec4d8440e2521df08f442d64f54e667044716`, Zheng
`0d7ba6d422d9b825f9685e903e55252f88ebecd9` and Nox
`2f09ca3c3f18ae470365310cca8db5208eda75c6`. Trisha's base is
`d59738198aff278e7166e5958fbbc5f9777986b7`. The new gate source is identified by
SHA-256 in `source.json`; the complete run also records its bootstrap hashes.
Tade is the twelfth origin input because Cargo resolves Zheng's workspace CLI
manifest even during package-filtered library checks.

## Exact local invocation and results

From the isolated Trisha worktree:

```sh
python3 -B scripts/native-proof-profile.py --target aarch64-apple-darwin --work /Users/master/cyber/.worktrees/selfhost-0.4-finalization-20261002/native-proof-ci/local-native-gate-v3 --results audit/native-proof-profile/local-native-gate-v3
python3 -B scripts/test_native_proof_profile.py
/Users/master/cyber/.worktrees/selfhost-0.4-finalization-20261002/native-proof-ci/actionlint-1.7.12/actionlint .github/workflows/native-proof-profile.yml
```

The native driver receipt records each exact Cargo command, working directory,
selected environment, UTC start, duration, exit status and output SHA-256.
Observed toolchain: Rust/Cargo 1.89.0, compiler host `aarch64-apple-darwin`;
actual executable paths and SHA-256 values are retained. Python was 3.14.5 on
local macOS 26.4.1/ARM64; hosted jobs select Python 3.13.15 natively.

| Gate at the selector revisions | Result |
| --- | --- |
| Joy complete release workspace tests | 215 passed, 1 existing ignored |
| Joy all-target/all-feature check and foreign-backend boundary | pass |
| Zheng disclosed default / all features | 40 passed in each |
| Zheng real allocation tests default / all features | 4 passed in each across 3 binaries |
| Zheng all-target/all-feature check | pass |
| Nox observer v1/v2 tests | 21 passed |
| Nox all-target native check | pass |
| Complete source inventories before / after | equal, all 12 trees clean |
| Captured compiler/Cargo warnings | none |
| Driver adversarial guard tests | 7 passed |
| actionlint 1.7.12 | pass |

All four required POSIX CLI test names ran, including actual compiled
`prove-artifact` / `verify-artifact` subprocesses. Windows requires the three
portable names; the links/pipes test is compiled only on Unix. The exact lists
of passing names are in the native receipt. The produced local Joy binary is
5,651,872 bytes, SHA-256
`2eeacfd40f71f0be0d0325115c029c9ae3a73c5df7eec9a22b64080eaf7a777c`.
This is this driver's release-test executable, not an installed release asset.

## Preserved failures and independent review

`local-native-gate.tar.gz` retains the original failed invocation. It used the
same invocation above with `-v3` removed from both directory names. All origin
fetches and initial inventories passed, then rustup failed before compilation:
`rustup is not installed at '.../local-native-gate/cargo-home'`. The driver had
set the isolated Cargo home before resolving rustup's existing installation.
The correction preserves manager storage only for toolchain installation/path
resolution, then isolates Cargo home for source gates. The failed receipt keeps
the exact original error, command and bootstrap source hashes.

`local-native-gate-v2.tar.gz` retains the second invocation, using `-v2`
directory names. All native gates passed, but a separate final evidence audit
found that Cargo fetches reused the Git fetch command names: three earlier
stderr files were overwritten. Its receipt says passed, but this attempt is
invalid evidence and is not accepted. The final driver uses distinct Cargo
fetch names, rejects duplicate command names, creates log files exclusively,
and checks every command log hash again before declaring success. The complete
gate was repeated from fresh origin inputs as `local-native-gate-v3`.

Independent root review first found the Unix-only required test and the risk
of selecting Homebrew tools or inherited compiler wrappers. The final driver
selects absolute rustup-resolved native executables, strips overrides, records
executable hashes, scans warning output and runs Cargo from each project root.
Root's final review reported no remaining finding in the driver, input guards
and adversarial tests, and authorized pushing after the complete local gate
and actionlint. Root also reviewed the later duplicate-log correction and
final hash replay, with no remaining finding. This review covers CI/input
closure, not a new cryptographic
review of the already integrated production proof implementation.

## Evidence layout and integrity

The three deterministic archives contain all surviving raw logs, receipts and
source inventories; the two completed test runs also contain their actual Joy
binaries. The overwritten first-fetch logs in v2 cannot be recovered; their
original hashes remain in that receipt. Every
archived file was compared byte-for-byte to the raw evidence before the raw
directories were moved outside the repository. `evidence.json` records archive
hashes, file counts and each integrity result. No failed result was removed
or changed. To inspect an archive, use `tar -xzf <archive>` in an empty directory.
Archives were created with:

```sh
python3 -B scripts/archive-source.py audit/native-proof-profile/local-native-gate audit/native-proof-profile/local-native-gate.tar.gz --epoch 0 --prefix local-native-gate
python3 -B scripts/archive-source.py audit/native-proof-profile/local-native-gate-v2 audit/native-proof-profile/local-native-gate-v2.tar.gz --epoch 0 --prefix local-native-gate-v2
python3 -B scripts/archive-source.py audit/native-proof-profile/local-native-gate-v3 audit/native-proof-profile/local-native-gate-v3.tar.gz --epoch 0 --prefix local-native-gate-v3
```

`static-checks.json` identifies exact lint/test commands and output hashes plus
the checksum-verified actionlint download from its official v1.7.12 release.
`source.json` identifies reviewed gate files and compares runtime bootstrap
hashes against those files. Native Actions artifacts will supply separate
receipts for macOS, Linux and Windows, ARM64 and x64. Their evidence must pass
before claiming six-platform coverage of this selector.

Run `python3 -B audit/native-proof-profile/verify_evidence.py` from the worktree
to recheck source hashes, archive hashes, every retained command log, the final
unchanged source inventories and native binary identity. It requires v2's three
known mismatches exactly, and requires no mismatch in the accepted final run.
