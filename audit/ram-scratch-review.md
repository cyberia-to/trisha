# Compiler scratch versus source RAM — independent review

2026-09-16: the implementation and new evidence are tracked in
[the repair record](ram-scratch-repair.md). The historical findings and
counterexamples below remain applicable to the frozen FINAL6 candidate.

2026-09-12. Read-only review of current source and installed FINAL6. No compiler,
VM, target metadata, fixture or archive was changed. Two concrete source-memory
clobbers are confirmed; this is not a hypothetical address collision.

## Contract

`trident/reference/language.md:485` defines word-addressed Field RAM and public
read/write, without an excluded address interval. `trident/lib/vm/io/mem.tri`
accepts Field addresses for scalar/block reads and writes. Trisha lowering at
`rs/lower/triton.rs:226` emits direct memory operations, without reserved-range
checks. The successful reproductions below independently establish acceptance.

`rs/lower/legalize.rs:2` internally calls `[2^31,2^31+depth+1)` reserved scratch;
that comment is not a canonical public memory ABI or an enforced source check.
The target metadata exposes `spill_ram_base=2^30`, without a range exclusion for
public operations. The generic cleanup allocator advances from that address.

`docs/reference/recursive-proof.md:22` does explicitly reserve its proof, claim,
control and context regions, and documents the upstream verifier's allocator.
Those contracts govern recursive verification calls; neither reproduction calls
a recursive verifier, context intrinsic, inline assembly or hand baseline.
Generic references to “compiler/backend-reserved memory” in crypto module docs
provide no complete address map for ordinary source RAM. They do not make these
otherwise ordinary source programs violate an explicit memory ABI.

## Confirmed source behavior

Run each source with:

```sh
trisha run <source.tri> --target triton --profile debug
trisha run <source.tri> --target triton --profile release
```

### Deep stack legalization silently overwrites2^31

```trident
program alias
use vm.io.mem
fn main() {
    let words: [Field; 20] = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
    mem.write(2147483648, 999)
    pub_write(words[0])
    pub_write(mem.read(2147483648))
}
```

Expected `[1,999]`; actual `[1,20]`, exit0, both profiles. Deep `Dup` lowers via
`rs/lower/legalize.rs:34`: it stores live words starting at2^31 and never restores
the prior user RAM contents. The first scratch word holds20 in this fixture.

### Multiword function cleanup silently overwrites2^30

```trident
program alias
use vm.io.mem
fn pair(x: Field) -> (Field, Field) { (x, x + 1) }
fn main() {
    mem.write(1073741824, 999)
    let (x, y) = pair(7)
    pub_write(x)
    pub_write(y)
    pub_write(mem.read(1073741824))
}
```

Expected `[7,8,999]`; actual `[7,8,8]`, exit0, both profiles.
`trident/src/ir/tir/builder/cleanup.rs:16` allocates return-preservation scratch
through `StackManager::alloc_scratch`, using the target's2^30 base. A one-word
parameter frame with a two-word return reaches this path through
`builder/functions.rs`. User RAM is not preserved after the returned words are
reloaded onto the stack.

## Evidence and scope

Both cases reproduce on both profiles using **both** binaries (8 actual VM runs):

- Current `trisha/target/release/trisha`, SHA256
  `498e3c496711ef0f55ba08fa376ef00c3300878fe90daf940804b3136c6ebbc9`.
- `/tmp/cyber-release-installed-v7-darwin-final6/bin/trisha`, SHA256
  `9dce2a104e6a01b21535a068f742bc5857c3cfebfc195016621e973fb204addf`.

Sources and complete process receipts are under `/tmp/trisha-ram-alias-review/`;
`current-final6-results.json` records exact commands, outputs, exit codes and
stderr. This review does not infer a proof failure: the VM correctly executes
its generated assembly, while source RAM semantics are silently altered.

The original2^29 runtime-index hypothesis is stale for **both current and FINAL6**:
no such allocator is present in their inspected TIR code. Runtime indices now
use balanced branch selection and stack copies; canonical `reference/ir.md:84`
describes that implementation. `TIRBuilder::new` tracks the full abstract stack
with `u32::MAX`; automatic sixteen-word LRU spill is not the path reproduced
here. The live2^30 cleanup and2^31 machine legalization paths are distinct.

The standard `ProgramInput` and Trisha file-input adapter expose public fields,
secret fields and digest paths, not an initial-RAM map. `sec ram` currently emits
TIR comments. No initial-RAM runtime experiment is claimed here; explicit source
writes already establish both defects without relying on first-read behavior or
an unavailable input surface.

