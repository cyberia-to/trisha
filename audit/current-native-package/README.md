# Current native package validation

Status: exact source export and independent reproduction passed. The fresh
Mac ARM package has passed its four CPU suites, installed/package checks,
133 baseline executions, 47 legacy corpus cases and 27 structured cases.
All five remote producers have passed. The new full198 gate remains in
progress.
Portable consumption of all six new legacy and structured corpora is activated;
its final receipt remains pending.
This distinct branch rehearsal uses source `734df69d...`; the frozen
`e4bac7ff...` receipts retain their original scope.

The following preparation observations were recorded before source export;
the later sections retain actual export, reproduction and package evidence.

`source-preview.json` comes from:

```
python3 -B audit/current-native-package/check-source-preview.py \
  --family /Users/master/cyber/.worktrees/selfhost-0.4-finalization-20261002/distribution \
  --receipt audit/current-native-package/source-preview.json
```

It reads committed Git blobs for all eleven proposed pins, compares protected
inventories with the frozen native and actual public-profile references, and
rejects deliberate Rust-file mutations in Trident, Trisha, Joy, Nox and Zheng.
It does not fabricate an original-matrix success receipt. The executable
production guard still requires the actual completed frozen remote run and
local native CPU evidence. Exact reference inventory digests are constants in
`scripts/current-source-impact.py`; the compressed originals are retained.
The PR21 actual runner was `2b7017f89a495eb43c0feca6818eb68f35c21a02` in run
36958147193. PR head `79f5ba8` includes later evidence retention and is not the
producer revision.

`structured-helper-evidence.tar.gz` preserves all helper trials, their source
fixtures, corpus bytes, raw process streams, exact helper scripts and candidate
metadata. The copied test executable is identified by its original PR21 receipt
and SHA-256 `9736c9b5dad76f40b0c08023783b30affcb64610e95562aa37a6c52b01f8cccf`;
its original authenticated binary remains in the PR21 retained evidence.
The fixture-only candidate metadata is explicitly a helper harness, not a
new production source/package claim. The final commands were:

```
python3 -B scripts/current-structured-corpus.py generate \
  --source ../measurements/structured-helper-v1/fixture-source \
  --candidate ../measurements/structured-helper-v1/test-candidate \
  --output ../measurements/structured-helper-v2
python3 -B scripts/current-structured-corpus.py verify \
  --corpus ../measurements/structured-helper-v2 \
  --candidate ../measurements/structured-helper-v1/test-candidate \
  --receipt ../measurements/structured-helper-v2-verification.json
```

The exact final helper generated five valid bounded certificates, rejected a
malformed artifact without replacing an old destination, and passed 27 corpus
checks (6 accepted, 21 rejected). The successful compiler-envelope case also
extracted and executed its generated program. These are small public-profile
fixtures, not whole-compiler SH7/SH8 evidence. An earlier added assertion used
Python indexing for an intentionally absent optional observation field and
failed with `KeyError: 'prover_observations'`; its script, partial receipt and
raw output remain in the archive. The final helper uses `.get` and requires
both an unattested physical-resource claim and no prover observations.

`checks.json` records Python parsing, existing actual-toolchain rejection tests
and actionlint 1.7.12 against the dormant workflows and native matrix workflow.
The corresponding stdout/stderr files retain the complete check output. No
production build, native matrix or full198 result is inferred from these checks.

## Review correction and case-map hardening

Root review of `4df03759fbbc8ff78aa0b7fc3cb3864f63d51889` found the full branch
`git diff --check 01f8a80..HEAD` failed on ANSI/trailing whitespace and EOF in
the preserved original Trident CPU log. Earlier local whitespace checks covered
only uncommitted changes. The exact failed root review is retained in
`root-review-original.tar.gz` (SHA-256
`3b1489e67f7009ba969ac8cb808acf0ddc51e721a593205b83ec8787e57741ad`).
The exact-path `.gitattributes` entry disables whitespace diagnostics only for
that raw log. Its bytes still match the original CPU receipt; no log bytes were
edited. The full branch comparison plus current changes subsequently passed,
as recorded in `hardening-checks.json`.

The structured consumer now fixes expected exit and extraction mode for every
case ID. A fresh actual helper run again passed all 27 cases. Two further
process tests rejected a count-preserving exchange of a valid/reject expected
exit and a changed compiler-diagnostic extraction mode. Their full inputs,
commands, raw output and final helper are in
`structured-helper-v3-evidence.tar.gz` (SHA-256
`137b00643cd71bfa660e6a3b3bf668edc789259d1eaa9b83e2d167417db6b3ae`).
Earlier helper evidence stays unchanged.

## Native Windows checkout byte identity

