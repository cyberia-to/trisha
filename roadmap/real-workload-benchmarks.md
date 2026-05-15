---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
status: open
---
# real workload benchmarks

the 4.3× speedup was measured on poseidon2.tri (2 ops, trivial trace). actual speedup at scale and for complex programs is unknown.

## tasks

```
G4.1  build benchmark suite:
      - trivial:    2 ops
      - medium:     1K ops
      - heavy:      10K+ ops
      - recursive:  verify-a-proof
G4.2  profile each: wall time, GPU dispatch %, CPU fallback %
G4.3  identify bottlenecks per program size
G4.4  publish results: table of program × GPU speedup
```
