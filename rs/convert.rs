use triton_vm::prelude::*;

use trident::runtime::{ExecutionResult, ProgramInput};

pub fn u64s_to_bfes(values: &[u64]) -> Vec<BFieldElement> {
    values.iter().map(|&v| BFieldElement::new(v)).collect()
}

pub fn bfes_to_u64s(bfes: &[BFieldElement]) -> Vec<u64> {
    bfes.iter().map(|b| b.value()).collect()
}

/// Bound decoded transport and copies before allocating native VM inputs.
pub const MAX_INPUT_WORDS: usize = 8 * 1024 * 1024;

pub fn validate_input(input: &ProgramInput) -> Result<(), String> {
    let words = input
        .digests
        .len()
        .checked_mul(Digest::LEN)
        .and_then(|n| n.checked_add(input.public.len()))
        .and_then(|n| n.checked_add(input.secret.len()))
        .ok_or("input field count overflows")?;
    if words > MAX_INPUT_WORDS {
        return Err("input exceeds8Mi field-word limit".into());
    }
    if input
        .public
        .iter()
        .chain(&input.secret)
        .chain(input.digests.iter().flatten())
        .any(|&word| word >= BFieldElement::P)
    {
        return Err("input contains a noncanonical Goldilocks field element".into());
    }
    Ok(())
}

pub fn to_triton_inputs(input: &ProgramInput) -> Result<(PublicInput, NonDeterminism), String> {
    validate_input(input)?;
    let public = PublicInput::new(u64s_to_bfes(&input.public));
    let mut non_det = NonDeterminism::default();
    non_det.individual_tokens = u64s_to_bfes(&input.secret);
    non_det.digests = input
        .digests
        .iter()
        .map(|d| Digest::new(d.map(BFieldElement::new)))
        .collect();
    Ok((public, non_det))
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
) -> Result<triton_vm::proof::Claim, String> {
    if program_hash.len() != Digest::LEN {
        return Err(format!(
            "program hash must contain exactly {} field elements",
            Digest::LEN
        ));
    }
    if program_hash
        .iter()
        .chain(public_input)
        .chain(public_output)
        .any(|&v| v >= BFieldElement::P)
    {
        return Err("claim contains a noncanonical Goldilocks field element".to_string());
    }
    let digest_bfes = std::array::from_fn(|i| BFieldElement::new(program_hash[i]));
    Ok(triton_vm::proof::Claim::new(Digest::new(digest_bfes))
        .with_input(u64s_to_bfes(public_input))
        .with_output(u64s_to_bfes(public_output)))
}

pub fn proof_to_bytes(proof: &triton_vm::proof::Proof) -> Vec<u8> {
    // Preserve the fixed-int bincode wire format without a fallible serializer.
    let mut bytes = Vec::new();
    bytes.extend_from_slice(&(proof.0.len() as u64).to_le_bytes());
    for field in &proof.0 {
        bytes.extend_from_slice(&field.value().to_le_bytes());
    }
    bytes
}

/// Largest accepted native proof artifact; bounds work before deserialization.
pub const MAX_PROOF_BYTES: usize = 64 * 1024 * 1024;

pub fn bytes_to_proof(bytes: &[u8]) -> Result<triton_vm::proof::Proof, String> {
    if bytes.len() < 8 || bytes.len() > MAX_PROOF_BYTES || bytes.len() % 8 != 0 {
        return Err("invalid proof byte length".into());
    }
    let word = |chunk: &[u8]| {
        u64::from_le_bytes([
            chunk[0], chunk[1], chunk[2], chunk[3], chunk[4], chunk[5], chunk[6], chunk[7],
        ])
    };
    if word(&bytes[..8]) != ((bytes.len() - 8) / 8) as u64 {
        return Err("proof field count does not match its byte length".into());
    }
    // Upstream BFieldElement's serde decoder reduces u64 modulo p. Checking the
    // actual wire values prevents aliases of a canonical proof being accepted.
    let fields = bytes[8..]
        .chunks_exact(8)
        .map(|chunk| {
            let value = word(chunk);
            if value >= BFieldElement::P {
                Err("proof contains a noncanonical Goldilocks field element".to_string())
            } else {
                Ok(BFieldElement::new(value))
            }
        })
        .collect::<Result<Vec<_>, _>>()?;
    Ok(triton_vm::proof::Proof(fields))
}

/// Default-security proof verification with exact consumption of proof items.
/// Native Triton verification tolerates additional items, but its recursive
/// verifier rejects them. Keep the two acceptance contracts identical.
pub fn verify_native_proof(claim: &Claim, proof: &Proof) -> Result<(), String> {
    use triton_vm::proof_item::ProofItem;
    use triton_vm::proof_stream::ProofStream;
    if claim.version != triton_vm::proof::CURRENT_VERSION {
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

/// VM diagnostics may contain operand stack and witness memory.
pub fn execution_error(error: impl std::fmt::Display, input: &ProgramInput) -> String {
    if !input.secret.is_empty() || !input.digests.is_empty() {
        "execution error: program rejected private witness".into()
    } else {
        format!("execution error: {error}")
    }
}
