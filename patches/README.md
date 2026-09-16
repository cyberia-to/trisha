# Pinned upstream bootstrap

Run `nu patches/apply.nu` to regenerate the eight patched registry crates.
Python 3.11 or newer is required. `upstream.json` fixes the exact crate version
and SHA-256 of each published `.crate` archive; these pins match the independent
Neptune policy oracle's Cargo.lock for Triton/tasm-lib 7.0.0 and twenty-first
1.1.0. Review version and checksum changes together with the patch anchors.

`fetch.py` first checks cached `.crate` bytes, then uses the official crates.io
CDN if no valid archive is cached. It verifies the pinned digest before
extracting into a fresh staging directory. Only regular files and directories
under the expected crate prefix are admitted. Mutable `registry/src` files,
archive links and paths escaping that prefix are excluded. A checksum or
extraction error preserves the previous vendor directory.

After extraction `apply.nu` applies the owned GPU overlay and pinned warning
fixes; `tasm.nu` installs the official recursive verifier crates. The source
packager records the resulting vendor file inventory separately from upstream
pins. Rust/manifest bytes must be compared when changing bootstrap mechanics;
an archive of different verifier code cannot inherit earlier proof receipts.

Validate the bootstrap boundary with `python3 -B patches/test_fetch.py`.
