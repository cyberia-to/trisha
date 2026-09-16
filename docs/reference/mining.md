# Neptune mining session contract (v0.15.1)

Consensus is selected from the exact pinned network/height schedule, never by
whether a PoW field happens to decode. Beta and Gamma use fast PoW; pre-Beta
rules use their corresponding leaf prefix and ordering. Required version and
lustration fields are checked before work. RPC failures and malformed templates
must not trigger allocation of a legacy mining buffer.

A session has one attempt budget across CPU/GPU workers, template refreshes and
submission retries. Reservations are bounded, non-overlapping, overflow-safe.
An exhausted device is not an unavailable device. Explicit CPU/GPU selections
are honored; auto may select CPU if GPU initialization is unavailable.

The host owns the accepted result under one mutex. GPU mapped state is private
to an exclusive, synchronous dispatcher. CPU workers never access GPU result
flags or payload. Only a completed, CPU-validated GPU result may enter the host
winner slot, which is write-once. No borrowed mapped data escapes the dispatcher.

Mining proceeds in bounded batches and refreshes the template between batches
and before submission. A changed parent invalidates a pending result. Submission
rejection refreshes the template and continues within the original budget.
No template is a bounded error, not an unbounded busy wait. Network requests have
a timeout. Legacy buffer construction remains explicit, expensive work; bounded
unit/oracle tests must not allocate the production-size buffer.

Validation includes deterministic reservation/publication/refresh tests and
small real Metal/native hash and threshold comparisons. No mock acceptance is a
claim of live mining or successful network submission.

## Implemented CLI behavior

`--backend cpu` and `honeycrisp` select CPU mining (the latter is an explicit
alias for the host CPU implementation). `gpu` selects Metal only and reports
unavailability; `auto` uses a reusable combined CPU/Metal miner when available,
otherwise CPU. There is no second full-budget retry after exhaustion.

The CLI checks `node_network` on the same HTTP endpoint before each template
fetch. Mainnet boundaries are 15000 / 23401 / 38000 / 40300; testnet-0 boundaries
are 120 / 3571 / 3669 / 4650 (Reboot, Alpha, TVM1, Beta, Gamma). Regtest,
testnet-mock and other valid testnet IDs use Gamma, matching upstream.

Templates require matching header/metadata parent and version. Fast PoW inserts
the declared header version in `pathA[26][4]` and validates all six lustration
codec fields against exact i128 JSON metadata (no floating-point conversion).
The parent remains fixed throughout a batch of at most 4096 reserved attempts.
A fresh template is fetched before submission. Rejected/stale results consume
their reservation; retries never reset the global attempt cap or nonce offset.
HTTP requests time out after 15 seconds. A null template or transport error is
reported explicitly. This is a bounded batch refresh, not asynchronous live tip
streaming; a tip can still change between the final check and submission, which
is handled as an ordinary rejection.

Legacy Reboot builds leaves from the current MAST commitment without bit
reversal. Alpha/TVM1 use the parent digest and bit-reversed order. Buffers are
cached only while that exact prefix/order matches, and old buffers are dropped
before rebuilding. Construction itself is not asynchronously cancellable and
requires approximately 43 GB peak memory; full-size construction remains an
operational gate on suitable hardware. No release test pretends a reduced tree
is a full 2^29-leaf live mining run.
