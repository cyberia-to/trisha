---
tags: trisha, docs
crystal-type: pattern
crystal-domain: cyber
alias: trisha GPU backend
---
# GPU backend

The default Trisha CLI executes and proves with the CPU backend. Its optional
`gpu` feature selects Apple mining support; it does not select GPU proving.
The separate `trisha-wgpu` library contains cross-platform GPU hooks and WGSL
kernels. CPU and wgpu use the same canonical proof codec and verifier.

The vendor overlay exposes acceleration hooks to the pinned Triton7 prover.
Each hook must preserve the upstream field/hash semantics and fall back when
unsupported. A compiled shader or available adapter alone does not establish
that a complete proof used every GPU stage correctly. Current end-to-end proof
release receipts refer to CPU unless they explicitly record another backend.

WGSL kernels cover Goldilocks arithmetic, NTT, FRI, matrix multiplication,
Tip5, a separate Poseidon2 experiment and nonce search. Goldilocks words use
low/high u32 halves because WGSL lacks native u64. Triton commitments use Tip5;
a Poseidon2 shader is not interchangeable with the Triton transcript hash.

The Honeycrisp mining library uses acpu Tip5 and affinity helpers only on
Apple Silicon macOS. Other CPU hosts use the official portable Tip5 operations
for the same nonce/hash algorithm. Apple-only dependencies must not be loaded
by a default Linux CPU build. This fallback does not advertise AMX/Metal support
on other hosts.

```sh
cargo build --release --locked -p trisha
cargo check --workspace --all-features --locked
```

The first command builds the normal CPU warrior. `--no-default-features` builds
the restricted mining CLI without the Trident warrior commands; it is not the
option for a complete CPU warrior. Apple GPU mining may be selected explicitly
with `--features gpu` on a supported host.

Performance claims need a pinned program, input, backend/device, dependency
revision and real proof verification. Unqualified timings from the earlier
GPU document are retained as unverified historical claims in
[audit/gpu-claims.md](../../audit/gpu-claims.md); they are not release benchmarks.
