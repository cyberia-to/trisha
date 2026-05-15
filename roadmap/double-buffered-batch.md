---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
status: open
---
# double-buffered batch verification

current batch verification uses `thread::scope` — parallel but no GPU overlap between proofs. double-buffering pipelines CPU decode of proof N+1 while GPU folds proof N.

## tasks

```
G5.1  two sets of FRI fold buffers (ping-pong)
G5.2  pipeline: CPU prepare → GPU fold → CPU verify, overlapped
G5.3  benchmark: batch of 4, 8, 16 proofs, speedup vs sequential
```
