# Coordinated local candidates

The coordinated candidate uses Trident 0.4, Trisha 0.3 and Joy 0.5. Installed
warriors must expose compiler API 3 with target schema 1; API 1 and 2 packages are
rejected. These are source-candidate versions, not a registry publication claim.

Windows is also required for the release. The native CPU matrix and
acceptance gates are in [release platforms](../docs/reference/release-platforms.md).
The scripts support native Windows executable names, staging, configuration
paths, process accounting and ZIP archives. Actual completion is recorded in
[the native release audit](../audit/native-release-20260916.md).


`package-source.nu <new-directory>` collects the locked Cargo dependency closure
of both Trisha and Joy, including Trident. The strict default requires committed
source inputs and the Trident/Trisha/Joy root lockfiles. It archives repository
commits and regenerates the pinned vendor sources from the archived patch script.

`package-source.nu <new-directory> --snapshot-worktrees` creates an explicitly
marked local candidate from current sources, including uncommitted dependency
inputs. It does not commit, stash, revert, or otherwise change those repositories.
`sources.json` records each HEAD, dirty status, and SHA-256 of every copied file;
`vendor-sources.json` records the patched dependency files. Git-ignored files,
build output, VCS directories and caches are excluded. Strict mode checks every
tracked or unignored source change, including deletions, assembly, Metal kernels,
patches and documentation; it uses no filename-extension allowlist. Root
workspace lockfiles govern builds. Regenerate the snapshot after any source change.
Strict committed archives also carry complete per-file inventories.

Both modes produce a `.tar.gz` and its SHA-256. The archive uses the fixed
`cyber-source/` prefix, sorted entries, normalized ownership/permissions and
the newest included commit timestamp; gzip stores no filename or current time.
Unchanged source/provenance bytes therefore produce identical archive bytes.
The vendor bootstrap transcript remains beside the archive as a separate log,
because its machine paths are not reproducible source inputs.
The archive includes `BUILD.txt`
with commands to build/install Trident, Trisha and Joy. Nushell, Python 3.11 or newer, Git,
Cargo and tar are required. Snapshot metadata validates provenance; it does not
claim that every experimental backend or network protocol is implemented.

`smoke-release.nu <installed-bin-directory> <new-work-directory>` exercises all
four installed binaries with only that binary directory on PATH. It requires
the adjacent `candidate.json` from the builder and checks the binary hashes
before and after the suite. It checks LSP initialize/shutdown/exit and
target/package discovery, project target precedence, Neptune state descriptions,
artifact extensions, CPU Triton proofs and tamper rejection, public/private Zheng execution certificates, authenticated public state,
claim rejection, a compiled Triton recursive outer STARK with a file witness,
Joy build identity/overwrite protection, verified offline
Neptune program inspection, and rejection of the retired Neptune proof alias
and deployment without transaction intent.
Run this against freshly installed coordinated binaries.
Only after every check passes does it create `smoke.json`, binding the result
to those exact binaries, source provenance and observed host platform. Build
and smoke bind the exact `source-verification.json` SHA-256, including its
vendor inventory digest. Smoke also binds its own script bytes before/after
execution; binary packaging ships that same script from the verified archive.

`package-binaries.nu <candidate-prefix> <new-archive.tar.gz> --smoke <smoke.json>`
packages the installed binaries after checking both build and full smoke
receipts. It creates a deterministic `cyber-tools/` archive with the binaries,
licenses, validation receipts and the exact installed-smoke fixture bytes.
Use `.zip` for native Windows packages. Candidate and smoke schema2 bind
`trident`, `trident-lsp`, `trisha`, `joy` and the LSP protocol helper.
It revalidates the source/vendor tree against the saved build verification;
changed source files or verification receipts reject.
Artifact creation is
local; publication remains a separate operation. This archive does not certify
live node admission or broader unsupported language/protocol features.

`python3 -B scripts/test_snapshot_source.py` checks snapshot fidelity, complete
dirty-source detection and unchanged worktrees. `python3 -B scripts/test_archive_source.py`
checks deterministic archive bytes, metadata, links and executable preservation.
`python3 -B scripts/test_verify_source.py` checks complete pre/post source
verification and failed-build cleanup. `python3 -B scripts/test_package_binaries.py`
checks changed inputs, staging failures, receipt binding and deterministic
packaging with synthetic fixtures.

## Build and inspect outside the checkouts

The source closure currently includes BBG, Hemera, Honeycrisp, Joy, Lens,
Neuron (the dependency-free neuron-id crate), nox, Strata, Trident, Trisha and
Zheng. Cargo metadata determines the closure rather
than a fixed repository list. Joy now depends on Trisha's Triton prover and its
workspace patches resolve to `../trisha/.vendor`; keep these sibling directories
in the archive. `package-source.nu` regenerates all eight pinned vendor crates
inside the archive using `patches/apply.nu`, including warning fixes, and records
the resulting files. Bootstrap verifies each upstream `.crate` against the
reviewed SHA-256 in `patches/upstream.json` before extraction and patching.
Mutable unpacked Cargo cache directories are never source inputs. The builder
rejects any local dependency outside the archive.

```nu
nu scripts/package-source.nu /tmp/source-candidate --snapshot-worktrees
nu scripts/build-candidate.nu /tmp/source-candidate /tmp/installed-candidate
nu scripts/smoke-release.nu /tmp/installed-candidate/bin /tmp/smoke-candidate
```

