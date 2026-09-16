# Triton 7 recursive-verifier dependency

The bootstrap pins `triton-vm`, `triton-air`, `triton-isa`, `triton-constraint-builder`, `triton-constraint-circuit`, `tasm-lib`, and `tasm-object-derive` to **7.0.0**. `twenty-first` is **1.1.0**. The native proof version is **5**; this is distinct from the crate version. Native artifacts use `stark-triton-v7` and reject legacy artifacts.

Published upstream sources:

- [Triton v7.0.0](https://github.com/TritonVM/triton-vm/tree/f54606bf9180bab4ac98a778ba28eeb23de06a86).
- [tasm-lib v7.0.0](https://github.com/TritonVM/tasm-lib/tree/2924deb65975148de986fa79cf765f8371e81c6a).
- [Triton security and proof-version history](https://github.com/TritonVM/triton-vm/blob/v7.0.0/CHANGELOG.md).

Version 7 includes the published AIR soundness fixes affecting earlier versions, including Program Table constraints. Earlier successful version-2 execution and proof tests do not establish soundness of its AIR. Version 2 is not a supported release backend.

`nu patches/tasm.nu` installs the published version-7 crates directly. The historical `tasm-lib-2.0.0-security.patch` is retained only as provenance; bootstrap never applies it. Its static proof-item, vector/polynomial length, and minimum-height guards are already upstream in version 7. `rs/tests/recursive_verifier.rs` retains direct assembly regressions for these attacks.

Warrior additionally rejects noncanonical proof bytes, unsupported native claim versions, and trailing proof-stream items. The last guard aligns native acceptance with the recursive verifier: upstream native verification alone can accept an unused appended item. `rs/tests/proof_consumption.rs` demonstrates the discrepancy and checks owner rejection. CCS and recursive witness adapters use the same canonical native codec and verifier.

```sh
RAYON_NUM_THREADS=4 cargo test -p trisha-rs --release --test recursive_verifier --test proof_consumption --test recursive_witness --test ccs
```

These checks generate real default-security proofs and reject altered program and public IO claims. The expensive outer-proof gate is explicitly ignored in the ordinary suite and must be invoked separately. See [the versioned contract](../docs/reference/recursive-proof.md).
