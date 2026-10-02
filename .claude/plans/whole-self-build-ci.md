# Full self-build proof replay on native Linux

Prepared scope: independent positive C1→C2 and C2→C3 replays from the immutable
accepted full inputs. No remote job or upload starts before root review and the
final input asset identity. Local producers and installed source families remain
untouched. Branch: `test/0.4-whole-self-build-ci`, based on origin/release/0.4
`d59738198aff278e7166e5958fbbc5f9777986b7`.

1. Reuse the exact committed `native_proof_inputs.py` from reviewed PR21 head
   `2b7017f89a495eb43c0feca6818eb68f35c21a02`, with its complete 12-repository
   selector. Resolve absolute native Rust 1.89.0 tools, use isolated Cargo home and
   target paths, verify clean source inventories and resolved Cargo closure.
2. Add a manual-only Linux x64 workflow with two independent generation jobs on
   free public-repository `ubuntu-24.04`; maximum six hours per job. Preserve the
   original 7,200-second guest-host deadline and all whole-proof profile caps.
3. Download the reviewed input asset by immutable release-asset ID, enforce exact
   16,637,580-byte size and SHA256
   `7929925282e338a2f761510167575bfe4494c2713ac6fb9182fe59ef6223b9b8`.
   Validate the pinned files.json hash and every safe regular archive member before
   using inputs. Archived scripts are retained as evidence and never executed.
4. Run a fixed allowlist of unused SDK cleanup only on the ephemeral hosted Linux
   runner. Record before/after filesystem observations. Keep the original 48 GiB
   free-start requirement; fail closed if unavailable. No paid runner or relaxed
   resource bound. The documented 14 GB standard-runner storage is insufficient
   by itself, so measured cleanup success is a prerequisite, never a claim.
5. Build exact native Joy; repack the unchanged full job and require byte equality.
   Produce a certificate with the exact C1/C2 artifact and job; verify in a fresh
   process with empty PATH; compare full roots, charge, depth, expanded steps and
   compiler response against the accepted SH6 receipt. Require exact C2/C3 ART1
   bytes. Rehash binary, inputs and source inventories after the commands.
6. Retain only successful complete certificates as ordered 1 GiB chunks with a
   full-file SHA256, part hashes/lengths, source/input/binary identities and raw
   command receipts. Keep at most one extra chunk on disk. A reviewed, explicit
   draft-retention flag may upload uniquely named parts to existing draft release
   389977897 by release ID, checking draft/tag state and server digest, then
   independently streaming each asset back and checking hashes. Never create a
   release, publish/promote, create/push a tag or replace an existing asset.
7. Preserve success/failure metadata through small Actions artifacts. Full proofs
   use release chunks to avoid Actions artifact storage quotas. The workflow must
   distinguish proof verification from successful durable retention and record
   failure at either stage without invented results.

Validation before review: Python unit tests for safe archive admission, exact
profile comparisons, chunk reconstruction and resource guards; syntax and
actionlint; positive local transport/fixture checks only where they are needed
to validate orchestration. No local full replay and no altered-input proof suite.

Input asset is now pinned as release asset 604704433; root checked its server
digest after upload. Root approved the exact 48 GiB preflight and fixed allowlist
cleanup. PR21 helper approval was confirmed by its owning agent; six native
profile jobs passed independently before this work. PR21 is now merged at
`191c6e03fa855be3b70b5aa5e4ee78be1ebffe91`; the reused helper bytes are identical.
