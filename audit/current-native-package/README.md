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
