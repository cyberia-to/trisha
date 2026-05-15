---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
status: open
---
# gpu proving at scale

recursive proof traces (2^25+ rows) have not been tested. the VRAM guards fall back to CPU — for recursive proofs the GPU barely helps. real streaming NTT (four-step FFT) would keep large NTTs on GPU instead of falling back.

## tasks

```
G1.1  build or find a program that generates 2^20+ cycle traces
G1.2  profile: where does time go? NTT? Hash? Merkle? GEMV?
G1.3  four-step FFT: decompose large NTT into GPU-sized sub-NTTs
      - split n-point NTT into sqrt(n) × sqrt(n) smaller NTTs
      - each sub-NTT fits in VRAM, twiddle multiply between stages
G1.4  streaming Merkle: chunk leaf hashing on GPU, build tree levels
      - bottom levels chunked, upper levels fit in single buffer
G1.5  benchmark: GPU vs CPU at 2^20, 2^22, 2^25 trace sizes
```

## depends on

[[proof-merging]] — the recursive verifier generates large traces. G1 is where that pays off.
