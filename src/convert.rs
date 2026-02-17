//! Type conversion between trident's Vec<u64> and triton-vm's BFieldElement.

use triton_vm::prelude::*;

use trident::runtime::{ExecutionResult, ProgramInput};

/// Convert u64 values to BFieldElements.
pub fn u64s_to_bfes(values: &[u64]) -> Vec<BFieldElement> {
    values.iter().map(|&v| BFieldElement::new(v)).collect()
}

/// Convert BFieldElements to u64 values.
pub fn bfes_to_u64s(bfes: &[BFieldElement]) -> Vec<u64> {
    bfes.iter().map(|b| b.value()).collect()
}

/// Convert ProgramInput to triton-vm's PublicInput + NonDeterminism.
pub fn to_triton_inputs(input: &ProgramInput) -> (PublicInput, NonDeterminism) {
    let public = PublicInput::new(u64s_to_bfes(&input.public));
    let mut non_det = NonDeterminism::default();
    non_det.individual_tokens = u64s_to_bfes(&input.secret);
    (public, non_det)
}

/// Convert triton-vm output to ExecutionResult.
pub fn to_execution_result(output: &[BFieldElement], cycle_count: u64) -> ExecutionResult {
    ExecutionResult {
        output: bfes_to_u64s(output),
        cycle_count,
    }
}

/// Convert a triton-vm Digest to Vec<u64>.
pub fn digest_to_u64s(digest: &Digest) -> Vec<u64> {
    digest.0.iter().map(|b| b.value()).collect()
}

/// Convert a triton-vm Claim to trident's Claim.
pub fn to_trident_claim(claim: &triton_vm::proof::Claim) -> trident::field::proof::Claim {
    trident::field::proof::Claim {
        program_hash: bfes_to_u64s(&claim.input),
        public_input: bfes_to_u64s(&claim.input),
        public_output: bfes_to_u64s(&claim.output),
    }
}

/// Serialize a triton-vm Proof to bytes via bincode.
pub fn proof_to_bytes(proof: &Proof) -> Vec<u8> {
    bincode::serialize(proof).expect("proof serialization should not fail")
}

/// Deserialize a triton-vm Proof from bytes via bincode.
pub fn bytes_to_proof(bytes: &[u8]) -> Result<Proof, crate::error::TrishaError> {
    bincode::deserialize(bytes)
        .map_err(|e| crate::error::TrishaError::Verify(format!("invalid proof bytes: {}", e)))
}
