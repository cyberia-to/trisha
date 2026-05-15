---
tags: trisha, docs
crystal-type: pattern
crystal-domain: cyber
alias: trisha proof file format, .proof.toml
---
# proof file format

trisha serializes proofs as `.proof.toml` files: a human-readable TOML envelope wrapping base64-encoded bincode proof bytes.

## structure

```toml
[proof]
format = "stark-triton-v2"
program_name = "hello"
cycle_count = 0          # stub: not yet captured from VM
padded_height = 0        # stub: not yet captured from Stark

[claim]
program_hash = [
    "1460305242624279511",   # Goldilocks elements as decimal strings
    "5843494972284683383",   # (exceed i64 range — cannot use TOML integers)
    ...
]
public_input = []
public_output = ["42"]

[data]
proof = "AgIAAAAAAAD..."   # base64(bincode(triton_vm::proof::Proof))
```

## why TOML + bincode

- TOML outer layer: human-readable header, diffable, greppable
- bincode inner layer: triton-vm `Proof` has no stable TOML representation; bincode preserves the exact type without a custom serializer
- base64: TOML has no binary type; base64 is self-describing in the file

## field elements as strings

Goldilocks field elements are u64 values that can exceed `i64::MAX`. TOML integer is signed 64-bit. serializing as decimal strings avoids the range problem while remaining human-readable.

## proving time metadata

`proving_time_ms` is populated at prove time. `cycle_count` and `padded_height` are currently 0 — see [[missing-metadata]].

## roundtrip

```rust
let proof_file = ProofFile::from_proof(&proof, claim, "program_name", proving_time_ms);
let toml_str = proof_file.to_toml_string()?;

// later
let proof_file = ProofFile::from_toml_str(&toml_str)?;
let (proof, claim) = proof_file.to_proof()?;
```

roundtrip is tested in `tests/integration.rs` via `proof_roundtrip_toml`.
