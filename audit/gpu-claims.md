# Historical GPU claims — 2026-09-12 review

The former GPU explanation reported a two-operation poseidon2.tri on M1 Max:
CPU proving1.2s, GPU280ms,4.3x; mining2M versus24M nonces/s,12x. No reproducer,
proof/device receipt or revision accompanied those numbers. They are retained
here as historical unverified claims and must not be presented as measured
results for Triton7 or the current CPU-default CLI.

The same document claimed seven fully accelerated stages, fused encoder
submission, fixed staging/buffer pools and GPU enabled by default. Current
release validation must establish each implemented path from actual code and
proofs; shader inventory and target availability alone do not do so.
