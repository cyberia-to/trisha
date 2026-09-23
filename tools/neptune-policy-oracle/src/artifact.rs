//! Portable native artifact for the Trisha CLI; no Trident serialization dependency.
use base64::Engine;
use neptune_consensus::proof_abstractions::tasm::program::TritonProgram;
use neptune_consensus::transaction::validity::single_proof::SingleProof;
use neptune_consensus::type_scripts::native_currency::NativeCurrency;
use std::path::Path;
use tasm_lib::triton_vm::prelude::*;
pub fn verify_native_proof(claim: &Claim, proof: &Proof) -> Result<(), String> {
    use tasm_lib::triton_vm::proof_item::ProofItem;
    use tasm_lib::triton_vm::proof_stream::ProofStream;
    if claim.version != tasm_lib::triton_vm::proof::CURRENT_VERSION {
        return Err("unsupported native proof version".into());
    }
    let stark = Stark::default();
    let stream = ProofStream::try_from(proof).map_err(|_| "invalid proof stream")?;
    // Proof::padded_height shifts by an unchecked proof-supplied u32. Validate
    // the actual leading item before deriving sizes or calling native helpers.
    let Some(ProofItem::Log2PaddedHeight(log_height)) = stream.items.first() else {
        return Err("proof must start with its padded height".into());
    };
    if !(8..32).contains(log_height) {
        return Err("unsupported proof padded height".into());
    }
    let height = 1usize
        .checked_shl(*log_height)
        .ok_or("proof height overflows this platform")?;
    // Native domain construction also uses usize arithmetic. Refuse oversized
    // domains before that arithmetic, including on 32-bit verification hosts.
    let domain_length = height
        .checked_add(stark.num_trace_randomizers)
        .and_then(usize::checked_next_power_of_two)
        .and_then(|length| length.checked_mul(stark.fri_expansion_factor))
        .ok_or("proof domain overflows this platform")?;
    // Native Fiat–Shamir index sampling narrows the domain to u32 with an
    // unchecked expect. The recursive verifier uses the same index width.
    if u32::try_from(domain_length).is_err() {
        return Err("proof domain exceeds native u32 index bounds".into());
    }
    let rounds = stark
        .fri(height)
        .map_err(|_| "invalid default-security FRI parameters")?
        .num_rounds();
    // Fifteen non-FRI items, four round-independent FRI items and two per round.
    // Matches the pinned Neptune0.15.1 transaction verifier and Triton7 prover.
    let expected_items = 19 + 2 * rounds;
    if stream.items.len() != expected_items {
        return Err("proof contains an unexpected number of items".into());
    }
    stark
        .verify(claim, proof)
        .map_err(|_| "proof does not verify for expected claim".into())
}

pub fn write(prefix: &Path, claim: &Claim, proof: &Proof, cycles: u64, proving_ms: u64) {
    verify_native_proof(claim, proof).expect("canonical complete native proof");
    let mut wire = (proof.0.len() as u64).to_le_bytes().to_vec();
    for word in &proof.0 {
        wire.extend(word.value().to_le_bytes());
    }
    let artifact = serde_json::json!({
        "proof":{"format":"stark-triton-v7","program_name":"pinned-neptune-policy","cycle_count":cycles,"padded_height":proof.padded_height().unwrap(),"proving_time_ms":proving_ms},
        "claim":{"program_hash":claim.program_digest.values().map(|v|v.value().to_string()),"public_input":claim.input.iter().map(|v|v.value().to_string()).collect::<Vec<_>>(),"public_output":claim.output.iter().map(|v|v.value().to_string()).collect::<Vec<_>>()},
        "data":{"proof":base64::engine::general_purpose::STANDARD.encode(wire)},
    });
    std::fs::write(
        prefix.with_extension("toml"),
        toml::to_string(&artifact).unwrap(),
    )
    .unwrap();
    if claim.output.is_empty()
        && ((claim.input.len() == 5 && claim.program_digest == SingleProof.hash())
            || (claim.input.len() == 15 && claim.program_digest == NativeCurrency.hash()))
    {
        let digests: Vec<Vec<_>> = claim
            .input
            .chunks_exact(5)
            .map(|chunk| chunk.iter().rev().map(|v| v.value().to_string()).collect())
            .collect();
        let mut commitments = serde_json::json!({"schema_version":1,"kernel":digests[0]});
        if digests.len() == 3 {
            commitments["inputs"] = serde_json::json!(digests[1]);
            commitments["outputs"] = serde_json::json!(digests[2]);
        }
        std::fs::write(
            prefix.with_extension("commitments.json"),
            serde_json::to_vec_pretty(&commitments).unwrap(),
        )
        .unwrap();
    }
}
