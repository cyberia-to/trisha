use trisha_rs::convert::{bytes_to_proof, proof_to_bytes, MAX_PROOF_BYTES};
use triton_vm::prelude::*;

#[test]
fn canonical_native_proof_codec_preserves_existing_fixed_int_bytes() {
    let proof = triton_vm::proof::Proof(vec![
        BFieldElement::new(0),
        BFieldElement::new(1),
        BFieldElement::new(BFieldElement::P - 1),
    ]);
    let bytes = proof_to_bytes(&proof);
    assert_eq!(bytes, bincode::serialize(&proof).unwrap());
    assert_eq!(bytes_to_proof(&bytes).unwrap(), proof);
    assert_eq!(bytes_to_proof(&0u64.to_le_bytes()).unwrap().0, vec![]);
}

#[test]
fn proof_wire_rejects_modular_aliases_bad_lengths_and_trailing_bytes() {
    let proof = triton_vm::proof::Proof(vec![BFieldElement::new(0)]);
    let canonical = proof_to_bytes(&proof);
    for noncanonical in [BFieldElement::P, u64::MAX] {
        let mut bytes = canonical.clone();
        bytes[8..16].copy_from_slice(&noncanonical.to_le_bytes());
        assert!(bytes_to_proof(&bytes).is_err());
    }
    for count in [0, 2, u64::MAX] {
        let mut bytes = canonical.clone();
        bytes[..8].copy_from_slice(&count.to_le_bytes());
        assert!(bytes_to_proof(&bytes).is_err());
    }
    for length in 0..canonical.len() {
        assert!(bytes_to_proof(&canonical[..length]).is_err());
    }
    for extra in [1, 8] {
        let mut bytes = canonical.clone();
        bytes.extend(vec![0; extra]);
        assert!(bytes_to_proof(&bytes).is_err());
    }
    assert!(bytes_to_proof(&vec![0; MAX_PROOF_BYTES + 8]).is_err());
}
