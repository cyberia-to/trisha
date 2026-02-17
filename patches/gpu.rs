//! GPU acceleration hooks for triton-vm operations.
//!
//! Register a GPU accelerator via `set_gpu_accelerator()` before proving.
//! The prover dispatches Tip5 hashing, NTT, and Merkle tree construction
//! to the GPU when available.

use std::sync::OnceLock;

use twenty_first::math::ntt::intt;
use twenty_first::prelude::*;
use twenty_first::util_types::merkle_tree::MerkleTree;

/// Trait for GPU-accelerated operations used during proving.
///
/// Acceleration targets (in order of impact):
/// 1. NTT/iNTT: polynomial interpolation, ~40-50% of prove time
/// 2. Tip5 batch hashing: Merkle tree leaf construction, ~20-30%
/// 3. Merkle tree construction: internal node hashing, ~10-15%
pub trait GpuAccelerator: Send + Sync {
    /// Backend name for diagnostics.
    fn name(&self) -> &str;

    /// Hash multiple variable-length inputs using Tip5.
    fn hash_varlen_batch(&self, inputs: &[&[BFieldElement]]) -> Vec<Digest>;

    /// In-place inverse NTT on a BFieldElement column.
    fn intt_bfe(&self, column: &mut [BFieldElement]) {
        intt(column);
    }

    /// In-place inverse NTT on an XFieldElement column.
    fn intt_xfe(&self, column: &mut [XFieldElement]) {
        intt(column);
    }

    /// Build a Merkle tree from leaf digests.
    ///
    /// Default: delegates to twenty-first's MerkleTree::par_new.
    fn merkle_tree(&self, leaves: &[Digest]) -> MerkleTree {
        MerkleTree::par_new(leaves).unwrap()
    }
}

static GPU_ACCELERATOR: OnceLock<Box<dyn GpuAccelerator>> = OnceLock::new();

/// Register a GPU accelerator for use during proving.
pub fn set_gpu_accelerator(
    accelerator: Box<dyn GpuAccelerator>,
) -> Result<(), Box<dyn GpuAccelerator>> {
    GPU_ACCELERATOR.set(accelerator)
}

/// Get the registered GPU accelerator, if any.
pub fn gpu_accelerator() -> Option<&'static dyn GpuAccelerator> {
    GPU_ACCELERATOR.get().map(|b| b.as_ref())
}
