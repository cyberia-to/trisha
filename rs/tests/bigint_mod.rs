//! Frozen expected residues were generated with Python arbitrary-precision
//! `(a*b)%m`, independently of the limb arithmetic under test.
use triton_vm::prelude::*;
fn program(operation: &str) -> Program {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("modular.tri");
    let fields = (0..8)
        .map(|i| format!("l{i}: f{i}"))
        .collect::<Vec<_>>()
        .join(", ");
    let reads = (0..8)
        .map(|i| format!("let f{i}: U32 = convert.as_u32(pub_read())\n"))
        .collect::<String>();
    let expression = if operation == "identity" {
        "a".to_string()
    } else if matches!(operation, "sub256" | "mul256_low") {
        format!("bigint.{operation}(a,b)")
    } else {
        format!("bigint.{operation}(a,b,m)")
    };
    let writes = (0..8)
        .map(|i| format!("pub_write(convert.as_field(result.l{i}))\n"))
        .collect::<String>();
    let source = format!("program modular\nuse std.crypto.bigint\nuse vm.core.convert\nfn read() -> bigint.U256 {{ {reads} bigint.U256 {{ {fields} }} }}\nfn main() {{ let a: bigint.U256 = read()\n let b: bigint.U256 = read()\n let m: bigint.U256 = read()\n let result: bigint.U256 = {expression}\n {writes} }}\n");
    std::fs::write(&path, source).unwrap();
    let code = trisha_rs::build_tasm(&path, "triton", "debug").unwrap();
    Program::from_code(&code).unwrap()
}
fn run(program: &Program, a: &[u64; 8], b: &[u64; 8], m: &[u64; 8]) -> Result<Vec<u64>, String> {
    let input = a
        .iter()
        .chain(b)
        .chain(m)
        .map(|&v| BFieldElement::new(v))
        .collect();
    VM::run(
        program.clone(),
        PublicInput::new(input),
        NonDeterminism::default(),
    )
    .map(|output| output.iter().map(|v| v.value()).collect())
    .map_err(|error| error.to_string())
}

