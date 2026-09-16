# Neptune contract completion audit

Reference: Neptune0.15.1, revision
`9869b5e35b659dc520fad51ba5a9c812fed46db0`. Native policy is defined in
`neptune-consensus/src/type_scripts/native_currency.rs`, `amount/`,
`native_currency_amount.rs` and the canonical salted-UTXO/transaction-kernel
codecs. The account-tree PLUMB standards are separately specified by Trident's
`reference/plumb-v2.md` (the older v1 references are historical).

## Findings and required contracts

- **Native currency:** the old sample discarded all three public digests and
  summed unauthenticated U32 amounts, emitting a fee. The canonical predicate
  authenticates both complete salted UTXO lists and kernel fee, coinbase and
  timestamp; enforces bounded signed128-bit amounts, exact
  `inputs + coinbase = outputs + fee`, and the coinbase timelock policy. Its
  public claim is kernel/input/output digests, each reversed, and empty output.
  Completion uses a full canonical-program proof with the pinned program hash,
  complete input binding and empty output. A separately compiled port is not
  described as replacing Neptune's consensus-native program identity.
- **Custom token:** private config and private coin witnesses were not bound to
  either public UTXO digest. A one-limb authority hash and an assumption that
  zero can never have a preimage did not implement disabled minting. Completion
  requires canonical salted-UTXO authentication and a versioned, full-digest
  token/config binding; ordinary transfers and authorized supply changes must
  be checked against those authenticated records.
- **Coin/Card:** these are custom PLUMB account-tree transitions, not canonical
  Neptune UTXO scripts. Independent membership paths for old and new leaves
  allowed arbitrary unrelated tree changes. Card mint omitted non-membership,
  Card burn did not constrain the new root, Card config update did not bind a
  new config, and unknown opcodes succeeded. These must be corrected for all
  five operations, not hidden behind a successful amount/helper vector.

## PLUMB v2 transition revision

The new normative version uses five-word Digest authorities and creator
identity, with explicit all-zero disabling. Domain-separated core hashes bind
full authority/configuration digests through Tip5 pairs; the versioned empty
leaf is `H(0,0,0,0,0,0,0,0,2,0)`. Depth20 direct nonzero IDs bind each leaf to its
unique index. Every update consumes exactly20 sibling digests and recomputes
both roots using those same siblings. Pay chains two distinct leaf updates;
Card mint proves an empty slot and burn restores that empty slot. Numerical
state is checked as U32 before and after arithmetic.

Card configuration update binds the new public digest and preserves the tree.
Card mint binds its cap to the full public metadata digest and binds the full
creator authority to the authenticated mint authority. These protocol repairs
intentionally require new witnesses. Old v1 sources remain under
`examples/experimental/neptune/plumb-v1/`, with explicit known defects.

Hook/controller IDs are emitted requests for external proof composition, not
proofs of those predicates. The transition alone does not establish trusted
clock/genesis/supply/current-state binding or update a Neptune UTXO. Integrating
verifiers must bind these public values and discharge every requested proof.

## Validation gates

Every operation needs a complete positive state-transition vector and negatives
for changed roots, paths, identities, configuration/authority, arithmetic and
operation-specific policy. Native/custom token tests must reject substitutions
of the actual committed UTXO/kernel data. No negative-only fixture closes a
baseline; the43-file inventory is unchanged. Functional tests are not production proof evidence; final proofs use Triton7.

## Completed execution checkpoint (Triton7, compiler API2)

The19 maintained fixtures covering Coin/Card's11 complete transitions, v2 shared
configuration, custom transfer/mint/burn and forged-selfhash rejection, and a
real canonical NativeCurrency proof plus changed-input rejection execute
correctly in both compiled and independent hand implementations. Log:
`/tmp/neptune-complete-baselines.log` (local receipt, not a distribution artifact).
PLUMB tests additionally exercise both source profiles, all operation flags,
creator/cap bindings, root/path/authority substitutions and arithmetic policy;
custom tests rebind malformed nested codecs to valid public hashes before
requiring rejection. Host canonical-codec bytes match the pinned upstream
`BFieldCodec` oracle. These checks do not replace the separate full-STARK gate.

The fresh canonical NativeCurrency proof checks10 input coins =7 output coins
+3 kernel-authenticated fee coins. Its canonical trace is2345 CPU cycles,
padded16384; the complete recursive source/reference wrappers execute in
578365/578310 cycles, padded1048576. The pinned consensus program itself binds
coinbase/fee/timestamp and signed128-bit amount rules. In particular its coinbase
branch requires at least half total output to be time-locked, as enforced by the
actual canonical assembly; a simplified “half coinbase” description would be
inaccurate. Full SingleProof validation remains separate.
