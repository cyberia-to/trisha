# Source candidate rehearsal — 2026-09-12

This is a working-tree build rehearsal, before final coordinated commits. The
later test-only native TOML fixture correction, bootstrap checksum verification,
smoke target/profile corrections and audit/changelog updates require a
regenerated final source archive. No release has been tagged or published.

Source archive: `/tmp/cyber-release-source-v7-20260912.tar.gz`, SHA-256
`9bce1a685bc5568277f01865c505008c43e733e1d242611ca047a228f0ae1961`.
Its fixed prefix is `cyber-source/`. It carries 10 repositories, 2336 provenance
entries (2328 files and 8 symlinks), and regenerated pinned vendor sources.
`sources.json` SHA-256 is
`6837745f8669d541a559f3d502d5cac978afbd8832dda4548892aa4b0d2190fd`.

An independent second archive of the same source bytes is byte-identical.
The archive epoch is 1789203553, the newest included repository commit time.
Archive inputs remain unchanged during a reproducibility comparison; the
comparison uses Python `-B` to avoid generating import cache files.

The packager's Trisha+Joy metadata union contains 39 local packages. The
builder checks three roots, adding Trident's `trident-silicon` workspace member
for 40. Its files are already included in the complete Trident repository.
Native Linux and host metadata give exactly the same 40 name/version/path
tuples; this count difference is caused by the selected roots, not a platform
dependency drift. Every resolved local source remains inside the archive.

## macOS arm64 build

`build-candidate.nu` built Trident, Trisha and Joy from the extracted source
closure, with the three root lockfiles and no compiler warnings. The separately
locked public-state fixture helper also built and ran. The local prefix is
`/tmp/cyber-release-installed-v7-darwin`; full command log:
`/tmp/cyber-release-installed-v7-darwin.log`.

| Binary | SHA-256 |
|---|---|
| trident | `073cf89b9ad102a503ed89c46d7aac5a2490c44f97f2c6e42e61539e5e6341a3` |
| trisha | `fb1c0dd4de5a9b076542301a93914ab9e41c222781a4bd6579047314614bafae` |
| joy | `1931c793c4e868f9fb212e2e4a918a6ceafe0b25514dfadfa5b886e33da5b5ca` |

These exact binary hashes subsequently passed the complete installed smoke,
including actual recursive proving and public/private/state proof paths. The
[installed smoke receipt](installed-smoke-validation.md) records the corrected
harness, independent negative checks and measured resources. This does not
relabel the binaries as having been built from later source changes.

## Linux arm64

The same archive hash and all 2336 source entries were independently checked
inside the isolated Ubuntu guest. Its symlinks stay within the extracted tree;
there are no host checkout mounts. Locked metadata and pinned Triton/tasm-lib
7.0.0 checks pass for all three products. The native Rust 1.89 candidate build
passes in 7m26.49s with zero warnings and zero swaps; maximum RSS was
4910168 KiB. Installed runtime/proof gates are separate; see
[Linux runtime validation](linux-runtime-validation.md).

## Upstream bootstrap correction after this snapshot

Independent packaging review found that bootstrap trusted mutable unpacked
Cargo source directories. The new shared `patches/fetch.py` extracts only
checksum-verified `.crate` bytes against the eight pins in `upstream.json`.
Both cache-backed and empty-cache/CDN bootstrap pass and produce exactly
557 identical files. Comparison to the tested live vendor tree shows one
difference: the generated `twenty-first/.cargo-ok` cache marker is absent.
Every Rust, manifest and other source byte is identical, so the correction
does not change the verifier code behind the existing proof receipts.

Two boundary regressions pass; an independent review confirms all eight pins
against the separate upstream oracle lockfile. Logs:
`/tmp/trisha-pinned-bootstrap-check.log`,
`/tmp/trisha-pinned-bootstrap-empty-cache.log`; exact live-tree difference:
`/tmp/trisha-pinned-bootstrap-diff.json`. The final archive must contain this
bootstrap correction as well as the later test/doc changes.
