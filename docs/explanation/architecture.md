# Architecture

Trident resolves source modules, checks types and produces target-independent IR. Trisha owns Triton instruction selection, linking, AET costs and runtime execution. Generic bundle metadata comes from `trident::bundle_with_assembly`; the warrior supplies its assembly and cost estimate. Source commands share project/profile/dependency resolution.

```text
source -> Trident resolved modules/TIR -> Trisha lower/link -> ProgramBundle
                                                               |
                                                        run/prove/verify
```

`cli/` is the interface; `rs/` implements the default CPU runtime. `wgpu/` is a separate backend, and `honeycrisp/` provides mining integration. The default command-line proving path uses CPU. Selecting a mining GPU feature does not change the proving backend.

Trisha owns Triton machine metadata in `targets/triton`, its SDK in `lib/vm/triton`, Neptune `.tri` modules in `lib/os/neptune`, network/state descriptors in `networks/neptune`, and hand assembly in `baselines/triton`. Source namespaces remain independent of physical paths. The embedded target package exports the authoritative descriptors and module sources to the compiler. CLI network selection is generated from the same Neptune state manifests; no separate hardcoded state registry is maintained. Runtime capabilities report CPU execution and STARK proving honestly; deployment and unimplemented GPU paths are not advertised as working.

Source execution requires a program entry. Library builds retain their definitions without inventing a halt-only program. Unknown and non-Triton targets fail. Neptune deployment is unsupported and returns an error; dry runs describe the artifact only.

Claims require exactly five canonical Goldilocks hash elements, canonical public input/output and the supported proof format. Incomplete nondeterministic digests are rejected. Batch proving checks unique destination paths before starting work.

Stack IR construction tracks all live operands, including imported named structures and unequal-width tuples. A final pass legalizes deep accesses through compiler-allocated scratch RAM. Return cleanup preserves word order and uses Triton's address-first memory convention. The optimizer must preserve the observable operand stack; equal-depth cleanup swaps cannot be collected ahead of their pops.

`trisha bench` executes unchanged programs using `.bench.toml` reference fixtures. Expected output must match before cycle comparisons appear. Full mode proves and verifies both dimensions. Assertions, recursion, reads and calls are never replaced with dummy operations. Missing or failing fixtures remain unverified and make the full coverage gate fail. Neural results require their own verified fixtures.

## Machine legalization and SDK names

Shared TIR carries unbounded semantic stack operations. Trisha batches counts into Triton instructions of at most five words and legalizes access deeper than register 15. Deep access reserves RAM starting at `2^31`, separate from compiler spill RAM at `2^30` and temporary RAM at `2^29`; source programs must not use compiler-reserved scratch addresses. Actual VM tests check all stack words after deep duplication and swapping.

Use `vm.triton.hash`, `vm.triton.merkle`, `vm.triton.merkle_proof`, and `os.neptune.auth` for the fixed Tip5/Neptune ABI. Old generic aliases are deliberately absent. Historical hand-assembly baseline names are retained as provenance, not as compiler module aliases.

`trisha describe --target triton` and `--target neptune` export schema/compiler API 1 JSON. Module hashes identify the embedded sources, and the package separates compilation identity from deployment-state selection.

The Neptune package excludes the unfinished `os.neptune.proof` verifier. Its previous implementation failed to constrain FRI/OOD/constraint consistency; the source and dependent transaction/proof entry programs are preserved in `examples/experimental/neptune`. Production imports fail closed. Low-level extension-field helpers do not claim complete recursive verification.
