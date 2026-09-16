# Neptune mining compatibility — release audit

Reviewed 2026-09-12 against Neptune **v0.15.1**, commit
`9869b5e35b659dc520fad51ba5a9c812fed46db0`. The independent checkout is
`/tmp/trisha-neptune-policy-v0.15.1`; permanent oracle dependencies pin that commit.
The first pass was a read-only review of concurrent production mining work.
The five findings below record that original snapshot; authorized fixes are
implemented as described in the closure section. No node, wallet, submission, large GuesserBuffer,
or STARK proof was run. Mining is not yet a closed release gate.

## Confirmed compatible pieces

- `NeptunePow::encode` agrees with native `Pow<29>::encode`: nonce 5,
  path B 145, path A 145, root 5 fields. Raw hashing input uses Montgomery
  words; target comparison uses canonical fields, highest digest coordinate first.
- `PowMastPaths::fast_mast_hash` has the exact native nested pair/variable-length
  hash structure. Three independently generated native vectors cover nonzero
  paths/root/nonce and values near the field modulus.
- Host `BlockTemplate` is 1440 bytes; MAST starts at 1160, target at 1400.
  `MineState` is 56 bytes, result attempt at 8, nonce at 16. These match the
  buffer offsets in `aruminium_mine.rs`. The `types.rs` comment saying target
  is “reverse-indexed” is inaccurate: storage is forward, comparison reverses
  the traversal, which is correct.
- Native `block/pow.rs::Pow::validate` treats **both HardforkBeta and
  HardforkGamma** as threshold-only fast PoW. Gamma does not require returning
  to memory-hard mining. Preserving the required lustration/version path fields
  remains necessary for the surrounding block validator.
- `cli/neptune.rs` uses the correct `mining_getBlockTemplate` and
  `mining_submitBlock` methods and positional tuple parameters. Native template
  metadata is snake_case; `RpcBlockPow` uses camelCase `pathA`/`pathB`. These are
  not schema mismatches. Server-side difficulty selection should be retained;
  do not independently recompute the threshold from proposal difficulty.

References in pinned upstream: `neptune-consensus/src/block/pow.rs`,
`block/block_header.rs`, `block/validity/block_primitive_witness.rs`,
`consensus_rule_set.rs`; `neptune-rpc/api/src/model/mining/template.rs`,
`model/block/header.rs`, `model/message.rs`; `neptune-core/src/application/json_rpc/server/service.rs`.

## Concrete release defects and bounded fixes

### 1. Fork selection is not a valid consensus discriminator

`cli/mine.rs:249` chooses fast PoW by non-null `metadata.lustration_status`.
Upstream metadata obtains this with `header.pow.lustration_status().ok()`.
**Even `Pow::<29>::default()` successfully decodes a lustration status** (the
independent oracle asserts this). Therefore a legacy template with zero PoW
can be misclassified as fast PoW. Conversely, missing metadata triggers an
unconditional roughly 43 GB peak legacy allocation rather than a schema error.

Infer rules from the configured network and template height using the pinned
schedule, validate required metadata, and explicitly reject unsupported legacy
rules before allocation. If supporting Reboot, implement its actual rule:
native leaf prefix is `mast_paths.commit()` and indices are not bit-reversed;
local `GuesserBuffer::build(prev_block)` uses the later parent-digest scheme
and bit reversal. A single generic legacy fallback is incorrect.

Also validate/build required path fields from metadata. The current comment
that the composer always inserts the version is not generally true:
`BlockHeader::template_header` initializes default PoW; native `Pow::guess`
explicitly writes the supplied version at `pathA[26][4]`. Pinned header version
is currently zero, so copying the template does not by itself prove a current
version mismatch. Add a nonzero-version contract regression rather than
claiming Gamma currently hashes incorrectly.

### 2. CPU winner is mistaken for GPU winner

In `honeycrisp/neptune_mine.rs:553–606`, CPU and GPU share `found = 1`, but CPU
writes only the Rust `Mutex<Option<NeptunePow>>`, whereas GPU writes
`MineState.winning_nonce`. If CPU wins during an in-flight GPU dispatch, the
GPU host thread sees `found`, reads stale GPU nonce data, and may clear the
shared winner flag as a “GPU false positive”. It can also overwrite the CPU
result when the stale nonce happens to meet an easy threshold.

Use distinct claimed/ready states and an explicit winner origin, or separate
GPU dispatch result state and a single host-owned publication point. Publish
payload before the ready state; never clear another worker's published win.
Add deterministic CPU-wins-during-dispatch and GPU-wins tests using an injected
small dispatcher, not a probabilistic mining stress test.

### 3. Safe GPU API permits unsynchronized aliasing

`honeycrisp/aruminium_mine.rs:44–45` asserts `Send + Sync`; `set_template(&self)`
creates a mutable template reference from the shared buffer while safe
`template(&self)` exposes an immutable reference. Concurrent calls or a retained
reference can overlap mutation. `state()` similarly exposes non-atomic payload
while Metal may write it. Documentation does not make these safe APIs sound.

Require exclusive configuration access and prevent configuration during a
running session; keep mapped payload behind the synchronization abstraction.
Return copied results only after dispatch completion and proper publication.
Do not expose references to concurrently mutable mapped memory.

### 4. Attempt limit and backend selection are not honored

