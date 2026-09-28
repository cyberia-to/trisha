# Archived candidate CPU and baseline proof gates

The third local candidate passed the exact archived CPU package selections
and the separate 198-proof baseline gate. This is one macOS ARM rehearsal
from committed feature-branch inputs. It is not a six-platform release
verdict, SH6 replacement, accepted portable kit, or SH7/SH8 compilation proof.

| Archived CPU command scope | Passed | Failed | Ignored | Rust summaries | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Trident workspace | 1231 | 0 | 5 | 49 | 3829.925 |
| Trisha four selected packages | 429 | 0 | 6 | 64 | 57.950 |
| Joy workspace | 172 | 0 | 0 | 27 | 50.153 |

Every command exited zero with zero Rust warnings. Counts are test
executions within each command, not a deduplicated cross-repository count.
The Trident workspace count includes workspace members and does not replace
the historical 1197 compiler-only count. Ignored tests remain ignored.

The subsequent proof gate passed all 133 fixtures: 99 positive fixtures,
each with a fresh classic and hand proof, plus 34 rejection fixtures.
All 43 hand baselines were covered. The archived checker recorded 198
fresh generated-and-verified proof events and completed in 3972.265937 seconds.
The sampled process-group RSS peak was 19917635584 bytes (18.55 GiB), from
791 samples. The unchanged guard was 28 GiB, sampled approximately every
five seconds; no guard stop occurred. This is a sampled peak, not a claim
about memory between samples.

## Exact inputs and commands

The source is the immutable third export with Trisha
`13c5c24b93d7136624d8725f911b2aa45a175129`, Trident
`57491633fbccb58ae44dca2da438ee31430be1bc`, Joy
`adb424023ae11a2264567d21171c3c2b3aa06f64`, Nox
`172811b7746cdcd6ab198a3ed976dc6c19f55d5b`, and Zheng
`633e5ba980db94ca10d9d6b67cf24d9d3aef63a7`. All eleven source revisions
and source/vendor identities are retained in `metadata/prepare.json`,
`metadata/sources.json` and `metadata/source-verification.json` inside the
archive. These newer Nox/Zheng inputs are separate from the frozen SH6 pins.

The measured driver is `cpu-and-proofs.py`, SHA256
`f572f9dee7b8a144a0d7418db737705e0a98317bba98c5cd199ec6b110e30561`.
Its full argv, cwd, environment, command exits, timings and unmodified
stdout/stderr identities are in `cpu-and-proofs.json`. It runs:

```text
cargo test --manifest-path SOURCE/trident/Cargo.toml --release --locked --no-fail-fast --workspace -- --test-threads=1
cargo test --manifest-path SOURCE/trisha/Cargo.toml --release --locked --no-fail-fast -p trisha -p trisha-rs -p trisha-neptune -p trisha-honeycrisp -- --test-threads=1
cargo test --manifest-path SOURCE/joy/Cargo.toml --release --locked --no-fail-fast --workspace -- --test-threads=1
python3 -B SOURCE/trisha/scripts/check-baselines.py CANDIDATE BASELINE_WORK --rss-limit-gib 28
```

Each CPU command uses its own `CARGO_TARGET_DIR=CANDIDATE/build/<project>`.
Actual rustc and Cargo were 1.89.0 through rustup, and actual Z3 was the
coordinator's pinned 4.15.3 asset. `CARGO_BUILD_JOBS=4`,
`RAYON_NUM_THREADS=4`, and `TVM_LDE_TRACE=no_cache` remained fixed. CPU
commands and the proof gate ran serially. A separately recorded supplied-C2
execution overlapped part of the proof gate; elapsed times are local
observations, not an isolated performance comparison.

The original driver checked source inventories, candidate metadata and all
four installed binaries after completion. The archived proof checker also
checked its own source, candidate, complete source inventory and binary
hashes before and after proving. All matched. The retention collector's
supplemental `metadata/tools-end.json` confirms the recorded rustc, Cargo
and Z3 hashes still matched; it is explicitly separate from original gate
output. No compiler/runtime source or installed artifact was changed.

## Proof payload boundary

The exact archived `source/bench.rs`, from Trisha 13c5c24b, lines 197–240
generates a proof, compares its complete claim with the expected program,
public input and output, calls the verifier, then prints
`TRISHA_PROOF_VERIFIED`. It records format, complete claim, proof HEMERA
identity and byte length. The proof payload is then dropped in memory.
There is no proof-output option in that archived benchmark command.

All 198 raw events are retained unchanged, together with the exact
`source/bench.rs` SHA256
`c27bf22f042458b412c32d1d1aa149a6e14aab189f2c9bd96b1d1bc12389c112`
and the checker that consumes exact classic/hand pairs,
`source/check-baselines.py` SHA256
`29b98dac0b6f07f579b3f44fdbe7e41c262b0372088d2909acf4e0d076cd229b`.
The 198 baseline proof payloads are transient and cannot be independently
cryptographically replayed from this receipt. The separately persisted
installed proof corpus is retained under Trisha
`audit/native-soft3-release/installed-rehearsal/` at
`f512e87e197df477eb4b8d952886f5d3a38a1d2b`; it does not substitute for these
baseline proofs. Its exact index/receipt hashes and the large source,
binary and corpus archive identities are in `files.json`.

## Retention check

`raw-evidence.tar.gz` contains 36 files, 2678541 raw bytes, with zero tar
timestamps/owners and a zero gzip timestamp. The archive is 410462 bytes,
SHA256 `0994dd69692feb1cbfd4df8c4d48eef3da67e957ab6ca552475866e5a9ba3b66`.
Original whitespace and paths inside recorded receipts/logs are preserved.
Original measurement files remain at their recorded paths. Large archive
containers and installed binaries are referenced by exact identity and are
not duplicated here. Earlier rehearsal failures remain retained separately.

```sh
python3 -B check.py .
python3 -B -O check.py .
```

Both commands passed. The standalone checker verifies exact archive bytes,
all member hashes, original CPU results, source/binary/tool bindings and
the archived proof checker's recorded oracle coverage. Only the two
log-checking functions from the exact pinned source are executed; no
compiler, guest, prover, build or external command is invoked. Three
synthetic missing/duplicate/altered-claim cases reject. A separate one-byte
archive corruption test also rejects. Exact test commands and raw outputs
are retained in `validation.json` and the adjacent logs. These are retention
checks and do not add to the original 198 proof count.
