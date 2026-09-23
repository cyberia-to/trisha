# Triton typed program entry ABI

For an executable `program`, `main` parameters consume a prefix of the public
input stream in declaration order. Each parameter is flattened recursively:
struct fields use declaration order, tuple/array elements use increasing index,
and Digest/XField words use source limb/coefficient order. Field words must be
canonical; Bool leaves must be0 or1 and U32 leaves must fit32bits. Missing words
or invalid leaves fail execution and cannot produce a valid proof.

The adapter places this prefix on the operand stack using the ordinary typed
function-call layout, then invokes `main`. Later explicit `pub_read` operations
consume the remaining stream. The adapter applies only to executable entry;
library functions named `main` and ordinary calls retain the usual caller ABI.

Only explicit `pub_write` operations contribute public output. A return value
from `main` remains an ordinary function result, not an implicit stream write.
Zero-parameter entries retain their existing behavior. Nox uses its separate
subject/result ABI and does not receive this Triton stream adapter.

Shared compiler metadata describes resolved primitive entry leaves without
Triton instructions. Trisha owns input marshalling, leaf checks and linkage.
