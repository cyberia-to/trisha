//! Source Field literals denote residues, even when their integer spelling exceeds p.
use triton_vm::prelude::*;

#[test]
fn field_literals_and_constants_emit_canonical_native_words() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("field.tri");
    std::fs::write(
        &path,
        "program fields
const ZERO:Field=18446744069414584321
const MAX:Field=18446744073709551615
fn choose()->Field {if ZERO==0 {7} else {9}}
fn main() {
 pub_write(18446744069414584321)
 pub_write(18446744069414584322)
 pub_write(MAX)
 pub_write(18446744069414584320+1)
 pub_write(choose())
}",
    )
    .unwrap();
    for profile in ["debug", "release"] {
        let assembly = trisha_rs::build_tasm(&path, "triton", profile).unwrap();
        let program = Program::from_code(&assembly).unwrap();
        let output = VM::run(program, PublicInput::default(), NonDeterminism::default()).unwrap();
        assert_eq!(output, bfe_vec![0, 1, 4294967294u64, 0, 7]);
    }
}

#[test]
fn u32_literals_keep_integer_bounds_instead_of_wrapping_as_fields() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("integer.tri");
    for value in [4294967296u64, 18446744069414584321, u64::MAX] {
        std::fs::write(&path, format!("program integer\nfn value()->U32 {{{value}}}\nfn main() {{pub_write(as_field(value()))}}")).unwrap();
        for profile in ["debug", "release"] {
            assert!(trisha_rs::build_tasm(&path, "triton", profile).is_err());
        }
    }
}
