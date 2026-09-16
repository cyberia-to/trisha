# Independent struct-literal correction review

Date: 2026-09-12. Status: four persistent regressions independently rerun and pass.
The implementation and tests were written by the typed-TIR owner; this reviewer
inspected them and executed them without changing their sources or expectations.

The original accepted-source defect constructed literal fields in textual order
while reads/calls used declaration layout: Pair{b:19,a:7} for declaration{a,b}
could produce1907 instead of719. The corrected shared TIR builder resolves the
qualified declared struct, requires exactly one initializer for every declared
field, evaluates values in declaration order, and aggregates their actual word
widths. Nested aggregates retain that order recursively. This matches the now
explicit contract in Trident `reference/language.md`: field expression effects
also occur once in declaration order, regardless of literal spelling order.

Inspection of `trident/src/ir/tir/builder/expr.rs` confirms lookup by declared
field name before evaluation. The validated field-set invariant justifies the
subsequent lookup. This does not rely on guessing a struct by its total width.
Malformed raw builder input emits an ERROR marker; Trisha's recursive checked
lowering rejects these markers instead of turning an unresolved name into a
stack duplicate or zero value. The guard remains enabled.

Independent run of `rs/tests/struct_literal_layout.rs` passed all4 tests:

- Reordered literal through local reads, parameter passing and return:719 three
  times, in both source profiles.
- Imported nested mixed-width struct return and dynamic array selection:
  [765,17] and[1365,17], in both source profiles.
- Nested field effects and input consumption: exact[1,2,3,7,19,31,43], proving
  declared-order evaluation once and preserving the later input word.
- Checked raw lowering rejects unresolved variable, falsely qualified constant,
  missing field and duplicate field ERROR markers.

Receipt: `/tmp/trisha-terminal-struct-review.log`, run together with terminal,
generic and previously failing std/compiler integration cases (28 total passes).
No new proof was generated for this independent struct review. Broader release
verification remains recorded by the implementation owner and root separately.
