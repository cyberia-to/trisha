# Independent terminal-return review

Date: 2026-09-12. Status: reviewed cases pass; owned changes stable.
No heavy proof was executed for this gate. Frozen archives were not changed.

Scope: ordinary and imported Trisha functions ending in If/Match, nested locals,
explicit early returns, aggregate results wider than the register window, and
intermediate branch/loop value disposal. Independent tests live in
`rs/tests/terminal_returns.rs`; the existing `early_return.rs` covers additional
explicit exits. Root separately reviews native Nox terminal normalization.

## Finding and correction

The broad Trisha workspace run reported four compile failures in
`compiler_pipeline` and `triton_audit_stdlib` after ERROR markers correctly became
fatal. Shared TIR `build_stmt` compared result widths of every IfElse, including
intermediate statement branches. Such branches can legitimately have distinct
tail value widths: those values are evaluated for effects and discarded.

The owner authorized the reviewer to correct this boundary. The change in
`trident/src/ir/tir/builder/early_return.rs` adds a recursive value-context pass;
`functions.rs` applies it to a cloned function body before existing return
lowering. Only a final If/Match in a value context forwards branch tails.
Intermediate If/Match and all loop bodies turn their tails into ordinary Expr
statements, which evaluate and discard the result. Explicit Return nodes remain
untouched for the existing return-slot/flag mechanism. Function tail expressions
retain their return role. No ERROR guard or actual terminal width check was
weakened, and the pass does not add return-slot overhead to every function.

## Actual execution coverage

Three persistent tests execute the real Triton VM with an independent 100,000
instruction cap in both debug and release source profiles:

1. Nested terminal If, local shadowing, explicit early return and caller sentinel:
   inputs0/1/7 return11/19/26 followed by unchanged97.
2. Imported terminal Match with nested terminal If and explicit return: four
   branches return a22-word aggregate, preserve every distinct array element and
   the caller's sentinel. Pair results are[11,13], [17,19], [23,29], [43,31].
3. Intermediate If and Match with differing tuple/scalar tails, plus loop tails:
   effects occur exactly once in the selected branch, loop effects occur twice,
   discarded values do not corrupt the final31 or caller97. Exact outputs are
   [11,17,23,23,31,97] and[13,19,23,23,31,97].

## Verification receipt

`/tmp/trisha-terminal-struct-review.log` records the release test invocation:

- `compiler_pipeline`:3 passed (both originally failing cases repaired).
- `triton_audit_stdlib`:13 passed (both originally failing cases repaired).
- `terminal_returns`:3 passed.
- `struct_literal_layout`:4 passed.
- `imported_generics`:5 passed; its separately proven gate intentionally ignored
  in this non-proof invocation.

Total:28 passed,0 failed,1 intentionally ignored proof test, no compiler warnings.
This is a bounded owner review, not a replacement for the root's full workspace
run or independent execution-proof relation verification.

The existing `rs/tests/early_return.rs` was then independently rerun after the
value-context change:9 passed,0 failed (`/tmp/trisha-terminal-existing-returns.log`).
This includes nested aggregate exits, loop returns, caller preservation and
skipped effects. Thus the two invocations total37 passes with the same single
intentionally ignored proof gate; no proof workload was started.