const VECTORS: [([u64; 8], [u64; 8], [u64; 8], [u64; 8]); 8] = [
    (
        [
            4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [
            4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [
            4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ),
    (
        [
            4294966318, 4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [
            4294966318, 4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [
            4294966319, 4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [1, 0, 0, 0, 0, 0, 0, 0],
    ),
    (
        [0, 0, 0, 0, 0, 0, 0, 2147483648],
        [2, 0, 0, 0, 0, 0, 0, 0],
        [
            4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [1, 0, 0, 0, 0, 0, 0, 0],
    ),
    (
        [
            4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [
            4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [97, 0, 0, 0, 0, 0, 0, 0],
        [11, 0, 0, 0, 0, 0, 0, 0],
    ),
    (
        [
            4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [12345, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ),
    (
        [0, 0, 0, 0, 0, 0, 0, 0],
        [
            4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [
            4294966319, 4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ),
    (
        [
            2596069104, 305419896, 2596069104, 305419896, 2596069104, 305419896, 2596069104,
            305419896,
        ],
        [
            1985229328, 4275878552, 1985229328, 4275878552, 1985229328, 4275878552, 1985229328,
            4275878552,
        ],
        [17, 0, 0, 0, 0, 0, 1, 0],
        [
            1153799302, 135742176, 1678448320, 4017459384, 1409004678, 1034864416, 0, 0,
        ],
    ),
    (
        [
            4294967292, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [
            4294967290, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295,
        ],
        [123, 0, 0, 0, 0, 0, 0, 2147483648],
        [63000, 0, 0, 0, 0, 0, 0, 0],
    ),
];

#[test]
fn full_width_mul_mod_matches_independent_integer_vectors() {
    let checker = program("mul_mod");
    for (index, (a, b, m, expected)) in VECTORS.iter().enumerate() {
        assert_eq!(run(&checker, a, b, m).unwrap(), expected, "vector {index}");
    }
    assert!(run(&checker, &[1; 8], &[2; 8], &[0; 8]).is_err());
}

#[test]
fn reduced_add_mod_retains_the_257th_carry_bit() {
    let checker = program("add_mod");
    assert_eq!(
        run(
            &checker,
            &[
                4294966318, 4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                4294967295
            ],
            &[
                4294966318, 4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                4294967295
            ],
            &[
                4294966319, 4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                4294967295
            ]
        )
        .unwrap(),
        [
            4294966317, 4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295
        ]
    );
}

#[test]
fn isolate_input_and_subtraction() {
    let a = [4294967295; 8];
    let b = [1, 0, 0, 0, 0, 0, 0, 0];
    assert_eq!(run(&program("identity"), &a, &b, &a).unwrap(), a);
    assert_eq!(
        run(&program("sub256"), &a, &b, &a).unwrap(),
        [
            4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295
        ]
    );
}

#[test]
fn quotient_and_mutable_bit_scan_use_all_32_bits() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("scan.tri");
    std::fs::write(&path, "program scan\nfn main() { let mut mask: U32 = as_u32(2147483648)\n for i in 0..32 { pub_write(as_field(mask))\n let (next,unused) = mask /% as_u32(2)\n mask = next } }\n").unwrap();
    let code = trisha_rs::build_tasm(&path, "triton", "debug").unwrap();
    let output = VM::run(
        Program::from_code(&code).unwrap(),
        PublicInput::default(),
        NonDeterminism::default(),
    )
    .unwrap();
    assert_eq!(
        output.iter().map(|v| v.value()).collect::<Vec<_>>(),
        (0..32).rev().map(|i| 1u64 << i).collect::<Vec<_>>()
    );
}

#[test]
fn original_branch_local_tuple_return_is_not_corrupted() {
    let path =
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/borrow_tuple.tri");
    let code = trisha_rs::build_tasm(&path, "triton", "debug").unwrap();
    let output = VM::run(
        Program::from_code(&code).unwrap(),
        PublicInput::default(),
        NonDeterminism::default(),
    )
    .unwrap();
    assert_eq!(
        output.iter().map(|v| v.value()).collect::<Vec<_>>(),
        vec![4294967294, 0]
    );
}

#[test]
fn original_branch_tuple_called_from_aggregate_subtraction() {
    let path =
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/original_borrow.tri");
    let code = trisha_rs::build_tasm(&path, "triton", "debug").unwrap();
    let output = VM::run(
        Program::from_code(&code).unwrap(),
        PublicInput::default(),
        NonDeterminism::default(),
    )
    .unwrap();
    assert_eq!(
        output.iter().map(|v| v.value()).collect::<Vec<_>>(),
        vec![
            4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295
        ]
    );
}

#[test]
fn aggregate_modular_loop_preserves_scalar_mask() {
    let path =
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/modular_loop.tri");
    let code = trisha_rs::build_tasm(&path, "triton", "debug").unwrap();
    let result = VM::run(
        Program::from_code(&code).unwrap(),
        PublicInput::default(),
        NonDeterminism::default(),
    );
    let output = result.unwrap_or_else(|error| {
        panic!(
            "{}; public output {:?}",
            error, error.vm_state.public_output
        )
    });
    let mut expected = (0..32)
        .rev()
        .flat_map(|i| [1u64 << i, 1u64 << i])
        .collect::<Vec<_>>();
    expected.push(4294967295);
    assert_eq!(
        output.iter().map(|v| v.value()).collect::<Vec<_>>(),
        expected
    );
}

#[test]
fn low_256_product_matches_full_integer_low_bits() {
    let checker = program("mul256_low");
    assert_eq!(
        run(
            &checker,
            &[
                4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                4294967295
            ],
            &[
                4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                4294967295
            ],
            &[0; 8]
        )
        .unwrap(),
        [1, 0, 0, 0, 0, 0, 0, 0]
    );
    assert_eq!(
        run(
            &checker,
            &[0, 0, 0, 0, 0, 0, 0, 2147483648],
            &[0, 0, 0, 0, 0, 0, 0, 2147483648],
            &[0; 8]
        )
        .unwrap(),
        [0, 0, 0, 0, 0, 0, 0, 0]
    );
    assert_eq!(
        run(
            &checker,
            &[
                4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
                4294967295
            ],
            &[2, 0, 0, 0, 0, 0, 0, 0],
            &[0; 8]
        )
        .unwrap(),
        [
            4294967294, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295,
            4294967295
        ]
    );
    assert_eq!(
        run(
            &checker,
            &[
                2596069104, 305419896, 2596069104, 305419896, 2596069104, 305419896, 2596069104,
                305419896
            ],
            &[
                1985229328, 4275878552, 1985229328, 4275878552, 1985229328, 4275878552, 1985229328,
                4275878552
            ],
            &[0; 8]
        )
        .unwrap(),
        [
            1444466432, 594381054, 2209288738, 1492824583, 2974111044, 2391268112, 3738933350,
            3289711641
        ]
    );
}
