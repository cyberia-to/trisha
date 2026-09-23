---
tags: trisha, docs
crystal-type: pattern
crystal-domain: cyber
alias: trisha proof file format, .proof.toml
---
# Proof file format

Trisha stores a native Triton proof in a `.proof.toml` envelope. The current
format is `stark-triton-v7`: pinned Triton VM7.0.0, native claim version5,
default upstream security parameters. Earlier formats require regeneration.

```toml
[proof]
format = "stark-triton-v7"
program_name = "hello"
cycle_count = 42
padded_height = 256
proving_time_ms = 1000

[claim]
program_hash = ["1", "2", "3", "4", "5"]
public_input = []
public_output = ["42"]

[data]
proof = "base64-encoded-native-proof-bytes"
```

These values illustrate the schema; they are not a proof or measured result.
Real metadata comes from the executed trace and proof generation timer.
Cycle count, padded height and timing are informational envelope fields; the
cryptographic verifier authenticates the actual native claim and proof.

The claim contains the five-word native `Program.hash()`, complete public input
and complete public output in VM stream order. Goldilocks elements are unsigned
decimal strings because TOML integers cannot represent every canonical field
value. Claim fields must be less than the Goldilocks modulus. The format selects
the native claim version; untrusted metadata cannot override it.

The decoded proof bytes retain the fixed-width bincode representation used by
earlier implementations: one little-endian u64 field count followed by exactly
that many little-endian u64 canonical field values. The owner-side codec rejects
modular aliases, inconsistent lengths and trailing bytes. Native proof bytes
and the outer TOML input are each bounded at64MiB before deserialization.

All default-security verification paths use the same owner-side checks: native
version5, a leading supported padded-height item, a FRI domain representable by
u32 indices, exactly the expected number of proof items, and upstream verification
against the complete expected claim. This also rejects appended proof items
that upstream native verification alone tolerates but recursive verification
rejects. A well-formed file is accepted only if its proof verifies.

`rs/tests/proof_wire.rs` tests canonical binary encoding;
`rs/tests/proof_consumption.rs` tests native/recursive acceptance consistency and
hostile height handling. CLI tests exercise TOML proof roundtrips and rejection
of changed claims in fresh processes.
