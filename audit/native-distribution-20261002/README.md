# Native 0.4 distribution rehearsal — 2026-10-02

Status: source and accepted-kit guards passed. The Linux ARM and Windows ARM producers passed;
three remote producers and the corrected local Mac ARM lane remain in progress.
The first local attempt was rejected for using Homebrew Rust 1.95 instead of
the pinned 1.89. Its original evidence remains in `rejected-local-rust195/`.
The fresh local lane checks both actual Rust and Cargo versions and paths.
This is a committed, pushed `release/0.4` branch rehearsal. The default branches,
existing tags and published releases are outside its scope. Product package
versions remain those in the frozen source manifests.

`origin-inputs.json` records the actual origin-ref checks and every source
revision. `prepare.json` binds each executed command and output to that closure.
`prepare.py` performs the strict export and guards. The source archive is
421623556 bytes, SHA-256
`e4bac7ff7260a5f395febc196b3e4792653e0ff81d7887d688e16ea0959aa361`.
The accepted kit is the existing retained Trisha artifact, SHA-256
`a3052d95c3de6d622157988a8e74826b2f0140724a634298458c3d75f6b508bd`.
Its production unpack check passed against the newly archived Trident sources.
The feature preparer at `49deb1a953dcc1102201df29f0c55a0286c70ef1`
reproduced the exact source archive on an actual Ubuntu runner in
[run 36948984631](https://github.com/cyberia-to/trisha/actions/runs/36948984631).
The source asset is `604481115`; the accepted kit asset is `604463150`.
The native selector binds both IDs and their verified SHA-256 identities.
`remote-preparer-artifact.zip` retains the original GitHub evidence ZIP, bound
to the saved API metadata by SHA-256
`cdb0275b9300d89cc031a548a3cbc2d68a072f06ad54ed245925b61eed822173`.
Default/release branch refs remain byte-identical and the draft tag remains
absent after upload. Original commands, API metadata and the interrupted local
upload/owned-starter cleanup receipts are retained alongside this record.
The pre-existing unpublished draft is transport only. No tag is created.
The original local upload remains recorded separately; local network throughput
motivated this exact-byte remote preparation route.

## Execution

The existing `release-candidate.yml` workflow runs from this feature branch.
Its five native runners build four portable binaries and exercise the archived
CPU workspace suites, Joy proof routes, process/file and LSP probes, all baseline
executions, fresh installed proof smoke, kit smoke, deterministic packaging,
and final unpacked identities. The existing pinned Neptune intent adds both
explicit transaction binding/process gates. Every failed run remains evidence.
The separate local Mac ARM lane uses the same selector/source with
`full_baselines: true`; the archived driver sets a 28 GiB proof RSS guard.
Source, candidate and proof-corpus identities must converge across all lanes.
After production, each native consumer verifies all six sealed producer corpora.

```sh
gh workflow run release-candidate.yml --repo cyberia-to/trisha --ref test/0.4-native-distribution-20261002
```

The source snapshot and current six-platform proof matrix are separate from
SH6 native bootstrap acceptance and SH7/SH8 compiler proof work. Native runner
success does not establish an older OS floor. The proposed macOS 14 and Windows 11 x64
floors still need matching-host receipts before they can become supported
minimums; the selected runners are macOS 15 Intel and Windows Server
2022 x64. This rehearsal does not relabel either proposed floor as validated.
`macos-link-inspection/receipt.json` retains actual `sw_vers`, `uname`, pinned
Rust, compiler/linker, `file` and `otool` commands on the local macOS 26.4.1 ARM
host. These are the first, subsequently rejected Rust 1.95 binaries; the
separate Rust 1.89 inspection was not the compiler used by that build.
The four binaries advertise Mach-O `minos 11.0` and SDK 26.4; their
observed runtime libraries are system libraries. Original raw command streams
and the candidate inventory are retained. `binding.json` records the unchanged
four installed hashes after inspection. These link values do not replace
execution on macOS 14.
The separately retained `macos-rust189-link-inspection/` contains the same
actual host/link commands against the fresh Rust 1.89 build, with its distinct
candidate and four binary hashes checked before and after inspection. The
candidate's own recorded compiler version agrees with the fresh preflight.

The separate `native-rehearsal-assets.yml` transport is dormant until a pinned
producer selection is committed. It requires successful exact producer runs,
raw Actions ZIP/API digest agreement, source and kit provenance agreement, and
the binary archive and sealed corpus identities before uploading unique draft
assets. It also preserves each original authenticated Actions ZIP as an evidence
asset, so the raw producer container survives the Actions retention period.
It executes no archive code. Existing archive, source-verifier, binary
package and kit guard suites pass under `-W error`; their actual commands and
outputs are retained in `transport-helper-checks/`. Native producer/corpus
acceptance remains separate from these helper checks.

## Rejected local toolchain and correction

The original native bootstrap installed Rust 1.89 and set `RUSTUP_TOOLCHAIN`,
but Homebrew `rustc` and `cargo` took precedence in the host `PATH`. The original
candidate records actual Rust 1.95. Its CPU gate was stopped before completion;
no full proof gate or native acceptance is claimed. The rejection receipt,
driver, selector, commands, raw output streams, partial CPU log, kit smoke and
all four exact binaries remain in the byte-verified rejected archive. Cargo
target directories and the complete source archive remain at their original
paths. The existing link-inspection record was preserved unchanged.

```sh
python3 -B -W error audit/native-distribution-20261002/rejected-local-rust195/verify.py --originals
```

The fresh measured driver and actual preflight are in `local-rust189/`. The
reusable `scripts/native-rehearsal-local.py --family FAMILY --output-name NAME`
requires a fresh output, selects actual `rustup which --toolchain 1.89.0` binary
paths, prepends their directory, sets `RUSTC`, checks both versions and native
architecture, and rejects any candidate whose recorded compiler differs.
Remote asset acceptance now rejects the same mismatch from actual candidate
metadata. The frozen remote bootstrap does not separately record Cargo's
version; transport receipts preserve that observation limit explicitly.
For subsequent builds, `native-candidate.py` now applies the same explicit
toolchain selection before compilation and records both actual tool versions,
paths and executable hashes. `bootstrap-toolchain-check/` records its actual
`pin_toolchain` regression on this host: child lookups resolve Homebrew 1.95
before selection and the pinned native 1.89 tools afterwards. The current
remote producer run remains at its original bootstrap revision.
The follow-up check in `bootstrap-toolchain-check-v2/` additionally binds
`rustdoc`, clears inherited compiler/doc-tool overrides, and selects the full
native host in both installation and lookup (`1.89.0-<target>`). This prevents
a Windows ARM host's default x64 rustup host from selecting the wrong tools.
The local source exporter requested 1.89 through `rustup run ... nu`; that
invocation alone does not establish the Cargo version used by the external
Nu process. No observed exporter-version claim is made. Source acceptance
rests on the exact origin closure, independent byte-identical remote export,
and source/kit guards.

The dormant `native-rehearsal-macos-floor.yml` adds a separate, free macOS 14
ARM consumer after all six exact producer assets exist. Its selector hash is
pinned, and it requires actual macOS 14 / ARM64 before running the archived
verification phase. It inspects the host/tool versions, records commands and
sampled process-group RSS, and bounds the consumer to 5 GiB and 30 minutes.
Only installed-kit smoke and the six existing proof corpora run; no compiler
build or new proof generation is selected. This supplements the six producer
lanes and does not close Intel macOS 14 or Windows 11 x64 execution gaps.
The [current standard runner table](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
lists 7 GB for `macos-14` ARM; GitHub's
[retirement notice](https://github.com/actions/runner-images/issues/13518)
sets November 2, 2026 as the image retirement date. No paid runner is selected.

## First measured native producer

The frozen selector at `c94da47247457f9e819c2682e74d34f5f1756f62` passed its
Linux ARM producer job in [run 36949324686](https://github.com/cyberia-to/trisha/actions/runs/36949324686/job/110658543001).
`producers/aarch64-unknown-linux-gnu/` retains the artifact API metadata, full
original-file inventory, compact original logs/receipts, and the independent
read-only inspection command. Its authenticated original Actions ZIP is retained
locally with SHA-256 `ccc1174519e4c55444b12ba9cd89674eca3479c9f5df1e64a1f3126efd222031`;
durable draft transport is pending completion of the whole producer run.
The actual candidate records native Rust 1.89.0 and Linux/glibc 2.35.
CPU summaries total 1,231 Trident, 429 Trisha and 173 Joy tests passed, with
zero failed summaries or Rust warning headers. The installed and unpacked kit,
Neptune binding/mock-client gates, process/file probes, 133 baseline executions,
fresh installed proof smoke and 47 corpus cases (18 positive, 29 rejections)
passed. These are the original frozen Joy proof routes, separate from the newer
SH7 profile implementation. No full 198-proof result is claimed for this runner.
The inspector compares the packaged candidate with the documented portable
inventory: `package-binaries.nu` removes only the absolute build `source` path.

```sh
python3 -B -W error audit/native-distribution-20261002/inspect-native-producer.py RETAINED_ARTIFACT_DIRECTORY FRESH_INSPECTION_JSON
```

The Windows ARM producer from the same run also passed. Its original ZIP
`11207109355` has SHA-256 `510fb6ebc05807dbdb8b9f4da7dffb577986114b5eeb479b2181181fceef6e58`;
`producers/aarch64-pc-windows-msvc/` retains its metadata, exact selected original
logs/receipts and inspection. Actual native Rust 1.89.0, Windows 11 10.0.26200
and ARM64 PE machine `0xaa64` are observed. CPU summaries contain 1,213 Trident,
418 Trisha and 167 Joy passes with zero failures or Rust warning headers;
platform-specific test selection accounts for the different totals. All named
producer gates and the same 47 corpus cases passed. The four observed PE import
tables contain no separately installed MSVC runtime dependency.

Both completed producers now also retain their original job logs and exact
download-command/SHA receipts. The Linux host was Ubuntu 22.04.5, runner image
`ubuntu-22.04-arm` version `20260927.143.1`. The Windows host was runner image
`windows-11-vs2026-arm64` version `20260924.168.1`. These are actual matching-host
observations; the Windows result names build 26200 and does not establish
execution on every earlier Windows 11 build.

## Local Mac package transport

The fresh native Rust 1.89 Mac build completed the package-producing gates,
including CPU suites, both kit checks, 133 baseline executions, installed proof
smoke, 47 corpus cases, deterministic repack, unpacked binary hashes and LSP.
Its full 198-proof run started afterwards and remains pending. The exact package
and corpus were uploaded while that independent proof gate ran. The successful
`local-package-transport/receipt.json` therefore claims package transport only.

- Binary asset `604717111`, 16,776,610 bytes, SHA-256
  `3def4024793c8416a369996020ae8bbf7031c87ff3ce5a0408cc1081d3d7743b`.
- Corpus asset `604728905`, 25,210,637 bytes, SHA-256
  `b632aaecca4f1e3fe7920e2e3cc223780101dde798f9a6d2a029e0f51cb4ab54`.

Both use unique `rehearsal-20261002-e4bac7ff-local-rust189-` names on the existing
unpublished draft. Original commands and raw API responses bind the upload
bytes to the server digests and continued tag absence. Before/after origin-ref
and comparison API receipts independently establish that all eleven frozen
pins remain reachable: Joy, Nox, Trisha and Zheng have advanced on their release
branches; the other seven selected refs remain at the original pins. Observed
master/main refs were unchanged across this transport. This explicitly preserves
the frozen closure rather than treating newer release-branch heads as its inputs.

### Additional frozen native producers

Authenticated run 36949324686 at selector
`c94da47247457f9e819c2682e74d34f5f1756f62` completed the Windows x64 producer
at 03:51 UTC and Linux x64 producer at 04:10 UTC on 2026-10-02. The retained
`producers/<target>/inspection.json` records the exact API artifact, original
ZIP digest, package and corpus identities, actual native Rust 1.89 observation,
CPU summaries and all named gates. `job.log` preserves the actual hosted image
and commands; `job-log.json` authenticates the downloaded log bytes.

Windows x64 ran on Windows Server 2022 and passed 1213 Trident, 418 Trisha and
167 Joy tests. Linux x64 ran on Ubuntu 22.04 and passed 1231 Trident, 429 Trisha
and 173 Joy tests. Each passed all 133 baseline executions and the fresh
47-case legacy corpus (18 accepted, 29 rejected). These numbers come from
`python3 -B audit/native-distribution-20261002/inspect-native-producer.py`
against artifacts 11208420793 and 11208532313 respectively. The Windows 11
x64 minimum is still untested. Intel Mac, portable cross-consumption and the
local full 198-proof verdict remain separate pending gates at this point.

### Completed frozen Mac ARM full proof gate

The fresh Rust 1.89 producer at runner revision
`20273ae93a63973cc04d7206abff517853cfff58` completed at 04:35:13 UTC on
2026-10-02. `local-rust189/final/` preserves the final driver, candidate, complete
198-proof receipt, byte-preserved compressed original start/log/telemetry and
full original-file retention inventory. The driver exited 0 with every named
producer gate passed. CPU summaries contain 1231 Trident, 429 Trisha and 172 Joy
passes on this actual Mac; other native hosts retain their own measured totals.

The exact archived command was `python3 -B trisha/scripts/check-baselines.py
CANDIDATE BASELINE_WORK --rss-limit-gib 28`, invoking the installed candidate's
`trisha bench ARCHIVED_BASELINES --full`. It generated and verified 198 fresh
proofs for 99 positive fixtures and rejected 34 negative fixtures, with all
source/vendor/candidate/binary identities unchanged. Its actual elapsed time
was 4106.085598958016 seconds and peak inner proof process-group RSS was
17252352000 bytes (about 16.07 GiB). The complete native driver took
8966.535507666995 seconds; its separately measured outer build/smoke group
peaked at 9463103488 bytes. These peaks describe different process groups and
are not summed or substituted for one another.

`python3 -B measurements/retain-local.py` in the owned distribution family
independently checked the original archived baseline parser, 198 events,
fixture inventory, raw log identities, telemetry bounds, CPU summaries and
package/corpus hashes. Its exact script is preserved beside `retention.json`.
The resulting complete original evidence archive has 80874375 bytes and SHA-256
`0b613f41a1c65aeb937f636070b0c497a6cb60c938f445dd53e3983ab9c15fab`.
Draft upload is in progress at this commit. Cross-platform corpus consumption
and the remaining Intel Mac producer are separate pending gates.

### Original evidence whitespace

A subsequent complete-branch `git diff --check d597381..HEAD` exposed ANSI
trailing whitespace and native Windows CRLF in 32 preserved original log/JSON
files. The earlier incremental checks had not covered already committed files.
`raw-whitespace-check/` retains the exact failed check, corrected full-branch
check and original Git/worktree SHA-256 comparison. `.gitattributes` now gives
only those 32 exact paths `-text -whitespace`; no evidence bytes were edited.

### Durable completed Mac evidence

The complete original Mac native/198 archive is now draft asset 604817694,
`rehearsal-20261002-e4bac7ff-local-rust189-evidence.tar.gz`, with server-confirmed
SHA-256 `0b613f41a1c65aeb937f636070b0c497a6cb60c938f445dd53e3983ab9c15fab`
and 80874375 bytes. `local-evidence-transport/receipt.json` records successful
transport and postchecks from 04:42:00 to 05:08:10 UTC on 2026-10-02. Original
command output, API responses and all eleven source reachability checks before
and after the upload are preserved beside it. The existing release remained a
draft, its tag remained absent (404), and all recorded default refs remained
unchanged. The earlier package-only upload receipt remains unchanged and still
states that the 198 verdict was pending at its own observation time.
