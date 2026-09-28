# Portable compiler kit rehearsal

Status: implementation guards and local historical-C2 rehearsal passed.
Production accepted-kit assembly remains pending the original 36-phase native
matrix and original successful aggregate. No accepted kit fixture was fabricated.
No new SH6 run or SH7/SH8 proof acceptance is claimed.

`frozen-source.json` records the ten exact implementation/test/document files
on Trisha parent `13c5c24b93d7136624d8725f911b2aa45a175129` plus the uncommitted
change. `final-gates-2.json` records all nine commands, exit codes, log hashes,
timestamps, Joy identity and unchanged start/end source identities. It is the
final gate receipt; earlier logs remain historical.

The final normal Python run passed 18 distinct kit guards. Optimized Python
repeated those same 18. Existing archive (2), snapshot (1), source verification
(10), binary-package routing (4), and baseline-checker (11) suites also passed:
46 distinct tests total. Warnings are errors. The packaging fixture explicitly
replaces only the kit subprocess with a routing double; it never constructs an
accepted compiler kit. A removed source-string test explains the historical
19-case log, which is not the final count.

The real rehearsal uses historical native C2
`76a07c08265bd2ef525164472b6b53ac3f0e6cbbedce3250c4202f40ffba34c8`
and the exact three Trident CLI-guide inputs. The final smoke uses the actual
Rust 1.89 coordinated candidate Joy built from the separate source archive,
SHA256 `6e4be9bc27bc090dc2bc040dca3f3c8ad84aea6555825aac1eb06990bfe93b0a`.
It checks all94 compiler sources against that candidate's actual archived
Trident tree. `final2-candidate-smoke пробел/` retains the five commands and
outputs: pack JOB1, guest compile, execute canonical atom13, pack invalid source,
reject it with `--force` while preserving the existing output. No Joy build,
host compiler, or seed fallback occurs in those commands. Source options and
resource limits are the unchanged guide manifest.

The first `smoke пробел-1/` attempt failed in the Python helper after the actual
guest correctly rejected invalid source: the draft incorrectly tried to parse
the empty stdout as JSON. Joy writes that diagnostic to stderr. Its failed
receipt, five raw command logs and preserved output are retained. Later runs
check the real stderr diagnostic, empty stdout, exit1 and unchanged output.

The pinned final36 authority remains Trident commit
`8576570d745139b733bb7dec090035dca938abe1`, validator SHA256
`72cd11ec62e410e908590a785c79011989ea2c6c32872c5db31d72a62947c0ec`.
It is not invoked against invented success inputs. Production packaging rejects
the retained rehearsal archive. The native candidate and unpacked-package
accepted-kit path still need the actual accepted archive and native release
run; the local rehearsal is supplementary distribution evidence.

## Retained bytes and commands

`raw-evidence.tar.gz` retains all165 original measurement files (72,622,640 raw
bytes), including earlier failures and gate scripts. Standard tar hardlinks
deduplicate identical raw payloads; `files.json` lists every original path,
length and SHA256. Each member was independently reread through `extractfile`
and compared with that manifest. `receipt.json` binds the archive and final
gate/source receipts. Raw log whitespace and newline bytes are unchanged.

Extract into a fresh directory. `final-gates-2.py` contains exact local commands;
the portable focused form is:

```sh
python3 -B -W error scripts/test_selfhost_kit.py \
  --rehearsal RETAINED/rehearsal-1/kit --trident VERIFIED_SOURCE/trident \
  --joy ABSOLUTE_INSTALLED_JOY -v
python3 -B -O -W error scripts/test_selfhost_kit.py \
  --rehearsal RETAINED/rehearsal-1/kit --trident VERIFIED_SOURCE/trident \
  --joy ABSOLUTE_INSTALLED_JOY -v
```

The final gate also runs each of `test_archive_source.py`,
`test_snapshot_source.py`, `test_verify_source.py`, `test_package_binaries.py`,
and `test_check_baselines.py` with `python3 -B -W error ... -v`, then the direct
`selfhost-kit.py smoke --rehearsal` command and `git diff --check`.
No Rust/runtime/compiler source changed in this delivery.

## Post-commit installation

Code commit `a0996b2a180eaf6f1c70c4a4a43fa25a0f2e1360` matches every captured
source blob. The required post-commit Trisha install used a new detached
`portable-native-smoke/trisha-kit-install` worktree, verified vendor patcher,
Rust1.89, one build job and a fresh target/install prefix. Cargo metadata bound
all36 local package manifests to the clean family; all8 resolved Git repositories
remained clean at identical revisions before/after. `postinstall.json` records
exact commands and the installed binary SHA256
`3239ab444013b41a5f2d4dc995cda880acfd2e136c5ad9138ea57b2ffe52a5fd`.

The first install emitted Cargo's install-directory PATH advisory, with zero
Rust compiler warnings. It is retained unchanged. Repeating with the owned
install directory explicitly on PATH completed without warnings and produced
identical binary bytes. `postinstall/` retains every command log, full Cargo
metadata and both receipts as gzip files with raw/compressed hashes. This is a
local installation check; it adds no native platform or proof acceptance.
`independent-review/` retains the root review's guards and full raw-archive
verification. Formatting `files.json` to one record per line changed no values
or raw archive bytes; `receipt.json` binds its final identity.
