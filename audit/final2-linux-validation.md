# FINAL2 native Linux validation

2026-09-12 status: source inventory verification passed; archived candidate
builder failed before Cargo. No release candidate or smoke receipt was produced.

## Exact input

Archive `/tmp/cyber-release-source-v7-20260912-final2.tar.gz`, 29,271,931 bytes,
SHA-256 `ce0aad90e0444450a9b3b876e257ff4cb2d838dd398b71cdcbbb45b364e09eba`.
Copied without host mounts into the isolated Lima ARM64 Ubuntu26.04 guest at
`/home/master.guest/release-validation/final2-20260912/source.tar.gz`, then
extracted into its sibling `cyber-source/` directory. Guest SHA matches.

The archived `verify-source.py` passed: 11 repositories, 2439 repository entries,
557 vendor entries. `sources.json` SHA-256
`0439006b0f2ad836f68d214d853df29b7205e861b322401c44e69d2571e878ae`;
`vendor-sources.json` SHA-256
`c80346aea2594e3a51a6ed3f2fc78f0421ebc25601e7cbaaf99efd745f9fdcbf`.
Receipt `/tmp/cyber-final2-linux-source-verification.json`.

## Archived builder failure

Used Rust1.89 configuration, jobs2, GCC, Nushell0.112.2, fresh candidate path;
20GiB guest disk was free. The actual archived `scripts/build-candidate.nu`
failed at line24 with `nu::shell::column_not_found`: `LAST_EXIT_CODE` is absent
following `let prefix = (^mktemp ... | str trim)`. No Cargo build began. The
staging directory creation lies before the script's try/catch and leaves an empty
staging directory on this path. Log `/tmp/cyber-final2-linux-build.log`, exit1.

Required correction: capture `mktemp` with `complete`, validate its explicit
`exit_code`, and derive the staging path from `stdout`. The source owner was
notified; the frozen FINAL2 source was not edited. A corrected archive requires a
new identity and a fresh native build, full installed smoke, packaging and node
gate. Existing rehearsal artifacts remain preserved and do not certify FINAL2.
