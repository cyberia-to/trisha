use triton_vm::prelude::*;

use trident::runtime::{ExecutionResult, ProgramInput};

pub fn u64s_to_bfes(values: &[u64]) -> Vec<BFieldElement> {
    values.iter().map(|&v| BFieldElement::new(v)).collect()
}

pub fn bfes_to_u64s(bfes: &[BFieldElement]) -> Vec<u64> {
    bfes.iter().map(|b| b.value()).collect()
}

pub fn to_triton_inputs(input: &ProgramInput) -> (PublicInput, NonDeterminism) {
    let public = PublicInput::new(u64s_to_bfes(&input.public));
    let mut non_det = NonDeterminism::default();
    non_det.individual_tokens = u64s_to_bfes(&input.secret);
    non_det.digests = input
        .digests
        .iter()
        .map(|d| Digest::new(d.map(BFieldElement::new)))
        .collect();
    (public, non_det)
}

pub fn to_execution_result(output: &[BFieldElement], cycle_count: u64) -> ExecutionResult {
    ExecutionResult {
        output: bfes_to_u64s(output),
        cycle_count,
    }
}

pub fn digest_to_u64s(digest: &Digest) -> Vec<u64> {
    digest.0.iter().map(|b| b.value()).collect()
}

pub fn to_trident_claim(claim: &triton_vm::proof::Claim) -> trident::field::proof::Claim {
    trident::field::proof::Claim {
        program_hash: digest_to_u64s(&claim.program_digest),
        public_input: bfes_to_u64s(&claim.input),
        public_output: bfes_to_u64s(&claim.output),
    }
}

pub fn to_triton_claim_native(
    program_hash: &[u64],
    public_input: &[u64],
    public_output: &[u64],
) -> triton_vm::proof::Claim {
    let digest_bfes: [BFieldElement; Digest::LEN] = program_hash
        .iter()
        .take(Digest::LEN)
        .map(|&v| BFieldElement::new(v))
        .collect::<Vec<_>>()
        .try_into()
        .unwrap_or_else(|_| [BFieldElement::new(0); Digest::LEN]);
    triton_vm::proof::Claim::new(Digest::new(digest_bfes))
        .with_input(u64s_to_bfes(public_input))
        .with_output(u64s_to_bfes(public_output))
}

pub fn proof_to_bytes(proof: &triton_vm::proof::Proof) -> Vec<u8> {
    bincode::serialize(proof).expect("proof serialization should not fail")
}

pub fn bytes_to_proof(bytes: &[u8]) -> Result<triton_vm::proof::Proof, String> {
    bincode::deserialize(bytes)
        .map_err(|e| format!("invalid proof bytes: {}", e))
}
