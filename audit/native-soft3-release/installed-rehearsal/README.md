# Third installed rehearsal: retained evidence

The completed local installed rehearsal passed on macOS aarch64 with actual
Rust 1.89 and committed Trisha `13c5c24b93d7136624d8725f911b2aa45a175129`.
The eleven exact source revisions are in `receipt.json`. Its original
`prepare.json`, `build.json` and `smoke.json` retain every command, environment,
exit status, raw stdout/stderr identity and source/binary binding.

This receipt covers the installed scope described in [the audit](../README.md)
after the [import visibility correction](../import-visibility/README.md).
CPU suites and the 198-proof gate were still running when this archive was
prepared. Their mutable files are excluded, and this receipt makes no claim
about them, SH6, other platforms or release acceptance. Selfhost kit acceptance
also remains separate.

`installed-evidence.tar.gz` contains 570 exact ordinary files totaling
75,967,071 raw bytes. The archive is 44,749,500 bytes, below the declared
50,000,000 byte compressed ceiling, with SHA256:

`90df5f7bab58980a316fe0b3c5df314e682079ac099930e55b4523f236bb9875`.

The retained original evidence includes:

- The complete sealed 47-case corpus: 18 accepted and 29 rejection cases, its 69
  payload files plus manifest and original verification receipt. Public,
  private `JOYZH001`, state, typed and tampered artifacts remain byte-exact.
- All 49 original Joy native smoke command records, stdout/stderr files and 22
  work files, with the actual public/private/state artifact bytes and fixtures.
- The full installed smoke, 28 process/file probes, 133 baseline executions
  (99 positive, 34 rejected; 43 baselines; no baseline proofs generated), and
  all 266 immutable baseline input files. The process/file probes used local
  mocks; this does not establish live Neptune behavior.
- Original source inventories, candidate metadata, four warning-free build
  logs, tool versions, measurement drivers, exact committed source scripts,
  deterministic package/repackage receipts and the unpacked LSP check.
- The independent review and both earlier drafts, including the failed first
  reviewer assumption about the location of one benchmark fixture. The
  corrected final review passed; the original failure was not removed.

All counts above come from the commands in retained
`rehearsal/{prepare,build,smoke}.json` and the source-bound independent
`independent-review/review.json`. Retention ran no builds or proofs. The
previous independent review checked 3917 source file/link entries against the
eleven Git revisions and checked the complete original archives. Its final
read-only source guard and all original outcomes remain retained.

`files-00.json` through `files-02.json` list every archive path, original absolute
path, exact length and SHA256. Raw JSON, logs and original path strings were
preserved. Every member was compared directly with its original bytes; every
original was rehashed after archival. A second deterministic encoding produced
the same archive identity. Gzip and tar timestamps are zero, tar owners are
empty/zero, and archived modes are normalized to 0644; mode preservation is not
claimed.

`external-files.json` records local paths, byte lengths and SHA256 for the
114,339,704 byte complete source archive, four executables in both installed
locations, original binary/repacked/proof archive containers, Rust tools and
Z3. These large bytes remain outside this retention. The original proof archive
container is external because its entire 70-file raw tree is retained here.
Build target directories are omitted. For Rust and Z3, the tool identities are
bound by the original receipts and rechecked; Nushell/Python/rustup hashes were
first recorded during retention, while original paths and versions are retained.

From this directory, the exact archival command was:

```sh
python3 -B -W error retain.py > retain.stdout 2> retain.stderr
```

The driver is a fresh-output archival operation, not an in-place refresh.
To verify the retained archive independently of its original location:

```sh
python3 -B -W error verify-retention.py
```

When the recorded local inputs still exist, this additionally byte-compares
all 570 originals and rehashes all 19 external references:

```sh
python3 -B -W error verify-retention.py --originals --external
```

Extract the verified archive into a fresh directory to inspect the raw tree.
For a fresh cryptographic replay of the 47 sealed cases, supply the exact
externally recorded candidate executables under `rehearsal/candidate пробел/bin`
and invoke the retained `verify-corpus.py` with the extracted `smoke пробел`
directory, `--candidate` set to the extracted candidate directory and a fresh
`--receipt` path. The retained `joy/scripts/smoke-native.py` can run the 49-command
smoke with that exact Joy executable, the retained candidate fixtures and a
fresh `--output` directory. Such replays are new executions and must retain new
receipts. Original receipts are never rewritten to substitute restored paths.

The copied driver/reviewer scripts retain absolute original measurement paths;
their original invocations are provenance, not a claim of automatic relocation.
The relative archive manifests support byte verification after relocation.

`deterministic-replay.py` retains the exact additional inline driver passed to
`python3 -B -W error -`; its combined tool output and receipt confirm direct
comparison of every compressed byte as well. `verification.json` and the raw
verification outputs record the later original/external checks.
