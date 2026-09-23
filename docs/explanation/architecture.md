# Architecture

Trident resolves source modules, checks types and produces target-independent IR. Trisha owns Triton instruction selection, linking, AET costs and runtime execution. Generic bundle metadata comes from `trident::bundle_with_assembly`; the warrior supplies its assembly and cost estimate. Source commands share project/profile/dependency resolution.

```text
source -> Trident resolved modules/TIR -> Trisha lower/link -> ProgramBundle
                                                               |
                                                        run/prove/verify
```

`cli/` is the interface; `rs/` implements the default CPU runtime. `wgpu/` is a separate backend, and `honeycrisp/` provides mining integration. `neptune/` owns the pinned consensus/RPC transaction adapter and its intent boundary; these protocol dependencies do not belong to the compiler or CPU engine. The default command-line proving path uses CPU. Selecting a mining GPU feature does not change the proving backend.

Trisha owns Triton machine metadata in `targets/triton`, its SDK in `lib/vm/triton`, Neptune `.tri` modules in `lib/os/neptune`, network/state descriptors in `networks/neptune`, and hand assembly in `baselines/triton`. Source namespaces remain independent of physical paths. The embedded target package exports the authoritative descriptors and module sources to the compiler. CLI network selection is generated from the same Neptune state manifests; no separate hardcoded state registry is maintained. Runtime capabilities report CPU execution and STARK proving. The generic deployment trait cannot carry transaction intent and retains `deploy=false`; the owner CLI exposes the separate transaction interface described below.

Source execution requires a program entry. Library builds retain their definitions without inventing a halt-only program. Unknown and non-Triton targets fail. Program inspection computes the native lock-script hash and checks any attached proof. Transaction preparation separately requires explicit network-bound intent, complete canonical transaction/output preimages and the exact SingleProof claim. A compiled program alone cannot select wallet funds or authorize submission. `trisha deploy output`, `prepare` and `submit` implement this owner interface. Genuine proof validation, mutation rejection and authenticated submission into an isolated Neptune 0.15.1 Testnet(1) mempool passed the [local node gate](../../audit/neptune-local-node-validation.md). Funded wallet construction, public-network operation and block confirmation remain separate requirements.

CPU and wgpu share the native input/claim/proof boundary implemented in `rs/convert.rs`; GPU acceleration must not change proof acceptance. Inputs are bounded at8Mi total field words (including five per digest) and must be canonical before conversion. Claims require exactly five canonical Goldilocks hash elements, canonical public input/output and the supported proof format. Incomplete nondeterministic digests are rejected. Batch proving checks unique destination paths before starting work.

Stack IR construction tracks all live operands, including imported named structures and unequal-width tuples. Generic TIR return cleanup uses stack permutations and pops, preserving word order and source RAM. The owner lowerer implements deep accesses with temporary RAM whose contents are restored before the next source operation. The optimizer must preserve the observable operand stack; equal-depth cleanup swaps cannot be collected ahead of their pops.

`trisha bench` executes unchanged programs using `.bench.toml` reference fixtures. Expected output must match before cycle comparisons appear. Full mode proves and verifies both dimensions. Assertions, recursion, reads and calls are never replaced with dummy operations. Missing or failing fixtures remain unverified and make the full coverage gate fail. Neural results require their own verified fixtures.

## Machine legalization and SDK names

Shared TIR carries unbounded semantic stack operations. Trisha batches counts into Triton instructions of at most five words and legalizes access deeper than register 15. Ordinary source RAM has no compiler-reserved interval. The lowerer checks every cell in a preferred temporary block at `2^31`; it uses the block only if all cells are zero. Otherwise it searches monotonically from address zero for a contiguous zero run and rejects address-space exhaustion. Occupied cells are never overwritten, including at the preferred address. The borrowed cells are zeroed before returning to source code, with no user calls or I/O while temporary values are live.

The requested temporary size depends on stack depth; search cost also depends on existing RAM contents. Static source costs cannot certify a bound for arbitrary RAM occupancy. Tests exercise occupied/fragmented memory, zero-valued stack words, field-address wrap, source block reads/writes, and preservation of every nonzero RAM cell. Inline assembly keeps live locals on the operand stack and must preserve the compiler-owned prefix; it shares source RAM without a hidden spill frame. The former fixed-address cleanup/spill behavior was a correctness defect, recorded in the [RAM review](../../audit/ram-scratch-review.md).

Consecutive pure `Dup`/`Swap`/`Pop` operations can share one temporary frame.
The owner computes their complete stack permutation and selects that lowering
only when it is cheaper than the individual accesses on a free preferred block.
It preserves untouched prefix words, handles duplicated and discarded words,
and restores the entire RAM frame before any I/O, memory operation, call,
assembly block or control-flow boundary. This keeps wide argument/return frames
from repeatedly searching, writing and restoring the same temporary cells.

Use `vm.triton.hash`, `vm.triton.merkle`, `vm.triton.merkle_proof`, and `os.neptune.auth` for the fixed Tip5/Neptune ABI. Old generic aliases are deliberately absent. Historical hand-assembly baseline names are retained as provenance, not as compiler module aliases.

`trisha describe --target triton` and `--target neptune` export schema1/compiler API3 JSON. Module hashes identify the embedded sources, and the package separates compilation identity from deployment-state selection.

The retired handwritten `os.neptune.proof` module remains excluded; its FRI/OOD/constraint checks were incomplete. Historical prototypes are preserved under `examples/experimental/neptune`. The production replacement is `vm.triton.proof.verify`, which invokes the official Triton7 verifier with a complete caller-authorized claim. Neptune exports fixed canonical0.15.1 policies through `os.neptune.transaction.verify` and `os.neptune.native_currency.verify`. See the [recursive proof contract](../reference/recursive-proof.md) for witness preparation and the distinction between consensus proof verification and network admission.
