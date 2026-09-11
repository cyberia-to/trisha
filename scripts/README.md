# Coordinated local candidates

`package-source.nu <new-directory>` collects the locked Cargo dependency closure
of both Trisha and Joy, including Trident. The strict default requires committed
source inputs and the Trident/Trisha/Joy root lockfiles. It archives repository
commits and copies patched vendor sources separately.

`package-source.nu <new-directory> --snapshot-worktrees` creates an explicitly
marked local candidate from current sources, including uncommitted dependency
inputs. It does not commit, stash, revert, or otherwise change those repositories.
`sources.json` records each HEAD, dirty status, and SHA-256 of every copied file;
`vendor-sources.json` records the patched dependency files. Git-ignored files,
build output, VCS directories and caches are excluded. Root workspace lockfiles
govern builds; ancillary dependency lockfiles are recorded without being treated
as clean-release prerequisites. Regenerate the snapshot after any source change.

Both modes produce a `.tar.gz` and its SHA-256. The archive includes `BUILD.txt`
with commands to build/install Trident, Trisha and Joy. Nushell, Python 3, Git,
Cargo and tar are required. Snapshot metadata validates provenance; it does not
claim that every experimental backend or network protocol is implemented.

`smoke-release.nu <installed-bin-directory> <new-work-directory>` exercises all
three installed binaries with only that binary directory on PATH. It checks
target/package discovery, project target precedence, Neptune state descriptions,
artifact extensions, CPU Triton proofs and tamper rejection, public Zheng
execution certificates and claim rejection, and unsupported recursive SDK/state
packaging. Run this against freshly installed coordinated binaries.

`python3 -B scripts/test_snapshot_source.py` checks snapshot fidelity and verifies
that source worktrees remain unchanged.
