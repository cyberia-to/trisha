//! Execute complete portable compiler stage records against the independent
//! handwritten RAM-machine reference. Grammar limitations are documented next
//! to the baseline; these tests do not claim full self-hosting support.
use std::path::PathBuf;
use triton_vm::prelude::*;

fn vector(text: &str, name: &str) -> Vec<BFieldElement> {
    let prefix = format!("{name} = [");
    text.lines()
        .find_map(|line| line.strip_prefix(&prefix))
        .unwrap()
        .trim_end_matches(']')
        .split(',')
        .filter(|n| !n.trim().is_empty())
        .map(|n| BFieldElement::new(n.trim().parse().unwrap()))
        .collect()
}

fn execute(code: &str, input: Vec<BFieldElement>) -> Result<Vec<BFieldElement>, String> {
    let program = Program::from_code(code).unwrap();
    let mut vm = VMState::new(program, PublicInput::new(input), NonDeterminism::default());
    while !vm.halting && vm.cycle_count < 500_000 {
        vm.step().map_err(|e| e.to_string())?;
    }
    assert!(
        vm.halting,
        "capacity-sized no-op loops or unbounded parser execution regressed"
    );
    Ok(vm.public_output)
}

fn check(stage: &str) {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../baselines/triton");
    let hand = std::fs::read_to_string(root.join(format!("std/compiler/{stage}.tasm"))).unwrap();
    let hand = format!("call __{stage}_main halt\n{hand}");
    let source = root.join(format!("fixtures/compiler-{stage}-precedence/main.tri"));
    let code = trisha_rs::build_tasm(&source, "triton", "release").unwrap();
    for name in ["precedence", "parentheses", "associativity", "reject"] {
        let fixture = std::fs::read_to_string(root.join(format!(
            "fixtures/compiler-{stage}-{name}/vector.bench.toml"
        )))
        .unwrap();
        let input = vector(&fixture, "input");
        let actual = execute(&code, input.clone());
        let reference = execute(&hand, input);
        if name == "reject" {
            assert!(actual.is_err(), "portable {stage} accepted malformed input");
            assert!(
                reference.is_err(),
                "reference {stage} accepted malformed input"
            );
        } else {
            let expected = vector(&fixture, "output");
            assert_eq!(actual.unwrap(), expected, "portable {stage}/{name}");
            assert_eq!(reference.unwrap(), expected, "independent {stage}/{name}");
        }
    }
    if stage == "pipeline" {
        let fixture = std::fs::read_to_string(
            root.join("fixtures/compiler-pipeline-type-reject/vector.bench.toml"),
        )
        .unwrap();
        assert!(
            execute(&code, vector(&fixture, "input")).is_err(),
            "tail Bool accepted as declared Field return"
        );
    }
}

#[test]
fn lexer_complete_records_and_rejection() {
    check("lexer");
}
#[test]
fn parser_precedence_parentheses_associativity_and_rejection() {
    check("parser");
}
#[test]
fn pipeline_complete_tir_entry_and_return_type() {
    check("pipeline");
}
