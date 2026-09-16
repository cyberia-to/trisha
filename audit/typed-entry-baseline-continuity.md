# Typed-entry baseline continuity — 2026-09-12

Actual native program hashes match for all84 unique source/target pairs in the
133 baseline fixtures when compiled with the retained original proof binary,
FINAL3 installed binary and the current compiler-API3 Trisha binary. This proves
compiler-output continuity for the compared input snapshots. Historical proof
receipts have a separate input-binding limitation described below.

## Compared implementations and input snapshots

- Original retained proof binary `/tmp/trisha-v7-proof-binary/trisha`, SHA-256
  `c73e8a58c848769abbc7f259c232ad1ae7d0bcc477872a3cffe55e06c568dede`.
  This identity matches the actual remaining37 proof-run log and receipt.
- FINAL3 installed Darwin binary from
  `/tmp/cyber-release-installed-v7-darwin-final3/bin/trisha`, compiling the exact
  archived source tree under `/tmp/cyber-release-extracted-v7-final3/cyber-source`.
- Current `/Users/master/cyber/trisha/target/debug/trisha`, built successfully with
  compiler API3; compiling current source inputs with release source profile.

For each of84 source/target pairs, the temporary probe parses generated assembly
with actual Triton `Program::from_code` and computes `Program.hash()`. Every native
hash matches across all three implementations. FINAL3 versus current TASM is
byte-identical in47 cases; the remaining37 have only whitespace differences, with
identical token sequences. All266 files in `baselines/triton` (fixture manifests,
source fixtures, hand assembly and witness files) are byte-identical between
FINAL3's archive and the current tree. Actual fixture count133 and baseline count43
remain unchanged. This task generated no new proofs.

Machine-readable comparison, including per-pair source, target, native hash and
assembly SHA-256: `/tmp/final4-baseline-assembly-identity.json`.
Driver `/tmp/final4-proof-binary-continuity.py`, result
`/tmp/final4-proof-binary-continuity.log`. Original and new assembly files are
retained under `/tmp/final4-baseline-assembly/`.

## Historical receipt limitation

The original remaining37 command used `/tmp/trisha-v7-remaining-fixtures`, whose
fixture directories are symlinks into the live source tree. Its guard recorded
the binary SHA, command, cycles, successful proof verification and log identity,
but did not record hashes of source, fixture manifests, witnesses or native
program claims. That selection is not an immutable proof-time input snapshot.
The six separate recursive/native-currency/transaction full-proof logs invoked
the then-live `target/release/trisha` and did not record its executable SHA.

All eight log hashes in `audit/full-baseline-proof-coverage.json` still match their
retained files. The logs establish198 successful fresh proof verifications over99
positive fixtures and the documented negative executions. However, the preserved
artifacts do not independently bind every proof-time input byte to today's
fixture bytes. Recompiling today's inputs with the retained proof binary cannot
retroactively add that missing binding. Therefore this report does not describe
all198 historical statements as cryptographically bound to the new release.

Current FINAL3 fixture identity and current/original compiler output identity are
verified facts; full historical statement continuity is the unsupported stronger
claim. A new complete proof run from a frozen inventory with per-fixture statement,
program and witness hashes would close that evidence gap. Existing full release
smokes and typed-entry proof tests have their separate receipts and scope.