The retained PR21 selector hashes differ between Windows (`e0fdfaad...`) and
Mac (`a5a6df5b...`) because native checkout line endings differ. The new package
uses raw selector/reference hashes, so it must preserve those exact Git bytes.
`checkout-bytes/receipt.json` records a read-only `git -c core.autocrlf=true
cat-file --filters HEAD:PATH` exercise: all six existing byte-bound files
changed before explicit attributes and matched their original hashes after.
Exact-path `-text` entries now cover the input selector, release selector,
Mac CPU raw reference files, public-profile receipt and future frozen-run API
reference. The sole whitespace exception still applies only to the original
Mac CPU log. Production source archive contents and selected revisions are
unchanged by this bootstrap metadata correction.

## Original matrix gate binding

The source-impact guard now requires all five distinct original producer
inspections as well as the successful original run API record. Each must bind
the exact frozen source/provenance, original runner and actual native Rust 1.89
host, with inspected compiler CPU evidence. A successful Actions badge alone
cannot authorize inheritance if a hosted compiler was shadowed by another
installation. `original-matrix-rejections.json` records rejection of the four
currently available real producers and of a duplicate substituted for the
missing Intel Mac. The complete positive check waits for actual Intel evidence.

### Exact current source exported

The frozen five-target producer run 36949324686 completed successfully, and
all five original authenticated ZIPs passed native Rust 1.89, source/kit, CPU
and producer receipt inspection before the current export. Their actual
inspections and original run API are retained under `references/`.

`source-export/export-reviewed-source.py` then checked the eleven clean exact
commits and their observed origin reachability, invoked the committed Trisha
source packager, and passed the archived source verifier, accepted kit guard
and current source-impact guard. Original command streams and hashes are in
`source-export/original-commands.tar.gz`. The resulting archive is 441342969
bytes with SHA-256 `734df69dc7d43467fc9ae574c7cf7b25eb9b4ec9bc08e9ca3f96b9500131f42e`;
its `sources.json` SHA-256 is
`3c6f2ced084812e73f97c069169f83807fc5d389e54b581dd52f10982cd5b227`.

The source preparation selector activates independent Linux reproduction
from those same eleven origin commits. Upload to the existing unpublished
draft requires the exact archive hash. Native builds and the new actual
198-proof measurement remain pending; no frozen binary receipt is relabeled.

### Independent reproduction passed; native production activated

Run 36968949223 at `1e159e6d3de1cfbba626d1d16cb44f5b4a573136` independently
reproduced archive `734df69dc7d43467fc9ae574c7cf7b25eb9b4ec9bc08e9ca3f96b9500131f42e`
from all eleven exact origin pins, passed the strict source/impact guards,
and uploaded its exact 441342969 bytes to the existing unpublished draft.
The tag remained absent. `source-reproduction/` retains the original
authenticated Actions ZIP and the exact source asset receipt.

The current package selector now activates five native remote producer jobs
and a separately measured local Mac ARM lane. Both use these exact bytes;
the local lane requires a new full198 proof gate after its fresh builds.
All producer/consumer and full198 results remain pending at this commit.

### Actual current Mac package gates passed

The local lane started with selector/runner
`ecdc4e2ea131c50a860036e34ee7636b91fb8dde` and observed Rust, Cargo and rustdoc
1.89.0 from the same native toolchain. Four fresh binaries were built from
archive `734df69d...`. All CPU commands passed: Trident workspace libraries
762 tests, Trisha CPU/default suites 429, Joy workspace 215, Nox standard
library 245. Each command and original output is preserved in
`local-package-gates/original-package-receipts.tar.gz`. These Trident library
counts are separate from the frozen full 1231-test integration measurement.

All 133 baseline executions and the installed/package gates passed, including
47 legacy corpus cases and 27 structured public-proof cases (6 accept, 21
reject). The current Mac Joy binary SHA-256 is
`cd8403626c29740b41e62c3160636bbce3a8ccd9abadc75d0b0bb874b6e441e6`.
`local-package-gates/guard.json` binds the actual package identities.
The added current receipt inspector passed against these actual package
receipts and rejected five mutations: Cargo version, input selector digest,
consumer Joy digest, count-preserving case-map swap and proof bytes. Its
check script and receipt are retained alongside the exact inspector. The
whole remote-container inspector awaits the actual remote producer outputs.

The new actual198 gate is running under the original 28 GiB process-group
guard and host free-memory check. Unique current Mac binary, legacy corpus
and structured corpus draft transport is running separately. Neither an
in-progress proof gate nor uploaded package bytes establish final acceptance.

### Current Mac package transport completed

`local-package-transport/` retains original command streams, before/after
origin-ref and ancestry checks, API responses and the package-only receipt.
All eleven exact source commits remained reachable; recorded default refs
remained unchanged. The existing release remained a draft and its tag remained
absent. Three distinct server-digest-checked assets were retained:

