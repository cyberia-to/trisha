# Imported release fixture visibility

Status: focused repair passed; complete archive acceptance pending.
Commit `13c5c24b93d7136624d8725f911b2aa45a175129` makes the two fields read
by the imported-module release smoke explicitly public. The language already
requires this; compiler/runtime behavior remains unchanged.

## Original failure

The second strict source export uses Trisha `4f7074b` and the eleven exact
revisions in `receipt.json`. All four binaries built with actual Rust 1.89.0
and zero warnings. The installed Joy native smoke passed its 49 commands.
The complete coordinated smoke then failed on the imported `release_helper.Pair`
field reads: the fixture declared private `a` and `b`, and the compiler rejected
external reads correctly. This attempt remains failed. No corpus sealing or
binary packaging followed that failure.

`second-export/{prepare,build,smoke}.json` retain the expanded commands, tools,
binary/source identities and original verdicts. The source archive is
113614569 bytes, SHA256
`87e5967777607d9669f3645f419ae5f8534f6dd5a483fdb90050b767f1d280ad`.
The exact failing fixtures and complete outer smoke logs are archived here.
`partial-smoke-files.json` indexes the original 57 partial files; their
30652053 bytes remain at the original local path in `receipt.json`, together
with the source archive, built binaries and Joy proof files. Those large
files are not members of this compact report archive.

Independent gates against these unchanged binaries passed 28 native process
and file checks, and all 133 execution fixtures across 43 baselines: 99
positive cases and 34 expected rejections. The supplemental local wrapper
initially misread only stdout while the summary was on stderr. Its failed
receipt and both streams remain unchanged; `check-independent.py` and
`independent-validation.json` validate the combined output, as the existing
native coordinator already does. There was no repeated benchmark execution.
These independent results do not change the failed full-smoke verdict.

## Focused repair check

`repair/check-release-import.py` extracts the three exact fixtures from the
corrected script, then invokes the actual second candidate binaries in a
fresh directory. It executes the four Trident/Joy/Trisha routes under both
debug and release profiles with input vectors `3,5` and `4,5`: all sixteen
commands return the independent expected values `803` and `809`.

It then restores private field declarations in that temporary fixture and
requires both nox and Triton checks to reject access with the private-field
diagnostic. Both rejections pass. The script and all four installed binary
identities remain unchanged. Every command and its raw output hash is recorded
in `repair/receipt.json`; the raw stdout/stderr files are included.

`nu --no-config-file -c 'nu-check scripts/smoke-release.nu'` and
`git diff --check` pass. The isolated post-commit Trisha installation passes
without warnings. A third fresh export/build and complete smoke must accept
the repaired source; no existing archive or candidate is edited by hand.

`files.json` indexes 110 retained files, 284349 raw bytes. The 50148-byte
`raw-evidence.tar.gz` has SHA256
`4f3c41484c5ae97aaff318b7930fb48f72c93eaebc25a330607358cdf9df9825`.
Every member was compared byte for byte with its original. `retain-local.py`
records the local retention operation and its checks.
