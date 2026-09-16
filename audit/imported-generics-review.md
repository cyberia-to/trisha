# Independent imported generic-function review

Date: 2026-09-12. Status: five independent owner execution/type tests and one genuine proof gate pass;
resource-limit and broad workspace verification belong to the core owner.
The reviewer owns `rs/tests/imported_generics.rs` and this audit only. The core
owner controls typechecking, specialization and module linking. Frozen release
archives are unchanged.

The original failure occurs before owner lowering: ModuleExports carried only
resolved signatures, so foreign size-generic calls lost their unresolved
parameter/return declarations. Fixing that export alone is insufficient: the
concrete body must be checked in its defining lexical environment, and all
reachable nested instances must be emitted with correct call routing.

Review requirements communicated to the implementation owner:

- Bind named types, private helpers and constants to the defining module. A
  same-named caller constant or helper must not alter specialization semantics.
- Preserve generic size-parameter shadowing and resolve compound size expressions
  with checked arithmetic, including signature constants from the owning module.
- Infer nested callee sizes from actual argument types, not from matching names
  in the caller's generic substitution map.
- Associate calls with the concrete caller specialization and stable source
  identity; one shared cursor or source span alone cannot distinguish different
  instantiations of the same generic body.
- Use collision-free deterministic labels. A user function named `value__N2`
  cannot alias a generated instance of `value<2>`. Module identities must not
  collapse merely because dots become underscores.
- Select only cfg-active bodies. Reject concrete return/body type errors before
  emitting assembly. Preserve visibility for callers while allowing an owned
  generic body to invoke its private helpers.
- Bound recursive instantiation and instance count. Memoizing exactly repeated
  instances does not terminate a recursive sequence N, N+1, N+2. Recursion must
  be rejected with a diagnostic rather than cause host stack/memory exhaustion.

The durable owner execution tests cover both debug and release source profiles:
lexical private helpers/constants/structs; same function names in two modules;
nested explicit and inferred instantiations of asymmetric array sizes; a
20-word array return; concrete invalid Field/Bool body; cfg selection; a user
name resembling a generated label; and deterministic assembly re-emission.
Expected numeric outputs are computed directly from source arithmetic, not
copied from the compiler. No VM or proof pass is claimed until recorded below.


## Findings corrected during this review

The first real owner run found generated definitions such as
`selected__trident_mono_0` but calls to `selected____trident_mono_0`.
The owner now allocates collision-checked names without the linker's reserved
leading-underscore convention. The final test calls a user-defined
`trident_mono_0` alongside generated instances and checks both results.

Bare module constants had an independent preexisting codegen defect:
`helper(x) { x + OFFSET }` emitted `x + x` through the missing-variable fallback.
The owner corrected constant lookup after local/spilled binding lookup. Actual
execution checks foreign private OFFSET=7, another module's OFFSET=19, caller
OFFSET=1000, and an argument that shadows OFFSET.

The next run correctly produced six outputs then rejected a valid call to
`padded<1>([3,5,7])`: its declared `[Field; N+FIXED]` used lexical FIXED=2 in
checking but left it unresolved in TIR layout, treating the input as one word.
The owner now substitutes lexical constants into concrete AST types and bodies,
with generic parameters taking precedence. The unchanged test now produces307
and demonstrates that caller FIXED=17 is not captured.

Canonical generic definitions now carry their owning module identity into
specialization. This removes the initially reviewed global-first-short-alias
routing ambiguity. Concrete functions remain in their owner module and have
unique allocated names; call rewrites use the concrete function name and source
span. Generated ordinary bodies are rechecked before either target sees them.

## Independently executed final receipts

Command:
`cargo test --release --locked -p trisha-rs --test imported_generics -- --nocapture`

Result: **5 passed, 0 failed, 1 intentionally ignored serialized proof test**.
All positive cases execute the real Triton VM in both debug and release source
profiles. The invalid Field/Bool body is rejected for the expected type mismatch
in both profiles. The expected negative diagnostic appears in the log and is
not a test failure. Log: `/tmp/trisha-imported-generics-review.log`.

The separate genuine proof command used `RAYON_NUM_THREADS=4` and
`TVM_LDE_TRACE=no_cache`, with `--ignored` selecting
`genuine_proof_binds_imported_generic_to_program_input_and_output`.
Result: **1 passed**, 0.24 s test runtime. It generates a fresh
`Stark::default()` proof of compiled imported `fold<2>` on public input `[3,5]`,
asserts output42, verifies through the hardened native verifier, then rejects
the same proof with changed input, changed output and changed program digest.
Log: `/tmp/trisha-imported-generics-proof.log`. No security parameters were lowered.

The final arithmetic oracles are:
`[42,54,426,768,1155,3001,307,6]` for the lexical/explicit case;
`[754,1138,1007,2007]` for nested inference and name collisions;
twenty unchanged distinct input words for the aggregate-return case; and10/22
for cfg-selected debug/release bodies. Two recompilations in each profile have
byte-identical assembly. This review does not claim exhaustive program
correctness or replace the owner's broader compiler regression suite.
