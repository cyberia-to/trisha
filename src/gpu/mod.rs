//! GPU backend abstraction for accelerating trace generation, proving,
//! and verification on Triton VM.
//!
//! The `GpuBackend` trait defines four operations that can be offloaded
//! to GPU hardware. The CPU fallback delegates to triton-vm's built-in
//! implementations. The wgpu backend uses custom WGSL shaders for
//! Goldilocks field arithmetic (NTT, Poseidon2, FRI).

pub mod cpu;
#[cfg(feature = "gpu")]
pub mod tip5_accel;
pub mod wgpu_backend;

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
/// Tries wgpu first (Metal/Vulkan/DX12). Falls back to CPU if
/// no GPU is available or shader compilation fails.
///
/// When GPU is available, also registers a `GpuAccelerator` with
/// triton-vm so the prover dispatches Tip5 hashing to the GPU.
pub fn select_backend() -> Box<dyn GpuBackend> {
    #[cfg(feature = "gpu")]
    {
        if let Some(backend) = wgpu_backend::WgpuBackend::try_new() {
            eprintln!("GPU: {}", backend.adapter_info());

            // Register Tip5 GPU accelerator with triton-vm's prover.
            // Needs its own device from the same adapter.
            if let Some(accel) = wgpu_backend::create_tip5_accelerator() {
                match triton_vm::gpu::set_gpu_accelerator(Box::new(accel)) {
                    Ok(()) => eprintln!("GPU: Tip5 accelerator registered"),
                    Err(_) => eprintln!("GPU: Tip5 accelerator already registered"),
                }
            }

            return Box::new(backend);
        }
    }
    Box::new(cpu::CpuBackend)
}
