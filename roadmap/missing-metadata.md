---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
status: open
---
# missing proof metadata

the proof file writes `cycle_count = 0` and `padded_height = 0`. triton-vm exposes these but they are not plumbed through.

## tasks

```
C1  capture cycle_count from VM::trace_execution
C2  capture padded_height from Stark internals
C3  write to proof file metadata fields
```
