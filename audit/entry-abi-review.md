# Entry ABI review: Nox subject/result versus Triton streams

## Conclusion

A returning Triton `main` producing no public output is consistent with the
canonical streaming I/O contract. A parameterized Triton `main` silently reading
initial VM stack registers is a real accepted-source correctness defect. These
are separate findings; the first does not excuse the second. No compiler,
backend, frozen archive or contract was changed during this review.

Trident `reference/language.md` section6 explicitly distinguishes Triton's
`pub_read`/`pub_write` streams from Nox's subject/result ABI. Section1 says an
executable must have `fn main()` but does not explicitly reject typed parameters
or define how a Triton entry receives them. General type checking accepts those
signatures. The README's returning `main` example explicitly targets Nox.
The available docs therefore do not establish that silently uninitialized
Triton parameters are a supported alternate calling convention.

## Actual lowering and runtime

Shared TIR emits `Entry("main")` for a program. Function lowering registers all
parameters with the assumption that a caller already placed them on the real
stack (`src/ir/tir/builder/functions.rs`). Both the owned Triton Entry lowerer
and multi-module linker emit only `call main; halt`; neither loads parameters
nor writes return values. The runtime places `ProgramInput.public` in Triton's
separate `PublicInput` stream, not on the operand stack.

Upstream Triton7 initializes16 operand registers, with the reversed program
Digest in the bottom5 and zeros above it. A small entry parameter consequently
reads zero; wider signatures can reach other initial registers or underflow.
Function cleanup can also pop below the VM's minimum stack depth. This is not
merely unused user input or an intentionally discarded return value.

Nox's `compile_fn` explicitly binds its parameters to the supplied subject
`[param_last [... [param0 0]]]`; its reduction result is the function result.
The entry inputs therefore have an actual caller-provided representation there.

## Concrete execution receipts

Small read-only execution probes used the existing frozen v7 executable
`/tmp/trisha-v7-proof-binary/trisha`; no proof or heavy build was run. Sources
remain in `/tmp/trisha-entry-abi-review`.

```trident
program parameter
fn main(n: Field) -> Field {
    assert(n == 0)
    pub_write(n)
    n
}
```

`trisha run parameter.tri --target triton --input-values 7` exits0, prints0,
and executes9cycles. Changing the assertion to `n == 7` fails. A unit-returning
parameterized variant reaches operand-stack-underflow during cleanup.

```trident
program consumed
fn main(n: Field) -> Field {
    let provided = pub_read()
    assert(provided == 7)
    assert(n == 0)
    pub_write(n)
    n
}
```

With public input7 this exits0 and prints0 in17cycles. The explicit stream read
receives7 while the accepted formal parameter still reads an initial zero.
Separately, `fn main() -> Field { 11 }` exits0 with no public output in4cycles;
it contains no `pub_write`, as expected for the stream ABI.

## Proof implications and proposed behavior

Native proofs bind the program Digest and complete public input/output streams.
`challenges.rs` computes the input terminal from every Claim input token; AIR's
cross-table terminal equates it to the processor's consumed-input evaluation.
The first probe leaves input7 unread, so its successful VM run does not imply a
valid proof for that complete Claim. The second probe consumes the input, but
this review did not generate a proof and does not claim verified proof evidence.
In either case, correct proof-to-assembly binding cannot repair an incorrectly
initialized source parameter.

A complete implementation should provide an explicit, target-owned typed entry
adapter for accepted parameterized programs: consume the public-input prefix in
source parameter order, validate Bool/U32 ranges and lower aggregates using the
same canonical calling layout as ordinary typed calls before invoking `main`.
Subsequent explicit `pub_read` calls then consume the remaining stream. This
must be tested with multiple parameters, aggregate/Digest/XField ordering,
insufficient input, narrow-type failures and actual proof/verify binding.

Keep the existing documented Triton output rule explicit: only `pub_write`
creates public stream output; a function return on the operand stack is not
implicitly a verifier-visible result. If a cross-target result-as-output entry
mode is desired, it needs an explicit versioned ABI decision and tests rather
than silently changing every existing returning-main program. Until an adapter
exists, silently accepting uninitialized parameters must not be represented as
release-ready support. Any interim rejection would be a deliberate contract
change, not evidence that the current accepted-source behavior was correct.


## Implemented remediation

The live source now implements the complete parameter adapter described above;
frozen FINAL3 archives remain unchanged. Canonical contract:
`docs/reference/triton-entry-abi.md`. Shared TIR adds resolved primitive
`EntryParameters` metadata; Trisha owns its input reads and Bool/U32 checks.
The linker preserves this executable prelude without applying it to library
functions or ordinary calls. Main return values retain explicit stream-output
semantics.

Actual execution tests pass in debug and release: asymmetric parameters and
remaining input,33-word struct/tuple/array/Digest/XField layout, imported nested
structs, narrow invalid leaves even when unused, missing input, normal library
main calls and zero-parameter behavior. Trisha lib89/89, early-return9/9 and
entry VM5/5 passed without warnings. Generic core metadata1/1 and the compiler's
all-features/all-targets check passed.

The dedicated default-security proof test also passed (3.39s): input
[7,19,1] produces explicit output719; fresh native verification succeeds and
changed input, output and program Digest all reject the same proof. This is
new real proof evidence, unlike the initial read-only probes. Log:
`/tmp/trisha-entry-proof.log`. No outer proof was needed for this bounded gate.
Source-file SHA256 identities and test counts are recorded in
`/tmp/trisha-entry-adapter-receipt.json`. The coordinated compiler API is now3 before the next source distribution;
this report does not
retroactively relabel the preserved FINAL3 artifacts.


Independent review also identified that raw checked lowering reset entry context
when descending into structured TIR. This is fixed: one contextual walk rejects
both typed entry metadata and bare Entry in nested branches/loops/proof blocks,
inside functions, or duplicated/mispaired entries. The new regression covers
20 nested placements plus valid top-level and malformed controls. After the
fix, Trisha lib89/89 and entry/checked-lowering6/6 pass without warnings
(`/tmp/trisha-entry-review-fix.log`). The linker reuses its validated program
reference instead of performing a second lookup with unwrap. No additional
proof was run for this structural-validation-only follow-up.
