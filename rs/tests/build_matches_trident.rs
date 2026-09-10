//! The warrior's build must equal the compiler's, byte for byte.
//!
//! `trisha build` drives the lowering from TIR itself
//! (`trident::build_tir_modules` → TritonLowering → link) instead of
//! taking finished assembly from `trident build --target triton`. While
//! both paths exist, this pins them to the same output — so when the
//! compiler's copy goes away, any change in what programs actually get
//! shows up here rather than in a proof that stops verifying.

use std::path::Path;

/// What `trident build --target triton` produces.
fn trident_tasm(path: &Path) -> String {
    let mut options = trident::CompileOptions::for_profile("debug");
    options.target_config = trident::target::TerrainConfig::triton();
    trident::compile_project_with_options(path, &options)
        .map_err(|d| d.iter().map(|x| x.message.clone()).collect::<Vec<_>>().join("; "))
        .expect("trident builds this program")
}

/// What `trisha build` produces.
fn trisha_tasm(path: &Path) -> String {
    trisha_rs::build_tasm(path, "triton", "debug").expect("trisha builds this program")
}

fn write(name: &str, source: &str) -> std::path::PathBuf {
    let path = std::env::temp_dir().join(name);
    std::fs::write(&path, source).expect("write fixture");
    path
}

#[test]
fn arithmetic_program_lowers_identically() {
    let p = write(
        "trisha_build_arith.tri",
        "program trisha_build_arith\n\nfn main() {\n    let a: Field = pub_read()\n    pub_write(a * 7 + 3)\n}\n",
    );
    assert_eq!(trisha_tasm(&p), trident_tasm(&p));
}

#[test]
fn control_flow_lowers_identically() {
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
    assert_eq!(trisha_tasm(&p), trident_tasm(&p));
}

#[test]
fn multi_function_program_links_identically() {
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
    assert_eq!(tasm, trident_tasm(&p));
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
