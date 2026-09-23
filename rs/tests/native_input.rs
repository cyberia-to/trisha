use trident::runtime::{artifact::BundleCost, ProgramBundle, ProgramInput, Prover, Runner};
use trisha_rs::{convert, Warrior};
use triton_vm::prelude::BFieldElement;

fn bundle() -> ProgramBundle {
    ProgramBundle {
        name: "input-boundary".into(),
        version: String::new(),
        target_vm: "triton".into(),
        target_os: None,
        assembly: "halt".into(),
        source_hash: "fixture".into(),
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
fn every_execution_entry_rejects_noncanonical_input_even_when_unused() {
    for value in [BFieldElement::P, u64::MAX] {
        for input in [
            ProgramInput {
                public: vec![value],
                ..Default::default()
            },
            ProgramInput {
                secret: vec![value],
                ..Default::default()
            },
            ProgramInput {
                digests: vec![[0, 0, value, 0, 0]],
                ..Default::default()
            },
        ] {
            assert!(convert::to_triton_inputs(&input)
                .unwrap_err()
                .contains("noncanonical"));
            assert!(Warrior
                .run(&bundle(), &input)
                .unwrap_err()
                .contains("noncanonical"));
            assert!(Warrior
                .run_bounded(&bundle(), &input, 1)
                .unwrap_err()
                .contains("noncanonical"));
            assert!(Warrior
                .prove(&bundle(), &input)
                .unwrap_err()
                .contains("noncanonical"));
        }
    }
    let input = ProgramInput {
        public: vec![BFieldElement::P - 1],
        secret: vec![BFieldElement::P - 1],
        digests: vec![[BFieldElement::P - 1; 5]],
    };
    let (public, secret) = convert::to_triton_inputs(&input).unwrap();
    assert_eq!(public.individual_tokens[0].value(), BFieldElement::P - 1);
    assert_eq!(secret.individual_tokens[0].value(), BFieldElement::P - 1);
    assert_eq!(secret.digests[0].values()[2].value(), BFieldElement::P - 1);
}

#[test]
fn word_limit_counts_all_three_streams_before_native_allocation() {
    let mut input = ProgramInput {
        secret: vec![0; convert::MAX_INPUT_WORDS - 5],
        digests: vec![[0; 5]],
        ..Default::default()
    };
    convert::validate_input(&input).unwrap();
    input.public.push(0);
    assert!(convert::validate_input(&input)
        .unwrap_err()
        .contains("field-word limit"));
    assert!(Warrior
        .run(&bundle(), &input)
        .unwrap_err()
        .contains("field-word limit"));
}
