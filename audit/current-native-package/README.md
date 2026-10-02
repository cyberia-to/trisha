# Current package runner preparation

This records helper and source-comparison checks before a new production
source export. No current package has been built or accepted by this report.
The dormant selectors/workflows require a separately selected source digest
and exact current input-file digest before dispatch.

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
