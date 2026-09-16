# Executable baseline fixtures

The collection contains 43 manual assembly files. Each `.bench.toml` runs a real compiled source and the referenced manual assembly against an independent expected output. A passing vector covers the behavior exercised by that driver; it does not certify every function in a library or establish a cryptographic security level.

Run `trisha bench baselines/triton --full` to execute, prove and verify both candidates. The command fails if any fixture fails or any baseline lacks a passing positive vector. The original 43-file denominator is preserved. A negative-only fixture never creates positive coverage.

A fixture contains `source`, `hand`, `input`, `output`, optional `target` (default `triton`), `secret`, flattened five-field `digests`, `hand_prefix`, `hand_libraries`, `reference`, `expect_failure`, and `max_cycles` (default1000000). Full Goldilocks values beyond TOML's signed-integer range use quoted unsigned decimal strings. Noncanonical fields and unknown keys are rejected. Instruction parse errors and cycle exhaustion do not count as expected execution rejection.

Drivers call the actual library algorithms. Hand libraries are linked without replacing calls, assertions or reads. Native Tip5/XField/Merkle vectors can be reproduced with `cargo run -p trisha-rs --example baseline_vectors`. The SHA256 manual baseline is generated from the independently written FIPS180-4 algorithm in `scripts/generate_sha256_baseline.py`; its expected double-hash vector comes from Python's `hashlib`.

Neptune predicates bind explicit caller-authorized commitments and versioned program identities. Each fixture documents which relation is proved. Native currency validation is one component of the complete SingleProof transaction graph; state freshness and network admission remain caller/node obligations. Historical incomplete prototypes remain under `examples/experimental` and are not production aliases.

## Recursive proof fixtures

The historical `os/neptune/proof.tasm` and verifier/relay/aggregator baseline paths now implement the Trisha-owned version 1 Triton proof contract. Their source examples live in `examples/triton`; they verify complete default-security proofs against publicly bound full-claim commitments. Configurable prototype FRI rounds are not retained as a security parameter. The 43-file inventory is unchanged.

Generate their native reference witnesses and official hand snippet with:

```sh
RAYON_NUM_THREADS=4 cargo run -p trisha-rs --release --example recursive_baselines
```

The generator never compiles source to obtain expected results. It proves the native program `read_io 1 push 3 add write_io 1 halt` for inputs 2 and 9, checks outputs 5 and 12, and computes full-claim commitments with native Tip5. Proof randomness can change generated witness bytes without changing the relation or expected outputs. Positive fixtures and altered-claim negative fixtures share private streams through `witness_files`; streams are appended in listed order, and public expectations always remain in the individual fixture. Sharing avoids duplicate megabytes of proof tokens.

The generic recursive primitive does not choose a transaction policy. `programs/transaction_validation.tasm` now binds the pinned Neptune0.15.1 HardforkGamma SingleProof program, native version 5, the caller kernel digest reversed as input, and empty output. Its genuine independent fixture includes all four integrity/collector proofs and the mandatory native currency proof before the complete SingleProof. Source and hand execution accept the proof and reject changed kernel, program, output and version.

The optional pinned oracle's `examples/single_proof.rs` generates that proof graph. `cargo run -p trisha-rs --release --example neptune_transaction_fixture -- PATH_TO_SINGLE_PROOF_JSON` verifies the fixed expected claim before regenerating the manual entry and its positive/adversarial fixtures. Full outer proof receipts are tracked separately from execution coverage; the `--full` benchmark verifies both outer proofs.

## Complete Neptune and PLUMB v2 predicates

`standards/coin.tasm` and `standards/card.tasm` implement every PLUMB operation,
including both Card update modes, full five-word authorities, the versioned
configuration and metadata cap, same-sibling atomic root updates, and exact
declaration-order public events. `scripts/generate_plumb_v2_baselines.py` is an
independent RAM implementation; it does not read compiler output. Its reference
vectors come from upstream Tip5 over a separate host sparse-tree implementation
in `rs/tests/support/plumb_v2.rs`. Run the meaningful tests with
`TRISHA_WRITE_PLUMB_FIXTURES=1 cargo test -p trisha-rs --test plumb_v2` to regenerate
all operation fixtures. External hook requests and trusted state/clock/supply
binding remain integrating-verifier obligations, as specified by
Trident `reference/plumb-v2.md`.

`types/custom_token.tasm` authenticates complete canonical Neptune0.15.1 salted
UTXO encodings, selects every coin with its own actual program hash, and checks
full-Digest issuer policy and bounded amounts. It supports ordinary transfers
and authorized mint/burn, with rejection of mixed issuers, malformed codecs,
overflow and forged type selection. The exact admission policy is in Trident
`reference/neptune-custom-token-v2.md`. The independent RAM implementation is
`scripts/generate_custom_token_baseline.py`; the codec vector is cross-checked
against pinned consensus by `tools/neptune-policy-oracle/examples/custom_codec.rs`.

A custom type's program hash differs between source and hand assembly, so its
canonical coin encodings and public UTXO roots must differ too. Explicit
`hand_input`, `hand_secret`, and `hand_digests` override only those streams for
the hand implementation. Such fixtures require `implementation_bound_identity`
to explain the mapping; the runner prints it before execution/proving. This is
a comparison of disclosed, distinct authenticated statements with the same
independent semantic outcome. It is never presented as one identical public
claim. Old fixtures keep identical inputs by default. Regenerate the canonical
positive and wrong-selfhash fixtures with
`TRISHA_WRITE_CUSTOM_FIXTURES=1 cargo test -p trisha-rs --test custom_token_v2`.

`types/native_currency.tasm` verifies a real proof of the complete pinned
Neptune0.15.1 NativeCurrency program, not an unauthenticated sum. Its fresh
canonical10-input/7-output/3-fee proof is generated by the pinned optional oracle,
encoded by `neptune_witness`, and tested against both implementations by
`neptune_native_fixture`. The public statement binds the authoritative program,
version5, all15 native input fields and empty output. The full SingleProof graph
remains a separate required predicate for a transaction.
