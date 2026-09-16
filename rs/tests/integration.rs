use std::path::Path;

use trident::runtime::{ProgramInput, Prover, Runner, Verifier};

use trisha_rs::convert;
use trisha_rs::Warrior;

/// Compile for Triton — this is the Triton warrior's suite. trident's own
/// default terrain is nox, where these programs' streaming I/O has no
/// meaning, so the warrior names its terrain (as `compile_source` does).
fn compile(path: &Path) -> Result<trident::runtime::ProgramBundle, String> {
    // trident::compile_to_bundle no longer lowers to Triton in-process (the
    // core stops at TIR); the warrior does its own build and wraps the
    // result, the same shape `bundle_from_tasm` uses for a raw .tasm file.
    let assembly = trisha_rs::build_tasm(path, "triton", "debug")?;
    let name = path
        .file_stem()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string();
    let source_hash = trident::hash::content_hash_bytes(assembly.as_bytes());
    Ok(trident::runtime::ProgramBundle {
        name,
        version: String::new(),
        target_vm: "triton".to_string(),
        target_os: None,
        assembly,
        entry_point: String::new(),
        functions: Vec::new(),
        cost: trident::runtime::artifact::BundleCost {
            table_values: Vec::new(),
            table_names: Vec::new(),
            padded_height: 0,
            estimated_proving_ns: 0,
        },
        source_hash: trident::hash::ContentHash(source_hash).to_hex(),
        reads_state: false,
    })
}

// ─── Runner Tests ──────────────────────────────────────────────────

#[test]
fn run_hello_world() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("test_hello.tri");
    std::fs::write(
        &path,
        "program test_hello\nfn main() {\n    pub_write(42)\n}\n",
    )
    .unwrap();
    let bundle = compile(&path).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };
    let result = warrior.run(&bundle, &input).unwrap();
    assert_eq!(result.output, vec![42]);
}

#[test]
fn run_with_public_input() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("test_square.tri");
    std::fs::write(
        &path,
        "program test_square\nfn main() {\n    let x = pub_read()\n    pub_write(x * x)\n}\n",
    )
    .unwrap();
    let bundle = compile(&path).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput {
        public: vec![7],
        secret: vec![],
        digests: vec![],
    };
    let result = warrior.run(&bundle, &input).unwrap();
    assert_eq!(result.output, vec![49]);
}

#[test]
fn run_multiple_outputs() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("test_multi.tri");
    std::fs::write(
        &path,
        "program test_multi\nfn main() {\n    pub_write(10)\n    pub_write(20)\n    pub_write(30)\n}\n",
    )
    .unwrap();
    let bundle = compile(&path).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };
    let result = warrior.run(&bundle, &input).unwrap();
    assert_eq!(result.output, vec![10, 20, 30]);
}

// ─── Prover + Verifier Tests ──────────────────────────────────────

#[test]
fn prove_and_verify_hello() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("test_pv_hello.tri");
    std::fs::write(
        &path,
        "program test_pv_hello\nfn main() {\n    pub_write(42)\n}\n",
    )
    .unwrap();
    let bundle = compile(&path).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };

    let proof_data = warrior.prove(&bundle, &input).unwrap();

    assert_eq!(proof_data.claim.public_output, vec![42]);
    assert_eq!(proof_data.format, "stark-triton-v7");
    assert!(!proof_data.proof_bytes.is_empty());

    let valid = warrior.verify(&proof_data).unwrap();
    assert!(valid, "valid proof should verify");
}

#[test]
fn prove_and_verify_with_input() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("test_pv_sq.tri");
    std::fs::write(
        &path,
        "program test_pv_sq\nfn main() {\n    let x = pub_read()\n    pub_write(x * x)\n}\n",
    )
    .unwrap();
    let bundle = compile(&path).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput {
        public: vec![5],
        secret: vec![],
        digests: vec![],
    };

    let proof_data = warrior.prove(&bundle, &input).unwrap();
    assert_eq!(proof_data.claim.public_input, vec![5]);
    assert_eq!(proof_data.claim.public_output, vec![25]);

    let valid = warrior.verify(&proof_data).unwrap();
    assert!(valid);
}

#[test]
fn tampered_proof_fails_verification() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("test_tamper.tri");
    std::fs::write(
        &path,
        "program test_tamper\nfn main() {\n    pub_write(99)\n}\n",
    )
    .unwrap();
    let bundle = compile(&path).unwrap();
    let warrior = Warrior::new();
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };

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
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };
    let (pub_in, non_det) = convert::to_triton_inputs(&input).unwrap();
    assert!(pub_in.individual_tokens.is_empty());
    assert!(non_det.individual_tokens.is_empty());
}

// ─── Compile Error Tests ───────────────────────────────────────────

#[test]
fn missing_file_compile_error() {
    let dir = tempfile::tempdir().unwrap();
    let result = compile(&dir.path().join("nonexistent.tri"));
    assert!(result.is_err());
}

