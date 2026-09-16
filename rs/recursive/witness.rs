//! Canonical bounded witness encoding for the owned Triton recursive verifier.
use tasm_lib::verifier::stark_verify::StarkVerify;
use trident::runtime::ProgramInput;
use triton_vm::prelude::*;

pub const SCHEMA_VERSION: u64 = 1;
pub const MAX_CLAIM_WORDS: usize = 1 << 17;
pub const MAX_PROOF_WORDS: usize = 1 << 20;
pub const CLAIM_ADDRESS: u64 = 1 << 25;
pub const PROOF_ADDRESS: u64 = 1 << 24;
pub const CONTROL_ADDRESS: u64 = 1 << 26;

/// The commitment binds every encoded claim field, including all public IO lengths.
pub fn claim_commitment(claim: &Claim) -> Digest {
    Tip5::hash(claim)
}

/// Encode an actual proof for the caller's explicit expected claim.
/// The verifier program checks the commitment and proof again during execution.
pub fn encode(expected: &Claim, proof: &Proof) -> Result<ProgramInput, String> {
    if expected.input.len().saturating_add(expected.output.len()) > MAX_CLAIM_WORDS {
        return Err("recursive claim exceeds version1 size limit".into());
    }
    if proof.0.len() >= MAX_PROOF_WORDS {
        return Err("recursive proof exceeds version1 size limit".into());
    }
    let claim_words = expected.encode();
    let proof_words = proof.encode();
    if claim_words.is_empty() || claim_words.len() > MAX_CLAIM_WORDS {
        return Err("recursive claim exceeds version1 size limit".into());
    }
    if proof_words.is_empty() || proof_words.len() > MAX_PROOF_WORDS {
        return Err("recursive proof exceeds version1 size limit".into());
    }
    let claim_roundtrip =
        Claim::decode(&claim_words).map_err(|_| "noncanonical recursive claim")?;
    let proof_roundtrip =
        Proof::decode(&proof_words).map_err(|_| "noncanonical recursive proof")?;
    if claim_roundtrip.encode() != claim_words || proof_roundtrip.encode() != proof_words {
        return Err("recursive witness encoding is not canonical".into());
    }
    let stark = Stark::default();
    crate::convert::verify_native_proof(expected, proof)
        .map_err(|_| "proof does not verify for the expected claim")?;
    let mut nd = NonDeterminism::default();
    StarkVerify::new_with_dynamic_layout(stark).update_nondeterminism(&mut nd, proof, expected);
    let mut secret = vec![SCHEMA_VERSION, claim_words.len() as u64];
    secret.extend(claim_words.into_iter().map(|v| v.value()));
    secret.push(proof_words.len() as u64);
    secret.extend(proof_words.into_iter().map(|v| v.value()));
    Ok(ProgramInput {
        public: claim_commitment(expected)
            .values()
            .into_iter()
            .map(|v| v.value())
            .collect(),
        secret,
        digests: nd
            .digests
            .into_iter()
            .map(|d| d.values().map(|v| v.value()))
            .collect(),
    })
}

/// Accept Warrior's serialized proof format without trusting its claim metadata.
pub fn encode_proof_data(
    expected: &Claim,
    artifact: &trident::runtime::ProofData,
) -> Result<ProgramInput, String> {
    if artifact.format != "stark-triton-v7" {
        return Err("recursive verifier requires stark-triton-v7 proof format".into());
    }
    let expected_metadata = crate::convert::to_trident_claim(expected);
    if artifact.claim.program_hash != expected_metadata.program_hash
        || artifact.claim.public_input != expected_metadata.public_input
        || artifact.claim.public_output != expected_metadata.public_output
    {
        return Err("proof artifact claim differs from caller expected claim".into());
    }
    let byte_limit = (MAX_PROOF_WORDS as u64) * 8 + 8;
    if artifact.proof_bytes.len() as u64 > byte_limit {
        return Err("recursive proof artifact exceeds version1 size limit".into());
    }
    let proof = crate::convert::bytes_to_proof(&artifact.proof_bytes)
        .map_err(|_| "invalid canonical recursive proof artifact")?;
    encode(expected, &proof)
}
