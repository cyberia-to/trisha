# Six native public-proof profile receipts — 2026-10-02

All six actual native jobs passed in
[run 36958147193](https://github.com/cyberia-to/trisha/actions/runs/36958147193),
completed at 03:15:08 UTC. Tested workflow/driver commit:
`2b7017f89a495eb43c0feca6818eb68f35c21a02`. These results supersede the local-only
status in the preparation receipt one directory above.

The selector at that commit pins twelve exact origin inputs, including Joy
`6e0ec4d8440e2521df08f442d64f54e667044716`, Zheng
`0d7ba6d422d9b825f9685e903e55252f88ebecd9`, Nox
`2f09ca3c3f18ae470365310cca8db5208eda75c6` and Trident
`da0d1a59cd8208fab96f219ccedef29122d5221a`. Each job independently fetched them
and selected actual native Rust/Cargo 1.89.0 executables. This is branch
validation of the public proof profile, not a release distribution or SH7/SH8
whole-compiler acceptance receipt.

## Observed gates

| Native target | Joy passed | Existing ignored | Native Joy bytes |
| --- | ---: | ---: | ---: |
| macOS ARM64 | 215 | 1 | 5,635,792 |
| macOS x64 | 215 | 1 | 6,127,240 |
| Linux ARM64 | 216 | 1 | 6,276,200 |
| Linux x64 | 216 | 1 | 6,645,672 |
| Windows ARM64 | 209 | 1 | 4,946,432 |
| Windows x64 | 209 | 1 | 5,912,576 |

Every platform also passed 40 Zheng disclosed tests and 4 real-allocation tests
in both default and all-feature configurations, plus 21 Nox observer v1/v2
tests. All all-target checks, the Joy foreign-backend boundary and captured
compiler/Cargo warning checks passed. No required command failed or emitted a
warning. Exact commands, UTC timestamps and raw outputs remain in each receipt.
Counts above come from those commands at the exact selector revisions.

Joy's fresh-process `prove-artifact` / `verify-artifact` cases, compiler JOB1/RES1
binding and failed-publication checks ran everywhere. Four required CLI names
ran on POSIX; the three portable names ran on Windows. Platform-conditioned
tests explain the complete workspace count differences. Each job's actually
passing names, host metadata, native tool executable SHA-256 values and Joy
binary SHA-256 are retained in `summary.json.gz` and the original receipts.

## Independent evidence checks

All six downloaded artifacts were checked against the committed selector and
bootstrap source: unique command names, every raw command log's byte length and
SHA-256, successful required tests, native compiler version/host, unchanged
before/after inventories, twelve exact origin heads, clean source status and
the actual downloaded binary's bytes/hash. The parsed source inventory entries
including every source-file SHA-256 are identical on all six platforms.
The sorted compact JSON encoding of that common inventory has SHA-256
`a9aa5c583177345df79bd78b79dc06c56be3dc439e440c49ead86e32d597fa52`.

The Windows Actions bootstrap checkout used its default CRLF conversion.
Every recorded Windows selector/driver/helper/workflow hash was verified as
exactly the committed LF bytes transformed to CRLF; no other byte change is
accepted. The four POSIX bootstrap hashes match committed bytes directly.
The twelve build-input repositories independently disable line-ending
conversion, so their source-file hashes agree everywhere. Windows also writes
receipt JSON with CRLF; original raw JSON hashes are preserved, and parsed
inventory equality is checked separately from serialization.

The independent verification command was:

```sh
python3 -B audit/native-proof-profile/verify_hosted.py ../hosted-proof-evidence/artifacts
```

Its successful JSON output is stored in `summary.json.gz`. Each artifact was
downloaded with `gh run download 36958147193 --name native-proof-<target> --dir
../hosted-proof-evidence/artifacts/native-proof-<target>`. `run.json.gz` preserves
`gh run view 36958147193 --json databaseId,status,conclusion,headSha,url,createdAt,updatedAt,jobs`.
`artifacts.json.gz` preserves `gh api repos/cyberia-to/trisha/actions/runs/36958147193/artifacts`.

## Durable retention

`evidence.tar.gz` preserves 2,070 log/receipt/inventory/metadata files from the
2,076 downloaded files. The six native binaries remain in the original Actions
artifacts (30-day retention) and local downloads; their exact bytes/hashes were
checked before retention and their hashes remain in this audit. They are not
duplicated in Git. `retention.json.gz` lists every downloaded file's size,
SHA-256 and exact retention disposition, including those six explicit omissions.

Identical retained bytes use ordinary TAR hard links to earlier entries. Every
retained entry was read back through the archive and compared with its original
length/hash. Archive SHA-256:
`073d7068c388ead0c881c473749e194cea385830288584ffc121d7ee9d3e4f03`.
The archive is 4,282,860 bytes. It was generated and verified with:

```sh
python3 -B audit/native-proof-profile/archive_hosted.py ../hosted-proof-evidence/artifacts audit/native-proof-profile/hosted-36958147193/evidence.tar.gz audit/native-proof-profile/hosted-36958147193/retention.json.gz
```

`archive.stdout` retains its successful result. `source.json` records the audit
helper and retained artifact hashes. Extracting `evidence.tar.gz` in an empty
directory restores the original retained file paths below `hosted/`.

The older frozen distribution rehearsal retains separate inputs and gates.
These six native results introduce no privacy, succinctness, physical LIM1/GC
attestation or full-compiler capacity claim.
