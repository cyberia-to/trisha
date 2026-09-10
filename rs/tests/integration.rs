use std::path::Path;

use trident::runtime::{ProgramInput, Prover, Runner, Verifier};

use trisha_rs::convert;
use trisha_rs::Warrior;

/// Compile for Triton — this is the Triton warrior's suite. trident's own
/// default terrain is nox, where these programs' streaming I/O has no
/// meaning, so the warrior names its terrain (as `compile_source` does).
fn compile(path: &Path) -> Result<trident::runtime::ProgramBundle, String> {
    let mut options = trident::CompileOptions::for_profile("debug");
    options.target_config = trident::target::TerrainConfig::triton();
    trident::compile_to_bundle(path, &options)
        .map_err(|diags| diags.iter().map(|d| d.message.clone()).collect::<Vec<_>>().join("; "))
}

// ─── Runner Tests ──────────────────────────────────────────────────

#[test]
fn run_hello_world() {
    std::fs::write(
        "/tmp/test_hello.tri",
        "program test_hello\nfn main() {\n    pub_write(42)\n}\n",
    )
    .unwrap();
    let bundle = compile(Path::new("/tmp/test_hello.tri")).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput { public: vec![], secret: vec![], digests: vec![] };
    let result = warrior.run(&bundle, &input).unwrap();
    assert_eq!(result.output, vec![42]);
}

#[test]
fn run_with_public_input() {
    std::fs::write(
        "/tmp/test_square.tri",
        "program test_square\nfn main() {\n    let x = pub_read()\n    pub_write(x * x)\n}\n",
    )
    .unwrap();
    let bundle = compile(Path::new("/tmp/test_square.tri")).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput { public: vec![7], secret: vec![], digests: vec![] };
    let result = warrior.run(&bundle, &input).unwrap();
    assert_eq!(result.output, vec![49]);
}

#[test]
fn run_multiple_outputs() {
    std::fs::write(
        "/tmp/test_multi.tri",
        "program test_multi\nfn main() {\n    pub_write(10)\n    pub_write(20)\n    pub_write(30)\n}\n",
    )
    .unwrap();
    let bundle = compile(Path::new("/tmp/test_multi.tri")).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput { public: vec![], secret: vec![], digests: vec![] };
    let result = warrior.run(&bundle, &input).unwrap();
    assert_eq!(result.output, vec![10, 20, 30]);
}

// ─── Prover + Verifier Tests ──────────────────────────────────────

#[test]
fn prove_and_verify_hello() {
    std::fs::write(
        "/tmp/test_pv_hello.tri",
        "program test_pv_hello\nfn main() {\n    pub_write(42)\n}\n",
    )
    .unwrap();
    let bundle = compile(Path::new("/tmp/test_pv_hello.tri")).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput { public: vec![], secret: vec![], digests: vec![] };

    let proof_data = warrior.prove(&bundle, &input).unwrap();

    assert_eq!(proof_data.claim.public_output, vec![42]);
    assert_eq!(proof_data.format, "stark-triton-v2");
    assert!(!proof_data.proof_bytes.is_empty());

    let valid = warrior.verify(&proof_data).unwrap();
    assert!(valid, "valid proof should verify");
}

#[test]
fn prove_and_verify_with_input() {
    std::fs::write(
        "/tmp/test_pv_sq.tri",
        "program test_pv_sq\nfn main() {\n    let x = pub_read()\n    pub_write(x * x)\n}\n",
    )
    .unwrap();
    let bundle = compile(Path::new("/tmp/test_pv_sq.tri")).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput { public: vec![5], secret: vec![], digests: vec![] };

    let proof_data = warrior.prove(&bundle, &input).unwrap();
    assert_eq!(proof_data.claim.public_input, vec![5]);
    assert_eq!(proof_data.claim.public_output, vec![25]);

    let valid = warrior.verify(&proof_data).unwrap();
    assert!(valid);
}

#[test]
fn tampered_proof_fails_verification() {
    std::fs::write(
        "/tmp/test_tamper.tri",
        "program test_tamper\nfn main() {\n    pub_write(99)\n}\n",
    )
    .unwrap();
    let bundle = compile(Path::new("/tmp/test_tamper.tri")).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput { public: vec![], secret: vec![], digests: vec![] };

    let mut proof_data = warrior.prove(&bundle, &input).unwrap();

    if let Some(byte) = proof_data.proof_bytes.get_mut(100) {
        *byte = byte.wrapping_add(1);
    }

    let result = warrior.verify(&proof_data);
    match result {
        Ok(false) => {}
        Err(_) => {}
        Ok(true) => panic!("tampered proof should not verify"),
    }
}

// ─── Convert Tests ─────────────────────────────────────────────────

#[test]
fn u64_bfe_roundtrip() {
    let values = vec![0, 1, 42, 1000000007, 0xFFFFFFFF00000000];
    let bfes = convert::u64s_to_bfes(&values);
    let back = convert::bfes_to_u64s(&bfes);
    assert_eq!(back, values);
}

#[test]
fn empty_input_conversion() {
    let input = ProgramInput { public: vec![], secret: vec![], digests: vec![] };
    let (pub_in, non_det) = convert::to_triton_inputs(&input);
    assert!(pub_in.individual_tokens.is_empty());
    assert!(non_det.individual_tokens.is_empty());
}

// ─── Compile Error Tests ───────────────────────────────────────────

#[test]
fn missing_file_compile_error() {
    let result = compile(Path::new("/tmp/nonexistent_file_12345.tri"));
    assert!(result.is_err());
}
