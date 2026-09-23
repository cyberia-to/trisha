use trident::runtime::{artifact::BundleCost, ProgramBundle, ProgramInput, Prover};
use triton_vm::prelude::Program;

fn bundle(assembly: &str) -> ProgramBundle {
    ProgramBundle {
        name: "lock".into(),
        version: "0.1.0".into(),
        target_vm: "triton".into(),
        target_os: Some("neptune".into()),
        assembly: assembly.into(),
        source_hash: "inspection-fixture".into(),
        reads_state: false,
        entry_point: "main".into(),
        functions: vec![],
        cost: BundleCost {
            table_values: vec![],
            table_names: vec![],
            padded_height: 0,
            estimated_proving_ns: 0,
        },
    }
}

#[test]
fn lock_script_identity_uses_native_program_hash_and_authenticates_attached_proof() {
    let original = bundle("push 7\nwrite_io 1\nhalt");
    let annotated = bundle("// identical instructions\n push 7 write_io 1 halt");
    let expected = Program::from_code(&original.assembly)
        .unwrap()
        .hash()
        .0
        .map(|v| v.value());
    assert_eq!(
        trisha_rs::deployment::inspect(&original, None)
            .unwrap()
            .lock_script_hash,
        expected
    );
    assert_eq!(
        trisha_rs::deployment::inspect(&annotated, None)
            .unwrap()
            .lock_script_hash,
        expected
    );
    let proof = trisha_rs::Warrior
        .prove(&original, &ProgramInput::default())
        .unwrap();
    assert!(
        trisha_rs::deployment::inspect(&annotated, Some(&proof))
            .unwrap()
            .execution_proof_verified
    );
    let other = bundle("push 8 write_io 1 halt");
    assert!(trisha_rs::deployment::inspect(&other, Some(&proof))
        .unwrap_err()
        .contains("another program"));
    let mut tampered = proof;
    tampered.claim.public_output = vec![8];
    assert!(trisha_rs::deployment::inspect(&original, Some(&tampered)).is_err());
    assert!(trisha_rs::deployment::inspect(&bundle("not_tasm"), None).is_err());
}
