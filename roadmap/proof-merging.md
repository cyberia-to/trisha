---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
status: open
---
# proof merging

`trisha merge` does not exist. the trident programs (`recursive_verifier.tri`, `proof_aggregator.tri`) compile but have never been run end-to-end with actual inner proof data as secret input. this is the largest single proof workload — proof-that-verifies-proof.

## tasks

```
G3.1  wire proof bytes into ProgramInput.secret for recursive verifier
G3.2  trisha merge <proof1> <proof2> → runs proof_aggregator, outputs outer proof
G3.3  test: prove poseidon2.tri, then prove the verifier of that proof
G3.4  profile the recursive proof: expected 2^25+ cycles
G3.5  optimize: this is where [[gpu-proving-at-scale]] pays off
```
