//! Independent complex arithmetic and gate matrices, checked on actual VM stacks.
use triton_vm::prelude::*;

const P: u64 = BFieldElement::P;
fn add(a: u64, b: u64) -> u64 {
    ((a as u128 + b as u128) % P as u128) as u64
}
fn mul(a: u64, b: u64) -> u64 {
    ((a as u128 * b as u128) % P as u128) as u64
}
fn neg(a: u64) -> u64 {
    if a == 0 {
        0
    } else {
        P - a
    }
}
fn product(a: &[u64], b: &[u64]) -> [u64; 2] {
    [
        add(mul(a[0], b[0]), neg(mul(a[1], b[1]))),
        add(mul(a[0], b[1]), mul(a[1], b[0])),
    ]
}
pub(crate) fn reference(name: &str, x: &[u64; 8]) -> Vec<u64> {
    let [a, b, c, d, _, _, _, _] = *x;
    match name {
        "complex_zero" => vec![0, 0],
        "complex_one" => vec![1, 0],
        "complex_add" => vec![add(a, c), add(b, d)],
        "complex_sub" => vec![add(a, neg(c)), add(b, neg(d))],
        "complex_mul" => product(&x[..2], &x[2..4]).to_vec(),
        "complex_scale" => vec![mul(a, b), mul(a, c)],
        "complex_conj" => vec![a, neg(b)],
        "complex_norm_sq" => vec![add(mul(a, a), mul(b, b))],
        "init_zero" => vec![1, 0, 0, 0],
        "init_one" => vec![0, 0, 1, 0],
        "paulix" => vec![c, d, a, b],
        "pauliz" => vec![a, b, neg(c), neg(d)],
        "pauliy" => vec![d, neg(c), neg(b), a],
        "hadamard" => vec![add(a, c), add(b, d), add(a, neg(c)), add(b, neg(d))],
        "sgate" => vec![a, b, neg(d), c],
        "tgate" => vec![a, b, add(c, neg(d)), add(c, d)],
        "two_qubit_product" => [(0, 4), (0, 6), (2, 4), (2, 6)]
            .into_iter()
            .flat_map(|(i, j)| product(&x[i..i + 2], &x[j..j + 2]))
            .collect(),
        "cnot" => [0, 1, 2, 3, 6, 7, 4, 5].map(|i| x[i]).to_vec(),
        "cz" => vec![a, b, c, d, x[4], x[5], neg(x[6]), neg(x[7])],
        "swap" => [0, 1, 4, 5, 2, 3, 6, 7].map(|i| x[i]).to_vec(),
        "measure_deterministic" => {
            let difference = add(add(mul(a, a), mul(b, b)), neg(add(mul(c, c), mul(d, d))));
            vec![u64::from((difference >> 32) < 2147483647)]
        }
        _ => panic!("unknown gate {name}"),
    }
}

pub(crate) const GATES: &[(&str, usize, &str)] = &[
    ("complex_zero", 0, ""),
    ("complex_one", 0, ""),
    ("complex_add", 4, "a,b"),
    ("complex_sub", 4, "a,b"),
    ("complex_mul", 4, "a,b"),
    ("complex_scale", 3, "x0,gates.Complex { re:x1,im:x2 }"),
    ("complex_conj", 2, "a"),
    ("complex_norm_sq", 2, "a"),
    ("init_zero", 0, ""),
    ("init_one", 0, ""),
    ("paulix", 4, "q"),
    ("pauliz", 4, "q"),
    ("pauliy", 4, "q"),
    ("hadamard", 4, "q"),
    ("sgate", 4, "q"),
    ("tgate", 4, "q"),
    ("two_qubit_product", 8, "q,r"),
    ("cnot", 8, "state"),
    ("cz", 8, "state"),
    ("swap", 8, "state"),
    ("measure_deterministic", 4, "q"),
];

pub(crate) fn source() -> String {
    let mut s = String::from("program gates_regression\nuse std.quantum.gates\nfn main() {\n");
    for i in 0..8 {
        s.push_str(&format!("let x{i}:Field=pub_read()\n"));
    }
    s.push_str("let a=gates.Complex {re:x0,im:x1}\nlet b=gates.Complex {re:x2,im:x3}\nlet c=gates.Complex {re:x4,im:x5}\nlet d=gates.Complex {re:x6,im:x7}\nlet q=gates.Qubit {zero:a,one:b}\nlet r=gates.Qubit {zero:c,one:d}\nlet state=gates.TwoQubit {q00:a,q01:b,q10:c,q11:d}\n");
    for (i, &(name, _, args)) in GATES.iter().enumerate() {
        s.push_str(&format!("let out{i}=gates.{name}({args})\n"));
        let fields: &[&str] = match reference(name, &[0; 8]).len() {
            1 => &[""],
            2 => &[".re", ".im"],
            4 => &[".zero.re", ".zero.im", ".one.re", ".one.im"],
            8 => &[
                ".q00.re", ".q00.im", ".q01.re", ".q01.im", ".q10.re", ".q10.im", ".q11.re",
                ".q11.im",
            ],
            _ => unreachable!(),
        };
        for field in fields {
            if name == "measure_deterministic" {
                s.push_str(&format!(
                    "if out{i} {{ pub_write(1) }} else {{ pub_write(0) }}\n"
                ));
            } else {
                s.push_str(&format!("pub_write(out{i}{field})\n"));
            }
        }
    }
    s.push_str("}\n");
    s
}

#[cfg(test)]
fn run(assembly: &str, input: &[u64]) -> Vec<u64> {
    VM::run(
        Program::from_code(assembly).unwrap(),
        PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    )
    .unwrap()
    .into_iter()
    .map(|v| v.value())
    .collect()
}

#[test]
fn every_pure_gate_matches_independent_matrix_arithmetic_and_preserves_its_frame() {
    let inputs = [
        [0; 8],
        [1, 2, 3, 4, 5, 6, 7, 8],
        [P - 1, P - 2, 1, 2, 3, 5, 7, 11],
        [1 << 32, 3, 1, 5, 0, 1, 1, 0],
    ];
    let library = include_str!("../../baselines/triton/std/quantum/gates.tasm");
    for input in &inputs {
        for &(name, width, _) in GATES {
            let mut expected = reference(name, input);
            let mut hand = String::from("push 97\n");
            for value in &input[..width] {
                hand.push_str(&format!("push {value}\n"));
            }
            hand.push_str(&format!("call __{name}\n"));
            for remaining in (1..=expected.len()).rev() {
                if remaining > 1 {
                    hand.push_str(&format!("pick {}\n", remaining - 1));
                }
                hand.push_str("write_io 1\n");
            }
            hand.push_str("write_io 1\nhalt\n");
            hand.push_str(library);
            expected.push(97);
            assert_eq!(run(&hand, &[]), expected, "hand {name} {input:?}");
        }
    }
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("gates.tri");
    std::fs::write(&path, source()).unwrap();
    for profile in ["debug", "release"] {
        let assembly = trisha_rs::build_tasm(&path, "triton", profile).unwrap();
        for input in &inputs {
            let expected: Vec<_> = GATES
                .iter()
                .flat_map(|(name, _, _)| reference(name, input))
                .collect();
            assert_eq!(
                run(&assembly, input),
                expected,
                "source {profile} {input:?}"
            );
        }
    }
}
