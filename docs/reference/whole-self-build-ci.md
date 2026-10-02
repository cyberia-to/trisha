# Native whole self-build replay

This workflow replays the accepted complete C1→C2 and C2→C3 compiler jobs using
the public `joy-nox-disclosed-compiler-v1` certificate profile. Each job builds
native Linux x64 Joy from committed source pins, proves one complete computation,
then checks the certificate in a fresh process against explicit expected compiler
and JOB1 files. It reports successful proof verification separately from durable
evidence retention. Observed results belong in `audit/`.

The workflow uses `ubuntu-24.04` in the public repository. Its first activation
is a reviewed push to exactly `test/0.4-whole-self-build-ci`, selected only by
changes to the workflow file or `.github/whole-self-build-activation.json`.
That committed selector explicitly authorizes this branch and draft retention.
Audit-only and script-only commits do not trigger another push run. Subsequent
manual dispatches select retention explicitly. The driver admits only that exact
push branch with the selector's authorization, or a manual dispatch in the fixed
repository. The workflow and all three selectors join the bootstrap source hash
inventory, which is rechecked after execution. The default branch is unchanged.
GitHub requires default-branch presence for initial manual workflow activation:
[workflow dispatch](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch).
GitHub documents free standard public runners with four CPUs, 16 GB RAM and
14 GB SSD storage. Their job limit is six hours. These are platform constraints,
not measurements of this workflow. The exact 48 GiB free-start preflight must pass
after recorded cleanup of a fixed unused-SDK allowlist; otherwise the job stops.
No paid runner or automatic resource increase is selected.
Sources: [hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
and [Actions limits](https://docs.github.com/en/actions/reference/limits).

The immutable input archive is selected by release asset ID, exact size, SHA256
and files.json SHA256. Admission requires its fixed root directory, unique safe
regular-file names, exact manifest membership and every member hash/size. Links,
path traversal, extra/missing files and mismatched bytes fail. Its historical
scripts are evidence only. Both compiler artifacts, both JOB1s, the full 94-module
source graph and accepted SH6 receipts stay byte-identical.

The source build reuses PR21's origin-only fetch, complete clean inventories,
Cargo closure validation and sanitized environment. Absolute Rust 1.89.0 compiler,
Cargo and rustdoc paths share one native toolchain directory. Build caches live
outside source checkouts; explicit isolated Cargo home prevents local overrides.
No source patch or working-tree input is accepted. The runtime commands use the
newly built absolute Joy path with empty PATH. Only the locale and the runner's
process-tracking identifier accompany that empty search path; build and network
credentials are excluded. SIGTERM unwinds the process-group guard and saves its
failure receipt. The workflow reserves separate build/replay, retention and
metadata-upload step deadlines within its six-hour job limit.

Host bounds retain 20 billion charge, one billion allocations, 65,536 frames,
3,145,728 resident nouns, 10 billion collection work and 7,200 seconds. Proof bounds
retain 24 GiB wire, 96 GiB decoded, 12 billion records, 16 billion expanded steps
and 262,144 cache slots. Outer bounds retain 7,500 seconds, 6 GiB sampled process
RSS, 30 GiB attempt disk and an 8 GiB free-space floor. Memory, time and physical
disk observations remain unattested host evidence.

Before proving, the full manifest is repacked by native Joy and must reproduce the
frozen JOB1 bytes. Prover and fresh verifier reports must match the accepted
program/input/output particles, charged reductions, logical peak frames, expanded
steps and full compiler response. Fresh verification must omit prover host
observations. Extracted C2/C3 ART1 bytes must match the accepted C2 SHA256 exactly.
Binary, source and input identities are rechecked after work completes.

Complete proof files are retained as ordered chunks of at most 1 GiB. The manifest
records each part's order, size and SHA256 and the reconstructed full-file identity,
along with source/input/toolchain/binary and command receipts. GitHub release
assets must each be below 2 GiB, so full certificates cannot be single release
assets once they cross that bound. Source:
[release storage limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

Draft retention requires an explicit dispatch selection or the reviewed push
activation selector's authorization. Both replay and retention validate the
same event and selection. It may add
uniquely named assets to the fixed existing unpublished draft, using its release
ID. It requires the expected draft/tag state, absent tag ref, exact returned asset
identity and an independently downloaded hash check. Before and after publication,
asset names and fixed-release membership are checked against a paginated listing.
Each uploaded and listed asset must have state `uploaded` and the exact fixed
repository's `api.github.com` release-asset URL for its numeric ID. Downloaded
parts also feed one ordered rolling SHA256 and byte count; the complete readback
identity must equal the verified original before the final manifest is emitted.
Pre/post draft checks are
observations rather than a lock against unrelated owner changes. No publication,
promotion, tag creation, overwrite or deletion is part of the workflow.
Small Actions artifacts retain raw success or failure metadata; complete proof
assets and their manifest have distinct durable-retention status. Missing or
failed work is recorded as incomplete or failed, never as acceptance.
