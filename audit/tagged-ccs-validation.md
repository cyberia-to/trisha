# Experimental tagged CCS proof validation — 2026-09-12

Two fresh native Triton7 STARKs passed in the ignored integration test
`genuine_tagged_ccs_proofs_bind_atom_pair_topology_under_same_matrices`.
This is test-only integration, not a production Joy/Zheng protocol or a claim
that general nox execution is complete. No production files changed in this gate.

## Exact gate and results

```sh
CARGO_BUILD_JOBS=2 RAYON_NUM_THREADS=4 TVM_LDE_TRACE=no_cache cargo test --release --locked -p trisha-rs --test tagged_ccs genuine_tagged_ccs_proofs_bind_atom_pair_topology_under_same_matrices -- --ignored --nocapture --test-threads=1
```

The verifier derives one relation for `if(axis1, quote7, quote[8,9])` and an atom
subject. Its checker assembly is byte-identical for both statements. Input0
selects atom7; input1 selects pair[8,9]; both bind exact native cost3. The test
sorts and consistently merges public coordinates, verifies the constant-one
pin, and leaves its enforcement to the native CCS checker. It binds all other
input/output tag, payload, absent-child padding and cost coordinates.

| Statement | Fresh proof bytes | Result |
|---|---:|---|
| input0, atom7, cost3 | 873856 | Verified |
| input1, pair[8,9], cost3 | 872816 | Verified |

Both proofs survive encode/decode and genuine native verification. Negative
assertions reject the opposite valid statement, reversed pair payload, changed
cost and mutated public claim. Crucially the test replaces the **complete**
public-input envelope with the opposite valid branch's coordinates and verifies
against that branch's checker. The program is the same and metadata now matches,
so rejection is by STARK claim binding, not only envelope mismatch. Both public
outputs of the native CCS checker remain its normal empty stream.

Test result: **1 passed, 0 failed, 0 ignored** (explicit ignored-test invocation;
1 ordinary test filtered out). Test duration **25.99s**. Whole invocation,
including dependency compilation and monitor shutdown: **131.089s**.

## Resource guard and receipts

An owned new process group was sampled every1s. Guard limits: aggregate process
group RSS16GiB and host free memory at least15% (`memory_pressure -Q`). On a
violation only that group would be terminated and the failure preserved.
The guard did not trigger. Maximum **sampled** group RSS was **3,479,126,016
bytes**; minimum observed host free percentage was **41%**. This is sampled
RSS, not a kernel-accounted instantaneous peak. No proof parameter/security was
reduced; `TVM_LDE_TRACE=no_cache` changes upstream memory/cache strategy only.

Receipts: `/tmp/trisha-tagged-ccs-proof.log`,
`/tmp/trisha-tagged-ccs-proof-memory.jsonl`,
`/tmp/trisha-tagged-ccs-proof-receipt.json`; monitor script
`/tmp/run-tagged-ccs-guard.py`. Exit0, no remaining owned process; Trisha build
slot released to the full all-target/all-feature checker.

## Source identity

The following SHA256 values were captured before execution and checked unchanged
afterward. Paths beginning `zheng/` are relative to the sibling workspace root;
others are relative to Trisha. This lists the test and relevant code/lock files,
not an independently inventoried release archive or complete dependency closure.

| File | SHA256 |
|---|---|
| `Cargo.lock` | `6b98b23f1cc92878cb4f70017ac2078d3cd04b28e2eddbfc00e8f127b9ae0105` |
| `rs/ccs.rs` | `65ca3f27a709689f57939317633f3d6ebfa7c9cc1ea1bee16dd8b68412622889` |
| `rs/convert.rs` | `51c4f86647309d01b2462fc9e4148fdeee362c8fe3900895a55e8b2cda55fec2` |
| `rs/tests/tagged_ccs.rs` | `d9f0253dc21ce6565a2b3c30bc1b6d2f667bb8ce4aba0c021eca7bb0299a8585` |
| `zheng/rs/src/execution/tagged/build.rs` | `d4c261a9e2a0128e1d1a28ef5854ed21a2215ae1eac8f840afeff76c3c5085d4` |
| `zheng/rs/src/execution/tagged/eval.rs` | `f3c6d6fa92ac5692f42dae179a673ab1106b559510589a556305f9ed4d64713a` |
| `zheng/rs/src/execution/tagged/hash.rs` | `9b3f58473c471b2732f12734b07d0216a331ac122dbe9e5f4422e22817fe058a` |
| `zheng/rs/src/execution/tagged/hash_tests.rs` | `ee59fee5a6c160ec8c10262b327e3544ba7e7c3b952750ce1ec15813e64b4f7a` |
| `zheng/rs/src/execution/tagged/mod.rs` | `ece1682258fe688a89e9caf03fa01964934dc34eaf164f1d8b605ab03be8a483` |
| `zheng/rs/src/execution/tagged/tests.rs` | `33e991a13a791452a7e5953e7cf1b3f67ad3900bb029e8128fa8f030559e1ff3` |
| `zheng/rs/src/execution/tagged/word.rs` | `0cb6feeaf33a5c81637f989e873ddf7cd284ae509c023a5854b81bfe71d0f04f` |
| `zheng/rs/src/execution/tagged/word_tests.rs` | `3e1d175d65621f6443799a425ef74aa38fa729f1ed71fd0efdabb6e55660d13e` |
