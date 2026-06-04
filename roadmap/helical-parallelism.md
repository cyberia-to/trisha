---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
status: open
---
# helical parallelism

## goal

reduce the sequential bottleneck in STARK proving by identifying topologically independent segments of the proof graph and processing them simultaneously across coprocessors.

current state: the sequential-grain optimization (14.4s → 3.02s/proof) was the first exploitation of proof graph structure. the next step is multi-strand parallelism at the coprocessor level.

## the topoisomerase model

a STARK proof circuit is a directed acyclic graph of algebraic constraints. segments are topologically independent when they share no witnesses — no value produced by one segment is consumed by the other. these segments can be processed simultaneously, like multiple topoisomerase molecules working different crossing regions of the same DNA strand simultaneously.

the crossing points (shared witnesses) form the sequential spine. the crossing-free segments form the parallel strands. the proof circuit's sequential depth reduces from O(N) to O(crossing number), which for arithmetic circuits with small fan-out is O(log N).

## multi-strand assignment

three strands, one per major coprocessor:

| strand | coprocessor | operations |
|--------|-------------|-----------|
| hash strand | Metal GPU (wgpu/honeycrisp) | Tip5 batch hashing, Merkle tree construction |
| field strand | AMX (honeycrisp phase 2) | field multiplication, NTT butterflies, polynomial evaluation |
| bookkeeping strand | NEON | witness tracking, constraint satisfaction checking, FRI folding |

strands run antiparallel where possible (different cache lines, no false sharing). data flows between strands only at crossing points — the minimal synchronization required.

## implementation sketch

```rust
// proof graph decomposition
let (spine, strands) = decompose_circuit(&aet);
// spine: topologically ordered list of shared-witness steps
// strands: Vec<Vec<Step>> — each inner vec is a crossing-free segment

// assign strands to coprocessors
let gpu_strand = filter_by_type(&strands, StepKind::Hash);
let amx_strand = filter_by_type(&strands, StepKind::Field);
let neon_strand = filter_by_type(&strands, StepKind::Bookkeeping);

// execute crossing-free segments in parallel, then resolve crossings
parallel! {
    gpu_strand.execute(&gpu_ctx),
    amx_strand.execute(&amx_ctx),
    neon_strand.execute(&neon_ctx),
}
// spine steps: sequential, reading outputs from parallel strands
for crossing in &spine {
    crossing.execute(&shared_witnesses);
}
```

## expected impact

current: 3.02s/proof (sequential grain). honeycrisp phase 2 (AMX field ops) alone: estimated 1.5-2.0s. helical parallelism on top: estimated 0.5-1.0s/proof. this reaches the range where interactive proving becomes feasible.

## dependency

requires honeycrisp phase 2 (AMX NTT) and phase 3 (unimem IOSurface zero-copy) to be complete. the zero-copy constraint is critical: between-strand data transfer must not copy through RAM — it must pass through shared Metal heaps to maintain the bandwidth advantage.

## reference

the topoisomerase analogy: [[topoisomerase]] processes DNA crossings one at a time, one ATP per step. the speedup from multiple topoisomerases working different regions is exactly this decomposition. the STARK prover's sequential constraint = the linking number change constraint in topoisomerase.

see [[honeycrisp-npt-mining]] for phase 2/3 status. see [[gpu-proving-at-scale]] for NTT streaming.