#[test]
fn spilling_preserves_twenty_five_live_values() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("spill.tri");
    let mut source = String::from("program spill\nfn main() {\n");
    for i in 0..25 {
        source.push_str(&format!("let x{i} = pub_read()\n"));
    }
    for i in 0..25 {
        source.push_str(&format!("pub_write(x{i})\n"));
    }
    source.push_str("}\n");
    std::fs::write(&path, source).unwrap();
    let bundle = compile(&path).unwrap();
    let values: Vec<u64> = (1..=25).collect();
    let result = Warrior::new()
        .run(
            &bundle,
            &ProgramInput {
                public: values.clone(),
                secret: vec![],
                digests: vec![],
            },
        )
        .unwrap();
    assert_eq!(result.output, values);
}

#[test]
fn deep_array_access_preserves_value_order() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("deep_array.tri");
    let mut source = String::from("program deep_array\nfn main() {\nlet a: [Field; 32] = [");
    source.push_str(&vec!["pub_read()"; 32].join(", "));
    source.push_str("]\n");
    for i in [0, 7, 15, 24, 31] {
        source.push_str(&format!("pub_write(a[{i}])\n"));
    }
    source.push_str("}\n");
    std::fs::write(&path, source).unwrap();
    let bundle = compile(&path).unwrap();
    let result = Warrior::new()
        .run(
            &bundle,
            &ProgramInput {
                public: (1..=32).collect(),
                secret: vec![],
                digests: vec![],
            },
        )
        .unwrap();
    assert_eq!(result.output, vec![1, 8, 16, 25, 32]);
}

#[test]
fn malformed_claims_are_rejected_without_normalization() {
    assert!(convert::to_triton_claim_native(&[0; 4], &[], &[]).is_err());
    assert!(convert::to_triton_claim_native(&[0; 6], &[], &[]).is_err());
    assert!(convert::to_triton_claim_native(&[0; 5], &[18_446_744_069_414_584_321], &[]).is_err());
}

#[test]
fn bundle_identity_and_state_requirements_are_enforced() {
    use trident::runtime::Guesser;
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("guard.tri");
    std::fs::write(&path, "program guard\nfn main() { pub_write(1) }\n").unwrap();
    let bundle = compile(&path).unwrap();
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };
    let warrior = Warrior::new();
    for mutation in 0..3 {
        let mut altered = bundle.clone();
        match mutation {
            0 => altered.target_vm = "nox".into(),
            1 => altered.target_os = Some("cyber".into()),
            _ => altered.reads_state = true,
        }
        assert!(warrior.run(&altered, &input).is_err());
        assert!(warrior.prove_full(&altered, &input).is_err());
        assert!(warrior.guess(&altered, &input, u64::MAX, 1).is_err());
    }
}

#[test]
fn sha256_module_assembly_uses_only_valid_stack_registers() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../trident");
    let assembly =
        trisha_rs::build_tasm(&root.join("lib/std/crypto/sha256.tri"), "triton", "release")
            .unwrap();
    triton_vm::prelude::Program::from_code(&assembly)
        .expect("SHA256 assembly must parse on the pinned VM");
}

#[test]
fn sha256_empty_block_matches_fips_digest() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("sha_empty.tri");
    let words = std::iter::once("convert.as_u32(2147483648)")
        .chain(std::iter::repeat_n("convert.as_u32(0)", 15))
        .collect::<Vec<_>>()
        .join(", ");
    let mut source = format!(
        "program sha_empty\nuse std.crypto.sha256\nuse vm.core.convert\nfn main() {{\nlet result = sha256.compress(sha256.init(), {words})\n"
    );
    for i in 0..8 {
        source.push_str(&format!("pub_write(convert.as_field(result.h{i}))\n"));
    }
    source.push_str("}\n");
    std::fs::write(&path, source).unwrap();
    let assembly = trisha_rs::build_tasm(&path, "triton", "release").unwrap();
    let program = triton_vm::prelude::Program::from_code(&assembly).unwrap();
    let output = triton_vm::prelude::VM::run(
        program,
        triton_vm::prelude::PublicInput::default(),
        triton_vm::prelude::NonDeterminism::default(),
    )
    .unwrap_or_else(|e| panic!("{}", e));
    let expected = [
        0xe3b0c442u64,
        0x98fc1c14,
        0x9afbf4c8,
        0x996fb924,
        0x27ae41e4,
        0x649b934c,
        0xa495991b,
        0x7852b855,
    ];
    assert_eq!(convert::bfes_to_u64s(&output), expected);
}

