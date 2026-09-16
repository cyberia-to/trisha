//! Trisha-owned official recursive proof verification and witness encoding.
mod witness;
pub use witness::{claim_commitment, encode, encode_proof_data, MAX_CLAIM_WORDS, MAX_PROOF_WORDS};
mod assembly;
pub use assembly::{assembly, ENTRYPOINT};

mod fixed_claim;
pub use fixed_claim::{expected_claim, fixed_claim_assembly};

pub mod neptune;

pub mod program_context;

// Re-export exact pinned engine types used by the public witness API.
pub use triton_vm::prelude::{
    BFieldElement as NativeField, Claim as NativeClaim, Digest as NativeDigest,
};
