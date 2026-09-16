# Native release preparation — 2026-09-16

Release execution is authorized. This is an active validation record, not a
completed-release claim. The new Windows requirement is included; general nox
expansion remains outside the release blockers.

## Tooling and native fixes

- Native executable suffixes, portable Windows staging and dependency path
  containment; ZIP binary archives with deterministic metadata.
- Existing `trident-lsp` is now included and exercised through actual stdio
  initialize/shutdown/exit. Candidate/installed-smoke schema2 binds all four
  binaries and both smoke scripts; schema1 cannot certify the new inventory.
- Windows APPDATA/USERPROFILE configuration paths, with explicit override;
  existing macOS path and Linux XDG/HOME selection are tested without mutating
  process-global environment. Three Rust tests pass.
- Source/link inventories use canonical POSIX separators on Windows too;
  content, file kind and in-archive target resolution remain checked.
- Native Windows Job Objects account resident memory and clean up owned
  descendant processes. Two actual process tests pass on Windows x64 and ARM64
  in run35106273708. No native Windows product build pass is yet recorded here.
- Local Python tooling:26 passed,2 Windows-only skipped; actual installed LSP
  protocol also passes. Logs: `/tmp/cyber-release-portable-tooling-v3.log` and
  `/tmp/cyber-release-platform-paths.log`.

## Frozen development candidates

The draft release `candidate-20260916.1` in `cyberia-to/trisha` holds immutable
named source assets for CI. Draft release ID389977897. These are explicit
working-tree snapshots, not final committed source archives.

| Source archive | SHA-256 | Draft asset ID |
|---|---|---|
| cyber-release-native-20260916-01.tar.gz | c608b2fabae54c84acc81ac900070745b7b401626162921ed9a7b550bb989bb0 | 568084455 |
| cyber-release-native-20260916-02.tar.gz | 5dcda6975ddec1c7b423655c8e2a94fb06561b8cbb9e53f1059e5c8a2393b947 | 568096294 |
| cyber-release-native-20260916-03.tar.gz | 27cda35f4754ec80205b46d9f61d5c7bb54bd7580a5e9e49f3bcfe1cdabf17a4 | 568106678 |

Source01 has a native macOS ARM64 Rust1.89 build and completed installed v2
smoke, including the recursive outer proof, public/private/state Joy paths,
typed inputs, RAM preservation and tamper rejection. Source and binaries are
under `/tmp/cyber-release-native-macos-arm64-01`; smoke is
`/tmp/cyber-native-smoke-01 пробел/smoke.json`. Build/smoke logs:
`/tmp/cyber-release-native-macos-{build,smoke}-01.log`.
Its binary archive SHA-256 is
`2e4e6e211d79d39286e8342e150909962a610a8cc35ec3e2d5a986593907172f`;
two independent packager invocations produce identical archive bytes.

Source02 has a new native Linux ARM64 Rust1.89 build in the isolated Lima guest:
`/home/master.guest/release-validation/native02/candidate`. Log:
`/tmp/cyber-release-native-linux-arm64-02.log`. Installed smoke is pending.
These two platforms currently refer to different complete source inventories;
they must converge on the final committed candidate before publication.

## Remote validation and observed failures

Automation is on `release/native-20260916`, with an isolated local worktree
`/tmp/cyber-release-workflow-20260916`; the user's product branches are preserved.
The selector identifies the exact draft asset/digest. Archive code receives no
GitHub token; Rust1.89 and Nushell0.112.2 are pinned, including Nushell asset hashes.

- Run35105501816: unpublished draft asset download rejected with403. Resolved
  by granting the bootstrap the draft-download permission and removing its token
  from the environment before compiling or executing archived code.
- Run35105658825: source01. Windows x64 detected link spelling mismatch after
  native extraction; ARM Python3.13.7 installation failed in the hosted image.
  Fixed canonical relative link spelling and pinned cached Python3.13.15.
- Run35106273708: source02. Both Windows process suites pass, then native
  Nushell rejects a full-path mktemp template. Fixed directory/template argument
  separation. Linux and Intel Mac jobs were still active at this checkpoint.
- Run35106910222: source03, focused Windows x64/ARM64 jobs active at checkpoint.

No failed gate is reclassified as a pass. Subsequent runs and final exact source
and binary identities must be recorded before final release publication.

## Fresh node admission and corpus verification

Fresh Neptune SingleProof generation/verification completed in541.932 seconds,
with24,101,502,976 bytes peak observed process-tree RSS and no guard stop.
The pinned0.15.1 node accepted the exact kernel into its mempool through the
new Linux ARM64 Trisha binary. Altered kernel and incorrect credentials reject;
loopback-only namespace, no wallet funds or public network. Receipts are
`/tmp/cyber-release-neptune-20260916/{receipt,admission}.json`.

Mac ARM64's sealed corpus passes47 actual verifier checks locally (18 accepted
proofs,29 rejection checks). Cross-platform execution remains separate.

Run35106273708 Linux x64/ARM64 builds succeeded; workspace suites then detected
missing Z3 in the runner PATH. The bootstrap now supplies hash-pinned native
Z3 4.15.3 instead of dropping the17 formal CLI tests.

## Committed source and workload allocation

All11 source repositories are frozen on `chore/coordinated-release-20260916`;
working directories remain unchanged. Product draft PRs: Trident47, Trisha7,
Joy2. RC1 source archive SHA-256 is
`b333304b9e61ffd3277b6fe9ae9fbb1a3990c5b4a25c2124cb04322bd061593b`.
It is superseded for publication by the next lockfile correction.

Trisha's lockfile now selects rustls-webpki0.103.15 and rand0.9.5, consistent
with the corrected versions already selected by its companion workspaces.
GitHub's high gix-fs and low lru alerts refer to optional Burn training
dependencies; neither package is in the default CPU Trisha dependency graph.
The CPU release does not certify the optional training dependency closure.

Native acceptance runs all133 execution fixtures on every target and produces
the installed smoke's fresh proofs on every target. The full198-proof baseline
gate runs on the48GiB dedicated Mac worker against the same committed source.
This preserves complete proof coverage while accounting separately for native
execution coverage and proof-worker capacity (hosted workers have14–16GiB).
The proof-corpus matrix verifies every native producer on every native consumer.
The full gate remains mandatory; execution rows are never counted as proofs.

## Windows native build and test corrections

Source03 Windows ARM64 compiled all four release binaries with Rust1.89 and
zero warnings in run35106910222. The native workspace then found the census
test comparing Windows separators against POSIX names. The test now compares
path components; the production Z3 locator also searches native PATH directly
instead of depending on Unix `which`. Local differential9 and formal17 tests
pass after this correction, plus the native-path unit test. Windows rerun is
required. Baseline proof accounting likewise canonicalizes Rust's Windows
extended-length names and Python's drive paths before matching fixture events.
