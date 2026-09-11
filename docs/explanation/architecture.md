# Architecture

Trident resolves source modules, checks types and produces target-independent IR. Trisha owns Triton instruction selection, linking, AET costs and runtime execution. Generic bundle metadata comes from `trident::bundle_with_assembly`; the warrior supplies its assembly and cost estimate. Source commands share project/profile/dependency resolution.

```text
source -> Trident resolved modules/TIR -> Trisha lower/link -> ProgramBundle
                                                               |
                                                        run/prove/verify
```

`cli/` is the interface; `rs/` implements the default CPU runtime. `wgpu/` is a separate backend, and `honeycrisp/` provides mining integration. The default command-line proving path uses CPU. Selecting a mining GPU feature does not change the proving backend.

Trisha owns Neptune `.tri` modules in `os/neptune` and hand assembly in `baselines/triton`. Compiler target-registry configurations remain available in Trident. Embedded module sources allow both libraries to work independently of the development directory.

Source execution requires a program entry. Library builds retain their definitions without inventing a halt-only program. Unknown and non-Triton targets fail. Neptune deployment is unsupported and returns an error; dry runs describe the artifact only.

Claims require exactly five canonical Goldilocks hash elements, canonical public input/output and the supported proof format. Incomplete nondeterministic digests are rejected. Batch proving checks unique destination paths before starting work.

Stack IR construction tracks all live operands, including imported named structures and unequal-width tuples. A final pass legalizes deep accesses through compiler-allocated scratch RAM. Return cleanup preserves word order and uses Triton's address-first memory convention. The optimizer must preserve the observable operand stack; equal-depth cleanup swaps cannot be collected ahead of their pops.

`trisha bench` executes unchanged programs using `.bench.toml` reference fixtures. Expected output must match before cycle comparisons appear. Full mode proves and verifies both dimensions. Assertions, recursion, reads and calls are never replaced with dummy operations. Missing or failing fixtures remain unverified and make the full coverage gate fail. Neural results require their own verified fixtures.
