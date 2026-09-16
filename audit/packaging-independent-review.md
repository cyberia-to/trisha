# Independent source packaging review

Scope: `scripts/snapshot-source.py`, `archive-source.py`, `package-source.nu`,
`build-candidate.nu`, `smoke-release.nu`, and the fixture manifest/lock/helper.
Read-only code review; no additional proof or live-network execution. Current
source tree inspected: `/tmp/cyber-release-source-v7-20260912`. Parent-provided
byte-identical repacking and platform build receipts are separate evidence, not
independently rerun here.

## Concrete reproducibility finding

The original source bootstrap did not authenticate its upstream vendor inputs.
`package-source.nu` runs `patches/apply.nu`; its `fetch_crate` selects the first
matching unpacked directory under Cargo registry sources. A cache hit is copied
without checksum verification. A miss downloads/extracts the CDN archive without
checking a pinned digest. `patches/tasm.nu` has the same behavior for tasm-lib
and tasm-object-derive. A changed cached Rust file outside a patch anchor is
therefore accepted into the release vendor tree under the same declared version.

`vendor-sources.json` records the resulting bytes after the fact; it cannot
establish that those bytes derive from the intended upstream release. Repacking
one completed tree byte-identically tests archive determinism, not independent
bootstrap reproducibility. Reported to the owner. The concrete closure is to
pin upstream crate archive SHA256 values and verify the archives before isolated
extraction/patching, rather than trusting mutable unpacked cache directories.
This is a bootstrap provenance gate, not evidence that the current vendor code
has actually been altered maliciously.

**Resolved by the owner and independently reviewed:** `patches/fetch.py` now
verifies pinned crate archive SHA256 before extraction, including the direct
install API boundary. Cached unpacked source directories are never consulted.
Both bootstrap scripts invoke this helper and propagate failure. Extraction
uses isolated staging, accepts only regular files/directories under the exact
crate prefix, rejects traversal/duplicate files, and preserves the existing
installation until validation/extraction succeeds.

Independent validation: all **8/8 pins** match the pinned Neptune oracle
Cargo.lock, and **2/2 fetch regressions** passed locally. The owner full bootstrap
and empty-CARGO_HOME bootstrap logs show all pinned downloads/patches succeeded.
The reviewed `/tmp/trisha-pinned-bootstrap-diff.json` records only removal of
`twenty-first/.cargo-ok`; no Rust, manifest or other source bytes changed. Thus
this fix closes the identified mutable-cache provenance gap without changing
the compiled vendor source. A fresh source archive must include the new helper
and pin manifest; older archives do not gain this corrected bootstrap script.

## Confirmed behavior

- Dependency discovery uses both Trisha and Joy all-feature locked Cargo
  metadata, collecting local package repositories. The inspected snapshot has
  ten repositories: bbg, hemera, honeycrisp, joy, lens, nox, strata, trident,
  trisha and zheng. All are explicitly marked working-tree snapshots.
- Snapshot mode includes dirty tracked and ordinary untracked source files and
  records each copied file/link identity. Build outputs and caches are excluded;
  `src/config/target` is preserved by the contextual target-directory rule.
  Required compiler/backend/resource paths are checked before packaging.
- The current tree contains eight symlinks, all resolving within the source
  closure. No actual symlink escape was found. The scripts preserve symlinks;
  they are not a general rejection policy for future externally pointing links.
- Archive creation uses sorted paths, fixed root name, normalized timestamp,
  owner and mode, an empty gzip filename, and disables hardlink-layout reuse.
  It rejects non-file/directory/symlink entries and refuses to overwrite output.
- Candidate builds use a fresh prefix/target directory, locked manifests, and
  enforce the expected Triton family version7.0.0. Local dependency manifest
  paths must lie under the archive tree. All three newly built binaries are
  copied into the same prefix and hashed. Build failure or Rust warnings abort.
- The fixture helper is a separate locked workspace linked to the archived
  BBG0.3 implementation, not a stale hand-written root. It generates current
  public certificates with distinct77/88 energy values and a complete public
  table for the private-query case. Its build runs offline after product builds.
- Smoke changes into a fresh work directory, sets PATH to only the candidate
  bin directory, and clears compiler library/target-package overrides. Compiler
  delegation therefore discovers the colocated installed warriors. Runtime
  module/state resources must work outside their source checkout.
- Smoke requires real command exit codes and explicit output assertions. It
  checks API2/schema1, Triton5-word digest/backend-v7 capabilities, package
  extensions, project target dispatch, state descriptions, and actual run/prove/
  verify flows. Tamper replacements are checked to have changed the input.
- Installed recursive execution includes a genuine outer proof, expected inner
  claim binding and forged commitment/output rejection. This is a heavy test;
  merely building a candidate does not run it or count it as passed.
- Joy public/private/state smoke requires JOYEXEC2/JOYZK003/JOYST001 respectively,
  checks exact outputs, and rejects wrong public input/result/state. Private
  state uses a bounded complete public table; sparse private state is rejected.
- Installed test-runner smoke asserts an exact pass/skip count and checks a
  failing release-profile test. The final PASS print is reached only after all
  commands/assertions, with no ignored command failures observed in the script.

## Limits of the receipts

The archive is a complete local sibling-source distribution with patched Triton
sources, not a complete offline vendor mirror of every registry/git dependency.
Normal locked product builds may fetch those dependencies. It is not evidence
of individual registry crate publication compatibility.

`candidate.json` hashes binaries and the provenance document; build-candidate
checks that the document exists but does not revalidate every source/vendor
inventory entry. Thus that receipt alone does not detect edits made after a
snapshot. The externally checked archive digest and disciplined extraction/build
workflow remain necessary for a same-archive claim. Similarly, the smoke script
checks the binaries supplied to it but does not itself compare them with a
candidate receipt or authenticate the archive digest.

The script's final text correctly separates offline inspection from Neptune
transaction validation and live deployment. No live admission, GPU execution,
formal whole-library proof, or unsupported platform result follows from smoke.
No stale Joy format acceptance or falsely unconditional smoke PASS was found.