The Neptune branch of `cli/mine.rs` ignores `args.backend`. On supported GPU
builds it always invokes combined mining, then `.or_else` runs a fresh full CPU
budget for any `None`, including ordinary exhaustion. In the GPU loop,
`fetch_add(THREADS_TOTAL)` and fixed dispatch execute a complete final batch even
if fewer attempts remain; the kernel has no active-count guard.

Distinguish unavailable/error/exhausted outcomes, honor the requested backend,
reserve bounded attempt ranges without overflow, and pass the final active
count to the kernel. Exhaustion must not restart the budget. Test limits 0, 1,
batch−1, batch, batch+1 and unavailable GPU fallback. Report actual attempts,
not the requested maximum after early success (the legacy reporting path also
uses the maximum to calculate throughput).

### 5. No stale-template cancellation/refresh

`cli/mine.rs:186` fetches a single template and mines it for the entire attempt
budget. There is no tip monitoring or cancellation when `prev_block` changes.
Upstream submission validates against the current tip, so a long session can
consume its entire budget on a stale block. Add bounded batches plus periodic
template refresh, cancellation and a fresh generation identifier; a late
worker result must never be submitted under a newer template. Mock RPC tests
should cover tip change, no available template, rejection, and subsequent retry.

## Reproducible bounded checks

The new independent example `tools/neptune-policy-oracle/examples/mining_pow.rs`
uses native consensus `Pow` and its codec/hash; it does not import local mining
code. It additionally proves the default-lustration discriminator counterexample
and the native nonzero-version slot. Regenerate vectors with:

```sh
RAYON_NUM_THREADS=4 cargo run --manifest-path tools/neptune-policy-oracle/Cargo.toml \
  --release --example mining_pow -j4
cargo test -p trisha-honeycrisp --locked --test neptune_pow_compatibility -j4
```

Golden output lives in `honeycrisp/tests/fixtures/neptune_pow_v0151.rs`;
`honeycrisp/tests/neptune_pow_compatibility.rs` checks all 300 canonical/raw codec
words, native MAST hashes, and CPU/Metal structure offsets. These tests establish
CPU hash/layout compatibility, **not execution of the Metal kernel**, concurrency
safety, successful live submission, or complete mining readiness. A small
explicit-nonce GPU-versus-native hash test is still required after production
ownership fixes, including threshold equality and adjacent boundary targets.

Receipt: independent oracle rerun succeeded and reproduced the checked-in
vectors byte-for-byte (`/tmp/mining-pow-oracle.log`). Local test command passed
**2 tests, 0 failed, 0 ignored**, without compiler warnings
(`/tmp/neptune-mining-compatibility-tests.log`).


## Authorized correction checkpoint

All five identified production defects have been addressed in the mining-owned
files. The normative contract is `docs/reference/mining.md`:

- Pinned network/height selection, HTTP node-network check, full exact lustration
  metadata validation and native version insertion; both legacy prefix/order
  variants retained rather than silently dropping pre-Beta functionality.
- Exclusive synchronous GPU API with no escaping mapped views; separate host
  winner mutex prevents GPU completion from resetting/overwriting a CPU win.
- Overflow-safe bounded reservations and an active nonce count in Metal; explicit
  backend selection, initialized GPU reuse, no exhaustion-as-unavailability retry.
- At most 4096 reserved attempts per template batch, a refresh before submission,
  and bounded retry within the same global cap/nonce sequence.
- Entire GPU buffers initialized before typed access; no configuration-free
  dispatch. Exact CPU/Metal layout remains unchanged.

Deterministic tests cover concurrent budget reservations up to u64::MAX, both
winner publication orders, exact fork boundaries, >u64 lustration amounts,
nonzero header version, stale-result discard, submission rejection/retry, null
responses, RPC envelope/network mismatch and budget exhaustion. The legacy leaf
ordering test independently computes pairwise 32-bud roots over a 64-leaf
fixture; it does not allocate a production GuesserBuffer.

The actual Metal oracle runs on the available Apple device with nonzero paths
and MAST inputs, including nonce attempts 0/1/255/u64::MAX, equality and adjacent
lower thresholds, and active batch counts 0/1/255/256/257. This closes the bounded
GPU/native hash gate, not the live node submission or full legacy-buffer gate.
No network submission, wallet mutation or large memory mining was performed.

Final bounded receipts after corrections:

- `/tmp/neptune-mining-owner-final.log`: **8 passed** (5 library tests, 1 actual
  Metal test, 2 pinned codec/layout tests), no failures, ignores or warnings.
- `/tmp/neptune-mining-cli-final.log`: **7 passed** in the mining-only CLI build,
  no failures, ignores or warnings. The default Triton+GPU CLI variant also
  passed the same seven tests before the final alias-only fixture addition.
- `/tmp/neptune-mining-only-check.log`: `cargo check -p trisha
  --no-default-features --locked` passed without warnings after gating the
  Triton-only error variants and display arms.

Remaining operational boundaries: no live-node accepted-block receipt; no full
2^29-leaf/43 GB peak legacy-buffer run; no asynchronous cancellation during that
legacy construction. Fast mining refresh is bounded by a 4096-attempt batch and
HTTP timeout, not a streaming subscription. These limits remain visible and are
not converted into a claim that the entire full-release goal is complete.
