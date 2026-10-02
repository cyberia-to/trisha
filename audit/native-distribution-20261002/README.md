# Native 0.4 distribution rehearsal — 2026-10-02

Status: source and accepted-kit guards passed; native distribution jobs pending.
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
host. The four binaries advertise Mach-O `minos 11.0` and SDK 26.4; their
observed runtime libraries are system libraries. Original raw command streams
and the candidate inventory are retained. `binding.json` records the unchanged
four installed hashes after inspection. These link values do not replace
execution on macOS 14.

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
