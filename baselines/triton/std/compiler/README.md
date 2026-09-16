# Self-hosted compiler baseline contract

These three baselines exercise the portable `std.compiler` implementation, not
Trident's Rust parser. They compare complete token records, complete AST records,
and optimized numeric TIR, respectively. Pipeline output is not executable TASM:
its final lowering stage is still unwired in the portable implementation.

The independent hand parser covers one `program NAME fn NAME() -> Field { EXPR }`
with decimal field literals, parentheses, addition and multiplication. It checks
all delimiters and EOF, builds the actual postfix AST with precedence and left
associativity, and rejects inputs outside this grammar. The hand lexer additionally
recognizes identifiers, reserved words and single-character punctuation. Neither
parser fixture coverage nor its presence in the inventory establishes support for
all language constructs. In particular, portable child-list representation for
multiple items, parameters and interleaved statements still needs separate repair
and regression coverage before claiming a complete self-hosted compiler.

The hand pipeline lowers the parsed expression into postfix arithmetic instructions
and emits the same complete numeric TIR envelope as the portable optimizer.
The current portable peephole optimizer does not fold arithmetic constants. Expected records are independently
computed from source bytes by the baseline generator; they are not copied from
compiler output. Inputs are bounded to 1024 ASCII bytes and decimal literals to
32 bits for this reference contract. Rejection vectors assert a real parser/lexer
error, not exhaustion of the VM cycle limit.

Additional remaining self-hosting gaps are explicit return-statement result/type
handling and complete target-owned lowering integration. The new tail-expression
check does not claim to repair every return/control-flow path. The portable
optimizer also retains legacy fixed batching policy that needs a separate
ownership review. The release compiler is the Rust compiler; these arithmetic
fixtures are a regression of the self-hosted prototype, not evidence that this
prototype can compile the complete language or itself.
