//! Boundary expectations are frozen from Python integers, independent of limb code.
use triton_vm::prelude::*;
fn words(hex: &str) -> Vec<u64> {
    let value = format!("{hex:0>64}");
    value
        .as_bytes()
        .rchunks(8)
        .map(|b| u64::from_str_radix(std::str::from_utf8(b).unwrap(), 16).unwrap())
        .collect()
}
fn build(operation: &str, profile: &str) -> Program {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("boundaries.tri");
    let reads = (0..8)
        .map(|i| format!("let f{i}: U32 = as_u32(pub_read())\n"))
        .collect::<String>();
    let fields = (0..8)
        .map(|i| format!("l{i}: f{i}"))
        .collect::<Vec<_>>()
        .join(",");
    let call = match operation {
        "add256" => "let (result, carry) = bigint.add256(a,b)".to_string(),
        "sub256" => "let result = bigint.sub256(a,b)".into(),
        "mod_reduce_once" => "let result = bigint.mod_reduce_once(a,m)".into(),
        _ => format!("let result = bigint.{operation}(a,b,m)"),
    };
    let writes = (0..8)
        .map(|i| format!("pub_write(as_field(result.l{i}))\n"))
        .collect::<String>();
    let carry = if operation == "add256" {
        "pub_write(as_field(carry))"
    } else {
        ""
    };
    let source = format!("program boundaries\nuse std.crypto.bigint\nfn read() -> bigint.U256 {{ {reads} bigint.U256 {{ {fields} }} }}\nfn main() {{ let a = read()\n let b = read()\n let m = read()\n {call}\n {writes} {carry} }}\n");
    std::fs::write(&path, source).unwrap();
    Program::from_code(&trisha_rs::build_tasm(&path, "triton", profile).unwrap()).unwrap()
}
fn check(operation: &str, vectors: &[(&str, &str, &str, &str, u64)]) {
    for profile in ["debug", "release"] {
        let program = build(operation, profile);
        for &(a, b, m, expected, carry) in vectors {
            let input = words(a)
                .into_iter()
                .chain(words(b))
                .chain(words(m))
                .map(BFieldElement::new)
                .collect();
            let output = VM::run(
                program.clone(),
                PublicInput::new(input),
                NonDeterminism::default(),
            )
            .unwrap();
            let mut expected = words(expected);
            if operation == "add256" {
                expected.push(carry);
            }
            assert_eq!(
                output.iter().map(|v| v.value()).collect::<Vec<_>>(),
                expected,
                "{operation}/{profile}: {a}, {b}, {m}"
            );
        }
    }
}

#[test]
fn add256_boundary_vectors() {
    check(
        "add256",
        &[
            ("0", "0", "0", "0", 0),
            (
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "1",
                "0",
                "0",
                1,
            ),
            (
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "0",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe",
                1,
            ),
            ("ffffffff", "1", "0", "100000000", 0),
            (
                "ffffffffffffffffffffffffffffffff",
                "1",
                "0",
                "100000000000000000000000000000000",
                0,
            ),
            (
                "8000000000000000000000000000000000000000000000000000000000000000",
                "8000000000000000000000000000000000000000000000000000000000000000",
                "0",
                "0",
                1,
            ),
            (
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2e",
                "2",
                "0",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc30",
                0,
            ),
        ],
    );
}

#[test]
fn sub256_boundary_vectors() {
    check(
        "sub256",
        &[
            (
                "0",
                "1",
                "0",
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                0,
            ),
            (
                "0",
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "0",
                "1",
                0,
            ),
            (
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "1",
                "0",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe",
                0,
            ),
            (
                "100000000000000000000000000000000",
                "1",
                "0",
                "ffffffffffffffffffffffffffffffff",
                0,
            ),
            (
                "1",
                "8000000000000000000000000000000000000000000000000000000000000000",
                "0",
                "8000000000000000000000000000000000000000000000000000000000000001",
                0,
            ),
            (
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "0",
                "0",
                0,
            ),
        ],
    );
}

#[test]
fn add_mod_boundary_vectors() {
    check(
        "add_mod",
        &[
            ("0", "0", "61", "0", 0),
            ("60", "60", "61", "5f", 0),
            ("1", "60", "61", "0", 0),
            (
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2e",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2e",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2d",
                0,
            ),
            (
                "8000000000000000000000000000000000000000000000000000000000000000",
                "8000000000000000000000000000000000000000000000000000000000000000",
                "800000000000000000000000000000000000000000000000000000000000007b",
                "7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff85",
                0,
            ),
            (
                "0",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2e",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2e",
                0,
            ),
        ],
    );
}

#[test]
fn sub_mod_boundary_vectors() {
    check(
        "sub_mod",
        &[
            ("0", "0", "61", "0", 0),
            ("60", "60", "61", "0", 0),
            ("1", "60", "61", "2", 0),
            (
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2e",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2e",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f",
                "0",
                0,
            ),
            (
                "8000000000000000000000000000000000000000000000000000000000000000",
                "8000000000000000000000000000000000000000000000000000000000000000",
                "800000000000000000000000000000000000000000000000000000000000007b",
                "0",
                0,
            ),
            (
                "0",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2e",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f",
                "1",
                0,
            ),
        ],
    );
}

#[test]
fn mod_reduce_once_boundary_vectors() {
    check(
        "mod_reduce_once",
        &[
            ("0", "0", "61", "0", 0),
            ("60", "0", "61", "60", 0),
            ("61", "0", "61", "0", 0),
            ("c1", "0", "61", "60", 0),
            (
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f",
                "0",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f",
                "0",
                0,
            ),
            (
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "0",
                "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f",
                "1000003d0",
                0,
            ),
            (
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "0",
                "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "0",
                0,
            ),
        ],
    );
}

#[test]
fn aggregate_branch_returns_with_different_local_counts_preserve_caller() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("branches.tri");
    let source = "program branches\nuse std.crypto.bigint\nfn choose(a: bigint.U256,b: bigint.U256,flag: Field) -> (bigint.U256,U32) { if flag == 0 { let tag: U32 = as_u32(17)\n (a,tag) } else { let first: Field = 19\n let second: Field = first + 2\n let tag: U32 = as_u32(second)\n (b,tag) } }\nfn main() { let a = bigint.from_u32(as_u32(7))\n let b = bigint.from_u32(as_u32(13))\n let survivor: Field = 77\n let flag = pub_read()\n let (result,tag) = choose(a,b,flag)\n pub_write(as_field(result.l0))\n pub_write(as_field(tag))\n pub_write(survivor) }\n";
    std::fs::write(&path, source).unwrap();
    for profile in ["debug", "release"] {
        let program =
            Program::from_code(&trisha_rs::build_tasm(&path, "triton", profile).unwrap()).unwrap();
        for (flag, expected) in [(0, vec![7, 17, 77]), (1, vec![13, 21, 77])] {
            let output = VM::run(
                program.clone(),
                PublicInput::new(vec![BFieldElement::new(flag)]),
                NonDeterminism::default(),
            )
            .unwrap();
            assert_eq!(
                output.iter().map(|v| v.value()).collect::<Vec<_>>(),
                expected,
                "{profile}/{flag}"
            );
        }
    }
}