#[test]
fn sha256_helpers_match_rust_integer_operations() {
    let dir = tempfile::tempdir().unwrap();
    let source_path = dir.path().join("helper.tri");
    let words = vec!["convert.as_u32(0)"; 16].join(", ");
    std::fs::write(&source_path, format!("program helper\nuse std.crypto.sha256\nuse vm.core.convert\nfn main() {{ let st = sha256.compress(sha256.init(), {words}) }}\n")).unwrap();
    let linked = trisha_rs::build_tasm(&source_path, "triton", "release").unwrap();
    let library = linked.lines().skip(2).collect::<Vec<_>>().join("\n");
    let x = 0x1234abcdu32;
    let cases: Vec<(&str, Vec<u64>, u32)> = vec![
        (
            "ch",
            vec![0x510e527f, 0x9b05688c, 0x1f83d9ab],
            (0x510e527fu32 & 0x9b05688c) ^ (!0x510e527fu32 & 0x1f83d9ab),
        ),
        (
            "maj",
            vec![0x6a09e667, 0xbb67ae85, 0x3c6ef372],
            (0x6a09e667u32 & 0xbb67ae85)
                ^ (0x6a09e667u32 & 0x3c6ef372)
                ^ (0xbb67ae85u32 & 0x3c6ef372),
        ),
        (
            "add32",
            vec![0xfffffff0, 123],
            0xfffffff0u32.wrapping_add(123),
        ),
        ("rotr", vec![x.into(), 128, 33554432], x.rotate_right(7)),
        ("shr", vec![x.into(), 1024], x >> 10),
        (
            "big_sigma0",
            vec![x.into()],
            x.rotate_right(2) ^ x.rotate_right(13) ^ x.rotate_right(22),
        ),
        (
            "big_sigma1",
            vec![x.into()],
            x.rotate_right(6) ^ x.rotate_right(11) ^ x.rotate_right(25),
        ),
        (
            "little_sigma0",
            vec![x.into()],
            x.rotate_right(7) ^ x.rotate_right(18) ^ (x >> 3),
        ),
        (
            "little_sigma1",
            vec![x.into()],
            x.rotate_right(17) ^ x.rotate_right(19) ^ (x >> 10),
        ),
    ];
    let state = [
        0x6a09e667u32,
        0xbb67ae85,
        0x3c6ef372,
        0xa54ff53a,
        0x510e527f,
        0x9b05688c,
        0x1f83d9ab,
        0x5be0cd19,
    ];
    let [a, b, c, d, e, f, g, h] = state;
    let t1 = h
        .wrapping_add(e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25))
        .wrapping_add((e & f) ^ (!e & g))
        .wrapping_add(0x428a2f98)
        .wrapping_add(0x80000000);
    let t2 = (a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22))
        .wrapping_add((a & b) ^ (a & c) ^ (b & c));
    let round_out = [t1.wrapping_add(t2), a, b, c, d.wrapping_add(t1), e, f, g];
    let round_args = state
        .iter()
        .map(|&x| u64::from(x))
        .chain([0x428a2f98, 0x80000000])
        .collect::<Vec<_>>();
    let mut asm = round_args
        .iter()
        .map(|v| format!("push {v}\n"))
        .collect::<String>();
    asm.push_str(&format!(
        "call std_crypto_sha256__round\n{}halt\n{library}",
        "write_io 1\n".repeat(8)
    ));
    let program = triton_vm::prelude::Program::from_code(&asm).unwrap();
    let output = triton_vm::prelude::VM::run(program, Default::default(), Default::default())
        .unwrap_or_else(|e| panic!("{}", e));
    let actual_round = convert::bfes_to_u64s(&output);
    for (name, args, expected) in cases {
        let mut assembly = args
            .iter()
            .map(|v| format!("push {v}\n"))
            .collect::<String>();
        assembly.push_str(&format!(
            "call std_crypto_sha256__{name}\nwrite_io 1\nhalt\n{library}"
        ));
        let program = triton_vm::prelude::Program::from_code(&assembly).unwrap();
        let output = triton_vm::prelude::VM::run(program, Default::default(), Default::default())
            .unwrap_or_else(|e| panic!("{}", e));
        assert_eq!(
            convert::bfes_to_u64s(&output),
            vec![u64::from(expected)],
            "{name}"
        );
    }
    assert_eq!(
        actual_round,
        round_out
            .iter()
            .rev()
            .map(|&x| u64::from(x))
            .collect::<Vec<_>>(),
        "round"
    );
}

#[test]
fn private_witness_failures_do_not_dump_vm_state() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("private_failure.tri");
    std::fs::write(
        &path,
        "program private_failure\nfn main() { assert_eq(divine(), 0) }\n",
    )
    .unwrap();
    let bundle = compile(&path).unwrap();
    let input = ProgramInput {
        public: vec![],
        secret: vec![987654321012345],
        digests: vec![],
    };
    let warrior = Warrior::new();
    for error in [
        warrior.run(&bundle, &input).unwrap_err(),
        warrior.run_bounded(&bundle, &input, 1000).unwrap_err(),
        warrior
            .prove_full(&bundle, &input)
            .err()
            .expect("invalid witness"),
    ] {
        assert_eq!(error, "execution error: program rejected private witness");
        assert!(!error.contains("987654321012345"));
    }
    let mut looping = bundle;
    looping.assembly = "call forever halt forever: recurse".into();
    let error = warrior.run_bounded(&looping, &input, 32).unwrap_err();
    assert_eq!(error, "execution budget exceeded: 32 cycles");
}
