use trident::runtime::{ProofData, Verifier};
use trisha_rs::{convert, recursive, Warrior};
use triton_vm::prelude::*;
use triton_vm::proof_item::ProofItem;
use triton_vm::proof_stream::ProofStream;

#[test]
fn native_recursive_and_warrior_reject_superfluous_proof_items() {
    assert_eq!(triton_vm::proof::CURRENT_VERSION, 5);
    let program = Program::from_code("push 5 write_io 1 halt").unwrap();
    let (trace, output) = VM::trace_execution(
        program.clone(),
        PublicInput::default(),
        NonDeterminism::default(),
    )
    .unwrap();
    let claim = Claim::about_program(&program).with_output(output);
    let proof = Stark::default().prove(&claim, &trace).unwrap();
    convert::verify_native_proof(&claim, &proof).unwrap();
    let mut stream = ProofStream::try_from(&proof).unwrap();
    stream.enqueue(ProofItem::MerkleRoot(Digest::default()));
    let extended: Proof = stream.into();
    // Pin the upstream discrepancy that requires this owner-side guard.
    assert!(Stark::default().verify(&claim, &extended).is_ok());
    assert!(convert::verify_native_proof(&claim, &extended).is_err());
    assert!(recursive::encode(&claim, &extended).is_err());
    let artifact = ProofData {
        claim: convert::to_trident_claim(&claim),
        proof_bytes: convert::proof_to_bytes(&extended),
        format: "stark-triton-v7".into(),
    };
    assert!(!Warrior::new().verify(&artifact).unwrap());
    let mut legacy = artifact;
    legacy.format = "stark-triton-v2".into();
    assert!(Warrior::new().verify(&legacy).is_err());
}

#[test]
fn hostile_height_items_are_rejected_before_shift_or_domain_arithmetic() {
    let claim = Claim::new(Digest::default());
    for height in [0, 1, 7, 8, 28, 29, 30, 31, 32, 63, 64, u32::MAX] {
        let mut stream = ProofStream::new();
        stream.enqueue(ProofItem::Log2PaddedHeight(height));
        let proof: Proof = stream.into();
        let error = convert::verify_native_proof(&claim, &proof).unwrap_err();
        if (29..32).contains(&height) && usize::BITS == 64 {
            assert_eq!(error, "proof domain exceeds native u32 index bounds");
        }
    }
    for heights in [vec![], vec![8, 8]] {
        let mut stream = ProofStream::new();
        for height in heights {
            stream.enqueue(ProofItem::Log2PaddedHeight(height));
        }
        stream.enqueue(ProofItem::MerkleRoot(Digest::default()));
        let proof: Proof = stream.into();
        assert!(convert::verify_native_proof(&claim, &proof).is_err());
    }
}
