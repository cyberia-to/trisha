# Coordinated CPU platform checks — 2026-09-12

These are local working-tree checks, before final source/binary packaging.
Compilation and runtime verification are reported separately.

| Product | macOS arm64 Rust1.89 default CPU check | Linux x86_64 cross-check |
|---|---|---|
| Trident0.4 | passed | passed, default features |
| Trisha0.3 | passed | passed, all features |
| Joy0.5 | passed | passed, default features |
| nox0.3 | included in the above dependency closure | passed, all features |

Rust1.89 checks use the explicit toolchain rustc and an isolated target folder:

```sh
RUSTC="$HOME/.rustup/toolchains/1.89.0-aarch64-apple-darwin/bin/rustc" \
  CARGO_TARGET_DIR=/tmp/cyber-msrv-check-target \
  rustup run 1.89.0 cargo check --manifest-path trident/Cargo.toml --locked
```

The corresponding commands select `-p trisha` with `trisha/Cargo.toml` and
`-p cyber-joy` with `joy/Cargo.toml`. Logs are
`/tmp/{trident,trisha,joy}-msrv189-check.log`. This verifies the default CPU
dependency closure; an all-feature MSRV claim has not been established.

Linux checks use Rust1.98 and its installed Linux target. The Homebrew Rust1.95
sysroot lacks that target, so the earlier E0463 missing-core check was not a
source defect. Ordinary Trisha cross-check then required a Linux C toolchain
for ring. The successful command supplies that toolchain through cargo-zigbuild:

```sh
RUSTC="$HOME/.rustup/toolchains/stable-aarch64-apple-darwin/bin/rustc" \
  CARGO_TARGET_DIR=/tmp/cyber-linux-check-target CARGO_BUILD_JOBS=4 \
  rustup run stable cargo-zigbuild check --manifest-path trisha/Cargo.toml \
  -p trisha --target x86_64-unknown-linux-gnu --all-features --locked
```

Logs: `/tmp/trident-linux-rustup-check.log`,
`/tmp/trisha-linux-zig-check.log`, `/tmp/joy-linux-rustup-check.log`,
`/tmp/nox-linux-allfeatures-check.log`. None of these checks links and executes
a Linux release binary. Linux runtime smoke remains outstanding.

## Platform defect corrected

The mining helper previously loaded Apple-only acpu unconditionally. Trisha's
acpu and optional aruminium dependencies now have a macOS/aarch64 target guard;
GPU exports, benchmarks and CLI dispatch use the identical guard. Other CPU
hosts use official portable Tip5 and do not pin workers to Apple cores. The
portable hash operates without per-nonce heap allocation and preserves the
raw Montgomery word ABI, including the variable-length padding boundary.

Two native regression tests compare the real Apple implementation and portable
fallback against official Tip5 for zero/boundary fields, mixed digest pairs and
lengths0/1/5/9/10/11/19/20/21/300. Both pass without warnings:
`/tmp/trisha-portable-hash-tests.log`. These test hash equivalence; they do not
certify the whole Neptune mining protocol, GPU kernels or network submission.

Nox separately guards its optional Apple dependency and falls back to CPU jet
implementations on other targets. Its default169/all-feature175 test receipts
and the input-admission correction are in `nox/audit/jet-input-release.md` in
the coordinated source tree.

## Subsequent adapter and cross-link checkpoint

After adding the pinned Neptune consensus/RPC adapter and repairing mining,
Trisha's default CPU check passes again on Rust 1.89 without warnings
(`/tmp/trisha-neptune-msrv189-final.log`). Its Linux x86_64 all-feature check
also passes (`/tmp/trisha-neptune-linux-check.log`). The MSRV run caught an
unused assignment in the legacy-buffer release path; `drop(legacy.take())`
now explicitly frees the previous buffer before constructing its replacement.

All three CPU binaries also link for Linux arm64 with Rust 1.98 and Zig.
Those cross-link runs emit Zig's deprecated linker optimization warning and
are not zero-warning final candidates. Logs are
`/tmp/cyber-linux-release-check/{trident,trisha,joy}-build.log`.
The separate [native Linux gate](linux-runtime-validation.md) builds from a
fresh source archive with Rust 1.89 and the native GNU toolchain, then tests
the installed binaries. Cross-link success alone is not runtime verification.
