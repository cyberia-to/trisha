//! Independent oracle: the pinned upstream Plonky3 implementation.
use p3_field::PrimeField64;
use p3_goldilocks::{
    Goldilocks, Poseidon2GoldilocksHL, HL_GOLDILOCKS_8_EXTERNAL_ROUND_CONSTANTS,
    HL_GOLDILOCKS_8_INTERNAL_ROUND_CONSTANTS,
};
use p3_poseidon2::ExternalLayerConstants;
use p3_symmetric::Permutation;
use triton_vm::prelude::*;
fn oracle(input: [u64; 8]) -> Vec<u64> {
    let permutation = Poseidon2GoldilocksHL::<8>::new(
        ExternalLayerConstants::new_from_saved_array(
            HL_GOLDILOCKS_8_EXTERNAL_ROUND_CONSTANTS,
            Goldilocks::new_array,
        ),
        Goldilocks::new_array(HL_GOLDILOCKS_8_INTERNAL_ROUND_CONSTANTS).to_vec(),
    );
    let mut state = Goldilocks::new_array(input);
    permutation.permute_mut(&mut state);
    state.iter().map(|v| v.as_canonical_u64()).collect()
}
fn program(body: &str) -> Program {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("standard.tri");
    std::fs::write(
        &path,
        format!("program standard\nuse std.crypto.poseidon\nfn main() {{ {body} }}\n"),
    )
    .unwrap();
    let code = trisha_rs::build_tasm(&path, "triton", "debug").unwrap();
    Program::from_code(&code).unwrap()
}
fn run(program: &Program, input: &[u64]) -> Vec<u64> {
    VM::run(
        program.clone(),
        PublicInput::new(input.iter().map(|&v| BFieldElement::new(v)).collect()),
        NonDeterminism::default(),
    )
    .unwrap()
    .iter()
    .map(|v| v.value())
    .collect()
}
#[test]
fn standard_permutation_matches_pinned_upstream_on_all_lanes() {
    let reads = (0..8)
        .map(|i| format!("let v{i}: Field = pub_read()\n"))
        .collect::<String>();
    let fields = (0..8)
        .map(|i| format!("s{i}: v{i}"))
        .collect::<Vec<_>>()
        .join(", ");
    let writes = (0..8)
        .map(|i| format!("pub_write(result.s{i})\n"))
        .collect::<String>();
    let code = program(&format!("{reads} let initial: poseidon.State = poseidon.State {{ {fields} }}\n let result: poseidon.State = poseidon.permute(initial)\n {writes}"));
    for input in [
        [0; 8],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [BFieldElement::P - 1; 8],
        [7, 0, 19, 1, 97, 65536, 4294967295, 100000000000],
    ] {
        assert_eq!(run(&code, &input), oracle(input));
    }
}
#[test]
fn full_digest_and_explicit_truncation_match_length_bound_upstream_permutation() {
    let code = program("let a: Field = pub_read()\n let b: Field = pub_read()\n let c: Field = pub_read()\n let d: Field = pub_read()\n let (h0,h1,h2,h3) = poseidon.hash4_digest(a,b,c,d)\n pub_write(h0)\n pub_write(h1)\n pub_write(h2)\n pub_write(h3)\n pub_write(poseidon.hash4(a,b,c,d))");
    let expected = oracle([1, 2, 3, 4, 4, 0, 0, 0]);
    assert_eq!(
        run(&code, &[1, 2, 3, 4]),
        vec![
            expected[0],
            expected[1],
            expected[2],
            expected[3],
            expected[0]
        ]
    );
}
#[test]
fn hand_ram_permutation_and_wrappers_match_independent_upstream() {
    let hand = include_str!("../../baselines/triton/std/crypto/poseidon.tasm");
    for input in [
        [0; 8],
        [0, 1, 2, 3, 4, 5, 6, 7],
        [BFieldElement::P - 1; 8],
        [7, 0, 19, 1, 97, 65536, 4294967295, 100000000000],
    ] {
        let pushes = input
            .iter()
            .map(|x| format!("push {x} "))
            .collect::<String>();
        let code = Program::from_code(&format!("{pushes} call __permute swap 7 swap 1 swap 6 swap 1 swap 2 swap 5 swap 2 swap 3 swap 4 swap 3 write_io 5 write_io 3 halt\n{hand}")).unwrap();
        assert_eq!(run(&code, &[]), oracle(input));
    }
    for n in 1..=4 {
        let mut input = [0; 8];
        for (i, x) in input[..n].iter_mut().enumerate() {
            *x = i as u64 + 1;
        }
        input[4] = n as u64;
        let pushes = input[..n]
            .iter()
            .map(|x| format!("push {x} "))
            .collect::<String>();
        let code = Program::from_code(&format!("{pushes} call __hash{n} write_io 1 halt\n{hand}"))
            .unwrap();
        assert_eq!(run(&code, &[]), oracle(input)[..1]);
    }
}
