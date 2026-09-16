use triton_vm::prelude::*;

const MATRIX: [u64; 8] = [2, 3, 5, 7, 11, 13, 17, 19];
fn programs() -> Vec<(String, Program)> {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("quantum.tri");
    std::fs::write(&path, "program quantum_ram\nuse std.quantum.gates\nfn main(){let addr:Field=pub_read()\nlet n:Field=pub_read()\nlet target:Field=pub_read()\ngates.apply_single_gate(addr,n,target,gates.Complex{re:2,im:3},gates.Complex{re:5,im:7},gates.Complex{re:11,im:13},gates.Complex{re:17,im:19})}\n").unwrap();
    let mut result = ["debug", "release"]
        .into_iter()
        .map(|profile| {
            (
                profile.to_string(),
                Program::from_code(&trisha_rs::build_tasm(&path, "triton", profile).unwrap())
                    .unwrap(),
            )
        })
        .collect::<Vec<_>>();
    let prefix = "read_io 1 read_io 1 read_io 1 push 2 push 3 push 5 push 7 push 11 push 13 push 17 push 19 call __apply_single_gate halt\n";
    result.push((
        "hand".into(),
        Program::from_code(&format!(
            "{prefix}{}",
            include_str!("fixtures/quantum_ram.tasm")
        ))
        .unwrap(),
    ));
    result
}
fn run(program: Program, addr: u64, n: u64, target: u64, cells: &[(u64, u64)]) -> (VMState, bool) {
    let mut secret = NonDeterminism::default();
    secret.ram.extend(
        cells
            .iter()
            .map(|&(a, v)| (BFieldElement::new(a), BFieldElement::new(v))),
    );
    let mut vm = VMState::new(
        program,
        PublicInput::new([addr, n, target].map(BFieldElement::new).to_vec()),
        secret,
    );
    for _ in 0..2_000_000 {
        if vm.halting {
            return (vm, true);
        }
        if vm.step().is_err() {
            return (vm, false);
        }
    }
    panic!("bounded gate did not terminate");
}
#[test]
fn arbitrary_complex_matrix_preserves_neighbors_for_each_target() {
    for (profile, program) in programs() {
        for n in 1..=3u64 {
            for target in 0..n {
                let count = 1usize << n;
                let mut words = (0..2 * count)
                    .map(|i| BFieldElement::new((i as u64 + 1) * 3))
                    .collect::<Vec<_>>();
                let mut cells = words
                    .iter()
                    .enumerate()
                    .map(|(i, v)| (100 + i as u64, v.value()))
                    .collect::<Vec<_>>();
                cells.extend([(99, 987), (100 + words.len() as u64, 654)]);
                for i in 0..count {
                    if i & (1 << target) == 0 {
                        let j = i + (1 << target);
                        let a = [words[2 * i], words[2 * i + 1]];
                        let b = [words[2 * j], words[2 * j + 1]];
                        for row in 0..2 {
                            let g = MATRIX.map(BFieldElement::new);
                            let k = 4 * row;
                            let pos = if row == 0 { i } else { j };
                            words[2 * pos] =
                                g[k] * a[0] - g[k + 1] * a[1] + g[k + 2] * b[0] - g[k + 3] * b[1];
                            words[2 * pos + 1] =
                                g[k] * a[1] + g[k + 1] * a[0] + g[k + 2] * b[1] + g[k + 3] * b[0];
                        }
                    }
                }
                let (vm, ok) = run(program.clone(), 100, n, target, &cells);
                assert!(ok, "{profile} n={n} target={target}");
                for (i, word) in words.iter().enumerate() {
                    assert_eq!(
                        vm.ram[&BFieldElement::new(100 + i as u64)],
                        *word,
                        "{profile} n={n} target={target} word={i}"
                    );
                }
                for (a, v) in [(99, 987), (100 + words.len() as u64, 654)] {
                    assert_eq!(
                        vm.ram[&BFieldElement::new(a)].value(),
                        v,
                        "neighbor {profile}"
                    );
                }
            }
        }
    }
}
#[test]
fn invalid_bounds_reject_before_state_mutation() {
    for (profile, program) in programs() {
        for (addr, n, target) in [
            (100, 13, 0),
            (100, 1, 1),
            (100, 0, 0),
            (100, 1, 1 << 32),
            (100, 1 << 32, 0),
            (1 << 32, 1, 0),
            ((1 << 32) - 3, 1, 0),
            (BFieldElement::P - 1, 1, 0),
        ] {
            let mut cells = (0..16).map(|i| (100 + i, 700 + i)).collect::<Vec<_>>();
            cells.extend((0..8).map(|i| ((addr + i) % BFieldElement::P, 800 + i)));
            let (vm, ok) = run(program.clone(), addr, n, target, &cells);
            assert!(!ok, "accepted {profile}: {addr},{n},{target}");
            let expected = cells
                .into_iter()
                .collect::<std::collections::HashMap<_, _>>();
            for (a, v) in expected {
                assert_eq!(
                    vm.ram[&BFieldElement::new(a)].value(),
                    v,
                    "mutated {profile}: {addr},{n},{target} at {a}"
                );
            }
        }
    }
}

#[test]
fn buffer_may_end_at_the_last_u32_address() {
    let addr = (1u64 << 32) - 4;
    let cells = [(addr, 3), (addr + 1, 6), (addr + 2, 9), (addr + 3, 12)];
    for (profile, program) in programs() {
        let (vm, ok) = run(program, addr, 1, 0, &cells);
        assert!(ok, "{profile} rejected highest valid buffer");
        for (i, expected) in [BFieldElement::P - 51, 144, BFieldElement::P - 120, 480]
            .into_iter()
            .enumerate()
        {
            assert_eq!(
                vm.ram[&BFieldElement::new(addr + i as u64)].value(),
                expected,
                "{profile} word {i}"
            );
        }
    }
}
