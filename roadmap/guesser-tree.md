---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
status: open
---
# guesser tree

`mine()` is brute-force flat search (256K nonces/batch). neptune mining needs a tree structure with ~40GB of intermediate state. the tree enables pruning and checkpoint/resume for long searches.

## tasks

```
G2.1  study neptune guesser tree spec (SWBF, M=29 parameters)
G2.2  design GPU-friendly tree layout (breadth-first, level buffers)
G2.3  implement tree node hashing shader (Tip5 over tree paths)
G2.4  host-side tree management: allocate levels, stream to GPU
G2.5  unified memory path (Apple) vs PCIe streaming (discrete GPU)
G2.6  benchmark: flat search vs tree search at various difficulties
```
