# Independent typed Triton entry ABI review

Reviewed `docs/reference/triton-entry-abi.md`, shared TIR EntryParameters and
builder layout emission, Trisha entry/target-call/triton/linker lowering, the
neural graph mapping, and `rs/tests/entry_abi.rs`. No implementation edits or
heavy proof were made by this review. The owner's separately completed actual
proof is distinct evidence.

## Concrete finding

The original checked raw-TIR validation resets structural context on recursive
calls. `rs/lower/target_call.rs::validate_target_calls` recursively calls itself for
If/Loop/ProofBlock bodies, each time invoking `entry::validate` with fresh
in_function=false and seen=false. Thus a nested body containing
EntryParameters followed by Entry passes the supposedly program-only admission,
including when nested within a function. Top-level adjacency checks alone do
not reject it. The same reset permits nested Entry without metadata.

This is a robustness defect in the advertised fallible raw-TIR lowering API;
no route from checked source to such malformed TIR was demonstrated. Reported
to root and the Trisha owner. **Resolved and independently checked:** the owner added one contextual
structural walk, rejecting entry metadata and bare Entry in nested bodies and
function scopes, and separated target-call recursion from that walk. Duplicate
entries and unresolved/mispaired signatures reject. The added regression covers
20 nested placements plus malformed cases and a valid top-level control.
Independent final execution passed that regression and all five source ABI
tests; no implementation edits were made by this reviewer.

## Confirmed source and lowering invariants

- Shared metadata lists primitive leaves in parameter declaration order. Named
  struct fields recurse in declaration order; tuples and arrays recurse in
  increasing element order. Digest/XField use resolved target widths, without
  embedding Triton instructions in the compiler.
- Metadata is emitted only for active executable main. Libraries receive no
  implicit public reads, and normal calls to an imported function named main
  use the usual caller layout.
- Trisha reads each leaf once in source order, leaving earlier leaves deeper
  on the operand stack. This matches the ordinary typed argument convention.
  The stack register window is an access limit, not a16word maximum stack; the
  function's existing spill logic handles wide aggregates.
- Bool validation preserves the original leaf while asserting x(x-1)=0. U32
  validation splits a canonical field and asserts the high limb is zero while
  preserving the low limb. These checks run even for unused parameters.
  Missing stream words reject. Host Field canonicality remains the shared
  input-codec boundary; native BFieldElement values are already field elements.
- Explicit pub_read consumes the remaining stream after all entry leaves.
  Main's return value is not silently written to public output. The adapter
  therefore does not invent a nox-style result ABI for Triton.
- The linker retains the emitted program prelude rather than regenerating an
  untyped main call. Reachability still starts at the mangled program main.
  Native program-digest capture is prepended before parameter reads, preserving
  the initial VM stack digest for reachable context operations.
- Unresolved leaf types reject through checked lowering. Low-level infallible
  lowering remains a prevalidated-TIR interface; its panic on unresolved leaves
  is not a recoverable public input boundary.
- The neural graph maps EntryParameters to the existing structural Entry kind,
  preserving opcode numbering. It does not encode the leaf types/count in its
  feature vector and does not model these reads as data producers. This limits
  its representation for future learned entry transformations. The current
  speculative lowering emits the classical operations unchanged, so this is
  not an observed semantic omission or a claim of proven neural equivalence.

## Execution coverage

The owned tests exercise declaration order and remaining-stream reads; missing
inputs;33words spanning a struct, tuple,20element array, Digest and XField;
invalid Bool/U32 values including unused leaves; nested imported structs;
normal imported main calls; zero-parameter compatibility; and non-public main
returns, under both debug/release source profiles. The ignored proof test binds
actual input/output/program hash and is not counted in the ordinary run.

Independent current execution receipt: `cargo test --release --locked -p
trisha-rs --test entry_abi` passed **6 tests**, zero failures, **1 explicitly
ignored proof test**, exit0 and zero Rust warnings. Log:
`/tmp/entry-abi-independent-final.log`. The proof test was not rerun by this
review; its separate owner receipt remains required. The review
makes no universal claim for arbitrary malformed raw TIR, unbounded aggregate
allocation, or future neural replacement paths beyond the stated checks.
