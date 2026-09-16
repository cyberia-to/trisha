# Strict committed-source packaging rehearsal — 2026-09-12

The strict default of `scripts/package-source.nu` successfully packaged11
isolated temporary Git repositories with committed source inventories, without
`--snapshot-worktrees`. These repositories were constructed from preserved
FINAL3 source solely to exercise packaging. Production worktrees and commits
were not changed, and these fixture commits are not release commits.

The final rehearsal retains all2442 original source entries, compared by exact
path, kind, byte length and content hash, plus557 verified vendor entries. The original
two Honeycrisp tracked plan files match too: the first fixture `git add --all`
had omitted them because the current ignore rules matched them. Explicitly
tracking those two fixture files restored the complete original inventory.
Manifest list ordering differs between strict and snapshot modes; equality is
checked by path, not array ordering.

- Fixture worktree: `/tmp/cyber-strict-package-fixture-20260912`.
- Output: `/tmp/cyber-strict-packaged-exact-20260912.tar.gz`.
- Source manifest SHA-256:
  `e045e70a71c6d07d66f9d27928791686119d2e775de494e343e3f800f95f7df8`.
- Archive SHA-256:
  `9a7522f5aeaa7c26c0999c8dd7a353f46e153d9e39794804c7cbe883c97507c4`.
- Machine receipt: `/tmp/cyber-strict-package-exact-receipt.json`.
- Packaging log: `/tmp/cyber-strict-package-exact-rehearsal.log`.

Nushell configuration was disabled and the ambient `LAST_EXIT_CODE` variable
removed before invoking packaging. Source verification succeeds independently
after packaging. This validates the strict packaging path for actual committed
fixture inputs; it does not establish a final product commit, executable build,
proof result or release publication. FINAL3 predates subsequent compiler fixes.
