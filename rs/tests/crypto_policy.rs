//! Independent full-vector checks for scalar policy and the two permutation
//! contracts. ECDSA helpers do not claim elliptic-curve verification; the custom
//! permutation does not claim standard Poseidon2 security.
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
        .map(|n| BFieldElement::new(n.trim().trim_matches('"').parse().unwrap()))
        .collect()
}
fn run(
    code: &str,
    input: Vec<BFieldElement>,
    secret: Vec<BFieldElement>,
    limit: u32,
) -> Vec<BFieldElement> {
    let program = Program::from_code(code).unwrap();
    let mut vm = VMState::new(
        program,
        PublicInput::new(input),
        NonDeterminism::new(secret),
    );
    while !vm.halting && vm.cycle_count < limit {
        vm.step().unwrap();
    }
    assert!(vm.halting, "algorithm exceeded regression execution budget");
    vm.public_output
}
fn fixtures() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../baselines/triton/fixtures")
}

#[test]
fn scalar_range_low_s_and_full_limb_roundtrip() {
    let root = fixtures();
    for profile in ["debug", "release"] {
        let code =
            trisha_rs::build_tasm(&root.join("ecdsa-half/main.tri"), "triton", profile).unwrap();
        for name in [
            "half",
            "high",
            "zero",
            "order",
            "invalid-r",
            "cross-limb",
            "even-order",
        ] {
            let fixture =
                std::fs::read_to_string(root.join(format!("ecdsa-{name}/vector.bench.toml")))
                    .unwrap();
            assert_eq!(
                run(&code, vector(&fixture, "input"), vec![], 100_000),
                vector(&fixture, "output"),
                "{profile}/{name}"
            );
        }
        let fixture =
            std::fs::read_to_string(root.join("ecdsa-oversized-limb/vector.bench.toml")).unwrap();
        let mut vm = VMState::new(
            Program::from_code(&code).unwrap(),
            PublicInput::new(vector(&fixture, "input")),
            NonDeterminism::default(),
        );
        let mut rejected = false;
        while !vm.halting && vm.cycle_count < 100_000 {
            if vm.step().is_err() {
                rejected = true;
                break;
            }
        }
        assert!(rejected, "{profile}: oversized scalar limb was accepted");
    }
}
#[test]
fn custom_permutation_all_lanes_with_caller_constants() {
    let root = fixtures();
    let code = trisha_rs::build_tasm(
        &root.join("custom-poseidon2-lanes/main.tri"),
        "triton",
        "release",
    )
    .unwrap();
    for name in ["zero", "lanes"] {
        let fixture = std::fs::read_to_string(
            root.join(format!("custom-poseidon2-{name}/vector.bench.toml")),
        )
        .unwrap();
        assert_eq!(
            run(
                &code,
                vector(&fixture, "input"),
                vector(&fixture, "secret"),
                1_000_000
            ),
            vector(&fixture, "output"),
            "{name}"
        );
    }
}
#[test]
fn keccak_all_rounds_all_lanes() {
    let root = fixtures();
    for driver in ["main.tri", "struct.tri"] {
        let code = trisha_rs::build_tasm(
            &root.join(format!("keccak-zero/{driver}")),
            "triton",
            "release",
        )
        .unwrap();
        for name in ["zero", "lanes"] {
            let fixture =
                std::fs::read_to_string(root.join(format!("keccak-{name}/vector.bench.toml")))
                    .unwrap();
            assert_eq!(
                run(&code, vector(&fixture, "input"), vec![], 10_000_000),
                vector(&fixture, "output"),
                "{driver}/{name}"
            );
        }
    }
}

#[test]
fn keccak_ram_checks_regions_and_limbs_before_mutation() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("ram.tri");
    std::fs::write(
        &source,
        r#"program ram_contract
use std.crypto.keccak256
use vm.io.mem
use vm.core.convert
fn main() {
    let state = pub_read()
    let scratch = pub_read()
    let first = pub_read()
    for i in 0..50 bounded 50 { mem.write(state + convert.as_field(i),0) }
    mem.write(state,first)
    mem.write(500,12345)
    mem.write(600,67890)
    keccak256.keccak_f1600_in_ram(state,scratch)
    pub_write(mem.read(500))
    pub_write(mem.read(600))
    for i in 0..50 bounded 50 { pub_write(mem.read(state + convert.as_field(i))) }
}"#,
    )
    .unwrap();
    let code = trisha_rs::build_tasm(&source, "triton", "release").unwrap();
    let expected = vector(
        &std::fs::read_to_string(fixtures().join("keccak-zero/vector.bench.toml")).unwrap(),
        "output",
    );
    for (state, scratch) in [(1000, 1050), (1000, 930), (1000, 3000)] {
        let actual = run(
            &code,
            vec![bfe!(state), bfe!(scratch), bfe!(0)],
            vec![],
            1_000_000,
        );
        assert_eq!(actual[..2], [bfe!(12345), bfe!(67890)]);
        assert_eq!(actual[2..], expected);
    }
    for (state, scratch, first) in [
        (1000u64, 1049u64, 0u64),
        (1000, 999, 0),
        (1000, 931, 0),
        (u32::MAX as u64 - 20, 3000, 0),
        (1000, u32::MAX as u64 - 20, 0),
        (1000, 3000, 1u64 << 32),
    ] {
        let mut vm = VMState::new(
            Program::from_code(&code).unwrap(),
            PublicInput::new(vec![bfe!(state), bfe!(scratch), bfe!(first)]),
            NonDeterminism::default(),
        );
        let mut rejected = false;
        while !vm.halting && vm.cycle_count < 100_000 {
            if vm.step().is_err() {
                rejected = true;
                break;
            }
        }
        assert!(
            rejected,
            "invalid region or limb accepted: {state}/{scratch}/{first}"
        );
        assert_eq!(
            vm.ram.get(&bfe!(state)),
            Some(&bfe!(first)),
            "state changed before rejecting invalid input"
        );
        assert_eq!(vm.ram.get(&bfe!(500)), Some(&bfe!(12345)));
        assert_eq!(vm.ram.get(&bfe!(600)), Some(&bfe!(67890)));
    }
}
