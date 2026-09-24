//! The shared parser must preserve block boundaries on the Triton owner path.
use triton_vm::prelude::*;

#[test]
fn control_blocks_execute_constants_and_delimited_struct_expressions() {
    let directory = tempfile::tempdir().unwrap();
    std::fs::write(
        directory.path().join("boundary.tri"),
        include_str!("../../../trident/tests/fixtures/control_blocks.tri"),
    )
    .unwrap();
    let path = directory.path().join("main.tri");
    std::fs::write(&path,"program control_blocks\nuse boundary\nfn main(n:Field) { if n==boundary.ZERO {} else {}\npub_write(boundary.choose(n)) }").unwrap();
    for profile in ["debug", "release"] {
        let assembly = trisha_rs::build_tasm(&path, "triton", profile).unwrap();
        let program = Program::from_code(&assembly).unwrap();
        for (input, expected) in [(0, 19), (1, 23)] {
            let output = VM::run(
                program.clone(),
                PublicInput::new(vec![BFieldElement::new(input)]),
                NonDeterminism::default(),
            )
            .unwrap();
            assert_eq!(
                output,
                vec![BFieldElement::new(expected)],
                "{profile}/{input}"
            );
        }
    }
}
