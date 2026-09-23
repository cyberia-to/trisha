# Candidate source provenance validation

The previous candidate builder hashed `sources.json` only after compilation.
It did not compare source bytes, symlink targets or patched vendor sources with
those manifests. A modified extracted archive could therefore produce a binary
whose receipt still named the unchanged provenance manifest. A failed fixture
build also left a partial final candidate prefix.

`scripts/verify-source.py` now verifies every recorded regular file and symlink
before Cargo runs and after all three binaries and fixtures finish. It checks
SHA256, byte length, file kind, missing and extra files, duplicate inventory
entries, canonical relative paths and special files. Symlinks must retain their
recorded target bytes and resolve to a file within the archive; absolute,
dangling, directory and escaping links fail closed. The vendor tree is verified
against its separate complete `vendor-sources.json` inventory. Repository roots
and the vendor root must be real directories.

Complete per-repository inventories are required for both committed and working
tree snapshots. Older committed archives without inventories are rejected.
`BUILD.txt` is documentary root metadata; its hash, both manifest hashes and the
verified file counts are retained in `source-verification.json`. The builder
compares the final receipt to the initial in-memory result as well as the saved
receipt, so rewriting an inventory during a build does not legitimize a change.
The final candidate receipt explicitly records `source_verified: true` and
`source_verification_sha256`, binding the exact saved verification receipt.

Builds use a private sibling staging directory and an external Cargo target
path. Only a completed, warning-free, source-verified build is moved into the
new final prefix. Build, fixture or verification failure removes staging and
leaves the final prefix absent; an existing final prefix is refused, including a dangling symlink. Destinations
inside the source tree (also through a symlinked parent) are rejected before
Cargo can create build artifacts or mutate the archived tree.

Nine focused tests passed with `python3 scripts/test_verify_source.py`. They
exercise actual file mutation/deletion/addition, vendor mutation, changed and
escaping symlink targets, changed source plus rewritten manifest, missing legacy
inventories, and real Nushell builder processes with a bounded stub Cargo.
The process tests cover fixture failure, mutation during compilation, cleanup,
successful publication with the exact receipt hash, and rejected dangling/inside-source
destinations. No compiler or proof
work is hidden behind these fixture tests.

This validates bytes against the supplied archive's manifests. It does not
independently authenticate a publisher: the source archive hash must be checked
through a trusted release channel. It does not attest registry/Git cache bytes
outside the archive, the installed Rust toolchain, system libraries or arbitrary
concurrent hostile processes. Cargo lockfiles pin those dependency identities;
this verifier's byte coverage is the recorded repository files and local vendor
tree. Empty directories are not file inventory entries. Previously completed
Darwin/Linux rehearsal builds retain their existing hashes and manual evidence;
these new checks are not retroactively claimed to have run during those builds.

Read-only verification of the actual extracted rehearsal archive
`/tmp/cyber-release-source-v7-20260912` also passed:2,336 repository files across
10 repositories and558 patched vendor files. No source or binary was changed.
Its source manifest SHA256 is
`6837745f8669d541a559f3d502d5cac978afbd8832dda4548892aa4b0d2190fd`;
vendor manifest SHA256 is
`0f75a41609baa5d5797b8d65976ac3b9eb9b950f3c1a63566f50e0a7a74338f1`.
The local verification receipt is
`/tmp/cyber-source-rehearsal-provenance-check.json`. This is a post-build
inventory check of that preserved tree, not a claim that its old builder ran
the new pre/post checks.


The FINAL2 Linux rehearsal exposed a Nushell portability error before Cargo:
the old staging code consulted `LAST_EXIT_CODE` after capturing `mktemp` output,
but that environment field is absent in clean Nu0.112.2. Staging now captures
`mktemp` with `complete` and reads that result's explicit exit code. Validation
occurs inside the cleanup handler, including a directory created by a failing
`mktemp`. The process suite now disables user config and removes inherited
`LAST_EXIT_CODE`; empty output, missing path, nonzero exit and created-directory
failure all leave no final prefix or staging residue. FINAL2 remains preserved
as a failed rehearsal; no frozen source tree was edited.
The same nine tests also passed under the actual isolated Linux Nu0.112.2
(1.193s, exit0), using a separate temporary script copy. Receipt:
`/tmp/cyber-final3-linux-builder-regression.log`. This did not modify FINAL2.