- binary package 604908144, SHA-256
  `b542e6e3bf8a15c4650cfeb8bda436ba45a1ecf32844aa9655275bf42086ab9b`;
- legacy corpus 604914519, SHA-256
  `1dca29b3906ca5fbb36a76c92ab712e93714260334b230785e4afc3f2ba4ff39`;
- structured corpus 604922737, SHA-256
  `488b34e98b975e3cb508241913fcca871a40953452d07caba085c8b26a630978`.

The transport coordination ended at 05:53:49 UTC on 2026-10-02. Its original
receipt retains the in-progress full198 status observed during upload; it is
not a final proof acceptance receipt. The complete current proof verdict will
be recorded separately after the native driver exits.

### Four current remote producers checked

At the observation retained in `remote-producer-progress/`, both Linux and
both Windows jobs in run 36969168806 had succeeded. Each original Actions
ZIP was authenticated against its API digest and inventoried, then checked
with the retained `inspect-current-native-producer.py`. All four passed
the exact source/kit/native Rust 1.89 identities, applicable CPU commands,
133 execution fixtures, package gates, 47 legacy cases and 27 structured
cases. The exact commands, totals, artifact identities and compressed original
job logs are retained per target. ANSI-normalized warning inspection found
no Rust warning in the original CPU/build logs. Intel Mac, full198 and portable
consumption remain separate pending gates at this observation.

The first independent WinARM inspection failed because its checker expected
LF-only hashes for two Python helper files. Actual Windows checkout used
CRLF. `inspector-checkout-correction/` preserves that failed command and raw
output. The exact source revision `ecdc4e2...` was independently transformed
with Git `cat-file --filters` under both `core.autocrlf` settings. Its Windows
byte hashes match the producer's recorded helper hashes exactly. The corrected
inspector requires those exact CRLF hashes on Windows and the exact LF hashes
on the other targets. All source-archive/input-selector hashes remain fixed;
no producer bytes or original receipts changed. The corrected inspector also
passed the actual local Mac added checks and rejected the same five receipt
mutations. Its earlier LF-only version remains in `local-package-gates/`.

### All five current remote producers passed

Run 36969168806 completed successfully on all five selected native hosts at
runner `ecdc4e2ea131c50a860036e34ee7636b91fb8dde`, consuming exact archive
`734df69d...`. `remote-producers-final/` binds the completed original run,
all five authenticated artifact inventories, passing independent inspections
and the final Intel Mac job log. Earlier four original job logs remain in
`remote-producer-progress/`. Fresh eleven-origin observations preserve source
reachability before draft transport; the fixed Trisha pin remains an ancestor
of the advancing `release/0.4` branch.

Read-only inspection of all 24 exact packaged binaries passed.
`remote-producers-final/linkage/` retains the commands and original compressed
LLVM/otool output: both Windows targets' actual PE imports satisfy the static
CRT packaging policy, and both Linux targets' imported glibc versions are at
most 2.35 on the measured Ubuntu 22.04 hosts. Mach-O deployment commands are
recorded separately from execution on an older macOS floor. No Windows 11 x64
or macOS 14 Intel execution qualification is inferred.

The distinct `.github/current-package-assets.json` selector activates the
reviewed draft transport for five exact binary archives, five legacy corpora,
five structured corpora and five original authenticated Actions ZIPs. Final
full198 and six-platform portable consumption remain pending at activation.

### Exact six-package consumption activated

Transport run 36973773801 at `a12f032f3dfd866025e07fd6f1347b0bf0b2d48d`
passed and retained twenty unique assets in the existing unpublished draft:
five binary packages, five legacy corpora, five structured corpora and five
original authenticated producer ZIPs. The original transport ZIP, receipt,
all asset IDs/digests and post-upload origin checks are retained in
`remote-asset-transport/`. Default refs remained unchanged; the draft's tag
remained absent. Joy and Trisha release branches advanced independently,
while this package's exact eleven source pins remain fixed.

The verify selector now binds all six packages and both six-corpus sets,
including the already retained local Mac package. Five native remote consumers
and one local Mac consumer will exercise all 36 producer/consumer pairs, each
with 47 legacy and 27 structured checks. The separate free macOS14 ARM lane
checks the same corpora and accepted kit on its observed host. This bounded
consumer phase does not rebuild or generate full proofs.

`matrix-helper-checks/` retains the independent checker and its actual
six-producer self-consumer trial: 444 case checks passed, and five altered
receipts were rejected (legacy binary/outcome, structured producer identity,
command inventory and raw output digest). That helper trial does not claim
the still-pending cross-platform consumer matrix.
