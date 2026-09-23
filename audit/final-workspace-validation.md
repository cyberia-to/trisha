# Final workspace validation

Validation scope: current coordinated working tree, Darwin arm64 host, release
profile and locked dependencies. This is a source-candidate check, not a registry
publication or a live network deployment. No wallet/node mutation is involved.

## Current final rerun

After the mining, Neptune adapter, local-testnet1 and scoped formatting changes,
`RAYON_NUM_THREADS=4 RUST_TEST_THREADS=4 cargo test --workspace --all-features
--release --locked` passed **428 tests**, with **0 failures and 3 ignored**,
across **55 test/doc-test binaries**. Exit0, zero Rust warnings. Receipt:
`/tmp/trisha-workspace-final-current-rerun.log`. This supersedes the earlier
409-test receipt below.

The first attempt exposed a test-only JSON Value to TOML serialization issue
under serde_json arbitrary_precision. The owner replaced the fixture with native
TOML values; typed production ProofFile serialization was unaffected. The full
rerun includes both fixed Neptune policy proof workflows and the FIFO input
regression. Initial failure: `/tmp/trisha-workspace-final-current.log`; narrow
fix receipt: `/tmp/trisha-policy-typed-toml-fix.log`.

The three intentionally ignored tests are:

- `genuine_transaction_prepare_and_mock_gateway_process` (CLI deployment).
- `genuine_custom_lock_transaction_and_binding_mutations` (Neptune adapter).
- `outer_proof_binds_compiled_recursive_sdk_to_public_claim` (recursive SDK).

Their separately scheduled proof evidence is not inferred from this run.
All three were subsequently invoked and passed: the [recursive SDK outer
proof](recursive-release.md) and both [genuine Neptune deployment
tests](neptune-local-node-validation.md). The actual isolated Neptune node then
accepted the same canonical kernel into its mempool and rejected a changed
kernel with the original proof. These separate receipts do not change the
ordinary suite's 428 passed / 3 ignored accounting.

The separate default-feature CLI package run, `RAYON_NUM_THREADS=4
RUST_TEST_THREADS=4 cargo test -p trisha --release --locked`, also passed:
**33 passed, 0 failed, 1 ignored**, across7 binaries, exit0 and zero Rust
warnings (`/tmp/trisha-default-cli-final-current.log`). This includes13 CLI
unit tests, output-construction1, deployment1, wallet8, node-status1,
recursive-input3 and source-pipeline6. The ignored test is the genuine
transaction prepare/mock-gateway proof gate listed above.

Scoped formatting changed only 13 already changed/untracked Trident Rust files
and 17 Trisha files, including the separate oracle workspace; those files now
pass rustfmt. Unchanged pre-existing formatting differences in other files and
sibling dependencies were not modified. `git diff --check` passed in Trident,
Trisha and Joy; Joy scoped cargo fmt check passed. A whole-workspace formatting
pass is not claimed. The post-format Trident workspace neural suite also passed
**851 tests**, zero failures/ignored/warnings, exit0:
`/tmp/trident-postformat-workspace-neural.log`.

## Earlier test commands

- `cargo test --workspace --release --all-features --locked`
  (`/tmp/trisha-final-workspace-validation.log`): exit101. Two failures in
  `trisha-rs --test triton_compile`: test_coin_compiles:434 and
  test_card_compiles:479 require a `merkle_step` opcode. The selected PLUMBv2
  examples now use plumb.update_leaf with explicit pair/hash operations over
  the same20 siblings and assert_digest of the old root. Reported to the owner;
  the owner then authorized test-only corrections. The checks now execute an
  independent PLUMBv2 transition and reject changes to every coordinate of
  both roots, changed shared-path siblings, and path truncation; they also
  require update_leaf linkage and digest assertions. Production code is unchanged.
  Full rerun: `/tmp/trisha-final-workspace-validation-rerun.log` passed
  **409 tests**, with **1 ignored**, across 49 test/doc-test binaries.
  Exit0; zero Rust warnings.
  No Rust compiler warnings were emitted.
- Default CLI source/process tests: **19 passed**, zero warnings, using
  `cargo test -p trisha --release --locked --test source_pipeline
  --test neptune_wallet --test node_status --test deployment --test recursive_input`
  (`/tmp/trisha-final-default-cli.log`). Counts: source6, wallet8, node-status1,
  deployment1, recursive-input3. This includes real small source proof/verify
  plus hostile-claim rejection, outside-checkout resources, and mock wallet IO.
- Ignored recursive proof tests are intentionally excluded from this run; their
  separate completed proof evidence belongs to the recursive backend audit.

## Read-only capability and documentation review

Confirmed directly against code and owned target manifests:

- Trident's default target is nox; Trisha's own source commands select Triton by
  default. These are separate defaults and should remain explicit.
- Trisha target packages use schema1/compiler API2, Triton VM7.0.0 and native
  proof/claim version5. The proof envelope is `stark-triton-v7`; verification
  requires the current native version and default upstream security parameters.
- Joy packages likewise use schema1/compiler API2. Private execution uses
  `joy-nox-ccs-triton7-zk-v3` / `JOYZK003`, distinct from public execution and
  public state formats. Its capabilities retain concrete static-shape/work
  limits, full public state tables, and no live synchronization/deployment claim.
- Neptune transaction and NativeCurrency SDK operations use pinned0.15.1
  HardforkGamma policies and require caller-authenticated commitments. The old
  handwritten `os.neptune.proof` module remains excluded. Official recursive
  verification is a replacement API, not rehabilitation of that old module.
- Both warriors advertise deploy=false. Neptune dry-run describes an artifact;
  it is not live deployment. CPU proving remains the CLI runtime; mining GPU
  feature selection does not automatically select a GPU prover.
- Complete sibling source archives are the supported packaging route under
  review. Resource files outside individual crate roots and workspace-root
  vendor patches remain registry publication blockers. See the exact manifest
  closure in `../../trident/audit/release-version-closure.md`; no registry install
  or publish success is inferred from workspace tests.

Documentation discrepancies initially reported to the parent (all four
subsequently corrected by the parent; no documentation edits made here):

1. `docs/explanation/architecture.md` says schema/compiler API1 instead of
   schema1/compiler API2.
2. README's baseline paragraph still says the collection lacks reference
   coverage; execution now passed133/133 fixtures and43/43 baselines. This does
   not imply all fixtures have completed proof benchmarks.
3. README's final paragraph must distinguish the excluded old proof module from
   the now implemented fixed transaction/NativeCurrency recursive SDK.
4. `docs/explanation/gpu-backend.md` says GPU is on by default; the current CLI
   uses CPU proving. Feature availability and selected backend must be separate.

This review does not assert universal private execution, private databases,
live Neptune state admission, registry publication, or unsupported platform
runtime validation.
