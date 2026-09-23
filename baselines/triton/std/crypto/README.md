# Additional crypto baseline contracts

`ecdsa.tasm` implements the public module's actual curve-agnostic scalar policy
and encoding helpers. `valid_range` requires `0 < r,s < order`; `is_low_s`
requires `0 < s <= floor(order/2)`. The latter independently checks s and does
not replace the r check or elliptic-curve signature verification. Fixtures
include the secp256k1 order, both sides of its half-order boundary, zero and
out-of-range scalars, a carry across four limbs, an even order, and a complete
16-limb signature roundtrip. Input limbs are range checked, never truncated.

`poseidon2.tasm` is the historical **custom** eight-lane arithmetic permutation
with caller-provided constants and custom matrices. Both full output states are
compared against independent modular integer arithmetic with 86 nonzero
constants. These fixtures establish arithmetic agreement, not a standard
Poseidon2 instantiation or cryptographic security. The separate `poseidon.tasm`
contains the pinned standard Poseidon2-HL contract.

`keccak256.tasm` executes all 24 rounds of Keccak-f[1600], and both fixtures check
all 25 lanes (50 U32 outputs), including zero and distinct nonzero lanes. The
independent Python oracle uses 64-bit integers; the hand assembly uses explicit
32-bit RAM operations. The algorithm and tables follow the [Keccak team's
specification summary](https://keccak.team/keccak_specs_summary.html). This module
exposes the permutation; message padding and Ethereum trie verification are
separate obligations.

The generator scripts do not invoke Trident or copy compiled assembly. Positive
vectors contribute to the unchanged 43-file inventory only after actual VM
execution succeeds. Proof coverage additionally requires `bench --full`.

The Keccak benchmark driver calls `keccak_f1600_in_ram(state_addr, scratch_addr)`.
Its caller owns a 50-word state and a disjoint 70-word scratch region. Both
exclusive ends must fit U32, and every input limb must fit U32. Overlap, wrapping
addresses and oversized limbs are rejected before the permutation. The function
writes only these regions; it replaces the full state with all 24-round output
lanes. This explicit RAM API avoids copying a 50-word aggregate at every step.
The existing struct API remains separately regression-tested against the same
complete independent outputs; its execution cost is not presented as the RAM
API's benchmark result.