`build-candidate.nu` uses the three root lockfiles, builds the CPU binaries,
requires the coordinated Triton/tasm-lib7.0.0 dependency set, rejects compiler
warnings, and installs them into one local `bin` directory. It checks every
recorded source/vendor byte, file kind and symlink target before Cargo and after
compilation. Source changes or manifest rewriting during the build reject.
Only a completed build moves its private staging directory into the final
prefix. Existing destinations, including dangling links, and destinations
inside the source tree reject before compilation. The builder also generates
public BBG state certificates from the archived implementation
under `share/trisha-release-smoke`; the smoke script can select another fixture
directory with `--fixtures`. The fixture helper has its own archived manifest
and lockfile in `scripts/fixtures/`; it runs with `--locked --offline`, so its
dependency resolution cannot drift with the local Cargo cache. Build logs, source provenance and binary hashes
remain in the candidate prefix. This creates a reviewable local candidate and
performs no upload, tagging or publication.

The smoke checks unchanged sources with helper calls through the public
`JOYEXEC2`, private `JOYZK003` and authenticated public-state `JOYST001` paths.
Private state queries use all ten bounded public dimension tables. Verifiers
run in fresh processes without witness arguments, reject changed claims/inputs
and state roots, and reject incomplete private-state certificates. An installed
`trident test --target triton` executes imported helpers with the actual Triton
runner and checks failed assertions and skipped cfg tests.

The recursive smoke uses the native program hash computed from source inspection
and explicit expected public I/O to construct the inner claim. Both Trident and
Trisha run the SDK from its private witness file, then Trident delegates a real
outer proof and a fresh verifier checks it. Changed inner commitments and outer
public outputs must fail. This step needs substantial CPU memory; the script
defaults Rayon to four threads unless explicitly configured by its caller.

Public state certificates disclose their tables. Private queries hide the
selected coordinates and private inputs, within the current table/gate bounds;
they do not hide the database. The production `vm.triton.proof` SDK verifies
official Triton proofs. The retired `os.neptune.proof` alias and deployment without explicit transaction
intent remain negative checks. Production fixed Neptune policies are distinct
from that retired alias. No smoke result certifies
unimplemented network protocols or experimental backends.

A snapshot taken during implementation is only a build rehearsal. Regenerate
and rebuild after all changes stabilize; record that final candidate's hashes
and smoke output before deciding whether to publish.

The expensive outer recursive STARK test is an explicit release gate, separate
from ordinary tests. Run it sequentially with full benchmark proofs to bound
memory use; it must actually pass before recording recursive proof readiness:

```sh
RAYON_NUM_THREADS=4 cargo test -p trisha-rs --release --locked --test recursive_witness outer_proof_binds_compiled_recursive_sdk_to_public_claim -- --ignored --nocapture
RAYON_NUM_THREADS=4 cargo run --release --locked -p trisha -- bench baselines/triton --full
```

`TVM_LDE_TRACE=no_cache` selects the upstream prover's supported time/memory
tradeoff when a machine cannot cache the extended trace. It preserves the
claim and security parameters. Record the setting with timing/RSS evidence.

The production Neptune adapter pins its upstream consensus and RPC Git revision
in the Trisha root lockfile. A source archive contains all local workspace and
patched Triton sources; Cargo still needs access to locked registry/Git sources
not already cached. This is not a fully offline dependency vendor archive.

The optional Neptune protocol fixture oracle is a separate Cargo workspace under
`tools/neptune-policy-oracle`, with its own lockfile and exact upstream Git
revision. Regenerating its fixtures requires those Git and registry dependencies
to be available to Cargo. The source archive carries the oracle sources/lock,
not a claim of an offline vendor cache for every upstream test dependency.

The full baseline proof gate can be run against an archive-built candidate:

```sh
python3 cyber-source/trisha/scripts/check-baselines.py /tmp/candidate /tmp/baseline-proof-gate
```

The checker disables Python bytecode writes before importing its archived source
verifier. The default command above therefore leaves the exact source inventory
unchanged; it does not require `-B` or `PYTHONDONTWRITEBYTECODE`.

It verifies complete source/vendor inventories and all installed binary hashes
before and after the real `bench --full` run, records fixture/baseline identities
and hashes the completed log. It requires all43 baselines,99 positive fixtures
and34 rejection vectors. Every positive fixture requires its classic/hand
`TRISHA_PROOF_VERIFIED` events, emitted after actual verification and matching
the expected native program and public claim. Execution-only PASS rows cannot
count as proofs; only a complete passing run records198 new verified proofs.
The checker uses4 prover threads, a40GiB process-group RSS guard and
pressure/available-memory guards. A stopped or failed run remains incomplete.
This can take substantially longer than the installed smoke; it does not turn
older proof logs into retrospectively bound input inventories.

`verify-corpus.py <completed-smoke-directory> --seal` binds the full proof
corpus and expected claims. Run it on each native producer, then use
`--candidate <unpacked-prefix> --receipt <new-json>` on every native consumer.
The 47 checks cover 18 accepted proofs and 29 changed-claim/input/state or
corrupted-artifact rejections. Producer and consumer must share the same source
inventory. Authenticate each corpus archive SHA-256 before extraction.

`native-candidate.py` is the CI bootstrap. Its selector pins a source release
asset and SHA-256; Rust1.89.0, Nushell0.112.2 and Z3 4.15.3 are pinned too.
The bootstrap runs CPU workspace suites, installed proofs, deterministic
packaging, unpacked LSP and complete baseline proofs. A separate `verify` phase
consumes authenticated binary/corpus archives for the cross-platform matrix.
GitHub credentials are removed before archived implementations execute.
