# Neptune SDK

These modules are supplied only by `trisha describe --target neptune`. The bare Triton package does not provide Neptune imports. Machine bindings live in `lib/vm/triton`; network and state descriptors live in `networks/neptune`.

The current SDK contains kernel/Merkle authentication helpers, preimage authorization helpers, extension-field and RAM inner-product operations, UTXO helpers, and source examples of token standards, lock scripts and type scripts under `examples/neptune`. Compilation coverage is not validation of a live Neptune transaction protocol. Live deployment remains unsupported.

`xfield.xx_dot_step` and `xfield.xb_dot_step` take an `XField` accumulator and two RAM pointers and return the updated accumulator and both pointers. These operations are arithmetic primitives, not complete recursive proof verification.

There is **no released `os.neptune.proof` module**. Its previous `verify_inner_proof` prototype did not enforce the computed FRI/OOD/constraint values and was not a sound verifier. The unfinished source and dependent entry programs are preserved under `examples/experimental/neptune`, excluded from target packages. Imports of that module fail compilation in the production package. This limitation is independent of Trisha's working CPU Triton STARK prover and verifier.

The expert assembly baselines retain historical names and remain unverified without an explicit independent execution fixture. No recursive-proof or transaction-security claim follows from their presence.
