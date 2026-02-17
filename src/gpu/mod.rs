//! GPU backend abstraction for accelerating trace generation, proving,
//! and verification on Triton VM.
//!
//! The `GpuBackend` trait defines four operations that can be offloaded
//! to GPU hardware. The CPU fallback delegates to triton-vm's built-in
//! implementations. The wgpu backend uses custom WGSL shaders for
//! Goldilocks field arithmetic (NTT, Poseidon2, FRI).

pub mod cpu;

use triton_vm::prelude::*;
use triton_vm::proof::Proof;

/// Backend for GPU-accelerated operations on Triton VM programs.
///
/// All methods have CPU fallback implementations. GPU backends
/// accelerate the hot paths: NTT (proving), Poseidon2 (Merkle trees),
/// and FRI evaluation (verification).
pub trait GpuBackend: Send + Sync {
    /// Backend name for diagnostics.
    fn name(&self) -> &str;

    /// Execute a program and return output + cycle count.
    ///
    /// GPU backends can accelerate trace generation (AET computation)
    /// by parallelizing constraint evaluation.
    fn trace(
        &self,
        program: &Program,
        public_input: PublicInput,
        non_determinism: NonDeterminism,
    ) -> Result<(Vec<BFieldElement>, u64), String>;

    /// Generate a STARK proof of correct execution.
    ///
    /// This is the most GPU-intensive operation: NTT for polynomial
    /// interpolation, Poseidon2 for Merkle tree construction, and
    /// constraint evaluation over the full trace.
    fn prove(
        &self,
        program: &Program,
        public_input: PublicInput,
        non_determinism: NonDeterminism,
    ) -> Result<(triton_vm::proof::Claim, Proof), String>;

    /// Verify a STARK proof.
    ///
    /// GPU can accelerate FRI query evaluation and Merkle path
    /// verification in parallel.
    fn verify(&self, claim: &triton_vm::proof::Claim, proof: &Proof) -> Result<bool, String>;

    /// Verify multiple proofs in parallel on GPU.
    ///
    /// Critical for mining nodes validating incoming proofs at
    /// network speed. Each proof is independently verified.
    fn verify_batch(&self, jobs: &[(triton_vm::proof::Claim, Proof)]) -> Vec<Result<bool, String>>;
}

/// Select the best available backend.
///
/// Returns wgpu backend if a GPU is available, otherwise CPU fallback.
pub fn select_backend() -> Box<dyn GpuBackend> {
    // TODO: try wgpu backend first when Phase 7 is implemented
    Box::new(cpu::CpuBackend)
}