## Required architecture decision

These are source-correctness blockers unless a complete reserved-memory ABI is
made explicit and enforced at every applicable public memory access. Merely
adding a comment or moving the scratch base leaves the same alias problem at a
new address. The alternative is an implementation that preserves visible RAM.
The owner must choose the memory contract before patching; this review does not
expand the language or prescribe a new general allocator.

Acceptance should cover both exact reproductions, runtime-supplied addresses,
block accesses crossing a boundary, and every memory-bearing public intrinsic
under the chosen contract. Legal addresses must retain their contents across
compiler-generated operations; prohibited addresses must fail explicitly rather
than producing a successful but different result. Existing deep-stack neighbor
tests do not exercise this source-RAM invariant.

## Preservation design (read-only, implementation pending)

The parent requires preserving arbitrary valid source RAM, not declaring the
reproduced addresses invalid after the fact. A feasible owner-level repair is:

1. Shared TIR return cleanup uses abstract stack permutations and pops, with no
   independent RAM frame. The typed owner is designing the known rotation repair
   for the `dead % return_width` case.
2. Trisha deep access temporarily stores displaced words in dynamically found
   pairs of **currently zero** cells. Each node stores `(word, previous_head)`.
   Head and a monotonic allocation cursor stay on the operand stack; all helper
   operations must fit the native direct stack window.
3. Restoring a node loads its word and predecessor and writes zero to both cells.
   The entire frame is unwound before the next original/source instruction.
   Thus all initially nonzero RAM is untouched and every borrowed zero cell has
   its original value at every source-visible boundary.

For deep Dup, save the words above the target, duplicate the target, then unwind
saved words **below the carried duplicate**. The result is the original stack
plus its requested copy. For Swap, carry the original top word, save only the
intervening words, exchange the carried top with the target, then unwind the
intervening words below the carried target. These transformations preserve every
other word. Exact emitted instruction sequences are the machine owner's work;
this report is not claiming an implemented/legalized assembly proof.

Required allocator invariants:

- Check both candidate cells are zero before borrowing either.
- Use a monotonic, nonrevisiting cursor while a frame is live. A node containing
  word0 and previous_head0 itself remains all-zero; “look for any zero pair”
  without nonreuse would overwrite a live node.
- Head0 can be a terminator by never choosing node base0 internally. This does
  not forbid source RAM address0, which remains untouched.
- Candidate pairs and cursor arithmetic cannot wrap modulo the field. If search
  starts above1, a correct full search must also consider the lower interval
  before claiming exhaustion. An arbitrary small scan cap would reject otherwise
  valid memory maps and is not a semantic fix.
- Full-address-space exhaustion is an explicit resource failure, not successful
  execution with overwritten data. For realizable sparse finite maps, zero
  pairs exist outside populated cells; no secret/prover assertion may simply
  assume a chosen address is free.
- No public I/O, source helper, inline asm or external target operation may run
  while the temporary frame exists. Internal helper labels must not collide with
  user labels, and their own stack accesses must not recursively need this frame.

The visible-memory invariant is extensional cell values, including zero cells
that were absent from native initial RAM. Restoring zero can leave a zero entry
in a host map; source reads observe the same value. The standard adapter has no
initial-RAM map, but the machine test should include native nondeterministic RAM
with occupied candidate cells, as well as explicit source writes and reads.

Hoisting a persistent scratch frame to entry is **not** transparent: later
arbitrary source RAM or inline asm could read/write those live cells. Neither
“the cells were initially zero” nor eventual restoration fixes that intermediate
observability. The same issue affects any existing inline-asm spill path that
keeps caller locals in RAM across arbitrary user assembly; that separate contract
is under the typed owner's review.

Scanning adds data-dependent runtime cost: O(cells searched + stack depth), with
extra restore writes. Dense occupied ranges and repeated accesses must be
benchmarked, not hidden behind the old static legalized-instruction count. A
static estimate cannot be called exact without a justified bound on search.
This is backend temporary storage, not a new source heap API or an excluded
source address range. The memory/cost documentation must state those distinctions.

Acceptance should additionally seed candidate RAM with nonzero sentinels and
zeros, displace zero-valued words, perform repeated/nested deep accesses, and
check every initialized RAM cell plus relevant zero cells after each operation.
Test dynamic source addresses and the exact FINAL6 counterexamples. No code
changes or new archive validity claims were made by this design review.
