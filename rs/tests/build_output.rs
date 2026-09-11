//! `trisha build` lowers what `trident::build_tir_modules` hands it.
//!
//! Until 2026-09-11 this test pinned trisha's output byte-for-byte against
//! `trident build --target triton`, which still had its own copy of the
//! Triton lowering during the migration. That copy is gone now (the core
//! stops at TIR — .claude/plans/warrior-owns-lowering.md S3 in trident),
//! so there is nothing left to compare against; these tests assert on
//! trisha's own output directly instead.

use std::path::Path;

fn trisha_tasm(path: &Path) -> String {
    trisha_rs::build_tasm(path, "triton", "debug").expect("trisha builds this program")
}

fn write(name: &str, source: &str) -> std::path::PathBuf {
    let path = std::env::temp_dir().join(name);
    std::fs::write(&path, source).expect("write fixture");
    path
}

#[test]
fn arithmetic_program_lowers_to_expected_tasm() {
    let p = write(
        "trisha_build_arith.tri",
        "program trisha_build_arith\n\nfn main() {\n    let a: Field = pub_read()\n    pub_write(a * 7 + 3)\n}\n",
    );
    let tasm = trisha_tasm(&p);
    assert!(tasm.contains("read_io 1"), "reads the public input");
    assert!(tasm.contains("mul"), "multiplies by 7");
    assert!(tasm.contains("add"), "adds 3");
    assert!(tasm.contains("write_io 1"), "writes the result");
    assert!(tasm.contains("halt"), "a linked program halts");
}

#[test]
fn control_flow_lowers_to_a_branch() {
    let p = write(
        "trisha_build_flow.tri",
        r#"program trisha_build_flow

fn main() {
    let x: Field = pub_read()
    if x == 0 {
        pub_write(1)
    } else {
        pub_write(x)
    }
}
"#,
    );
    let tasm = trisha_tasm(&p);
    assert!(tasm.contains("eq"), "compares x to 0");
    assert!(tasm.contains("skiz") || tasm.contains("call"), "branches on the comparison");
    assert!(tasm.contains("halt"), "a linked program halts");
}

#[test]
fn multi_function_program_links_into_one_program() {
    let p = write(
        "trisha_build_calls.tri",
        r#"program trisha_build_calls

fn double(x: Field) -> Field {
    x * 2
}

fn main() {
    let a: Field = pub_read()
    pub_write(double(a) + double(1))
}
"#,
    );
    let tasm = trisha_tasm(&p);
    assert!(
        tasm.contains("trisha_build_calls__double:"),
        "double is a labeled function"
    );
    assert!(
        tasm.contains("trisha_build_calls__main:"),
        "main is a labeled function"
    );
    assert!(
        tasm.contains("call trisha_build_calls__double"),
        "main calls double"
    );
    assert!(tasm.contains("halt"), "a linked program halts");
}

#[test]
fn a_program_that_does_not_compile_reports_the_error() {
    let p = write(
        "trisha_build_bad.tri",
        "program trisha_build_bad\n\nfn main() {\n    let x: U32 = pub_read()\n}\n",
    );
    let err = trisha_rs::build_tasm(&p, "triton", "debug")
        .expect_err("a type error must not produce assembly");
    assert!(!err.is_empty(), "the error carries the diagnostic text");
}
