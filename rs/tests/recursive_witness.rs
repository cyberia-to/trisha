//! Exercise witness transport and caller claim binding independently of host preprocessing.
use trident::runtime::ProgramInput;
use trisha_rs::recursive;
use triton_vm::prelude::*;

fn execute(input: &ProgramInput) -> Result<u32, String> {
    let code = format!(
        "read_io 5 call {} halt\n{}",
        recursive::ENTRYPOINT,
        recursive::assembly()
    );
    let program = Program::from_code(&code).map_err(|e| e.to_string())?;
    let (public, secret) = trisha_rs::convert::to_triton_inputs(input).unwrap();
    let mut state = VMState::new(program, public, secret);
    for _ in 0..5_000_000 {
        if state.halting {
            return Ok(state.cycle_count);
        }
        state.step().map_err(|e| e.to_string())?;
    }
    Err("bounded recursive adapter exceeded5Mcycles".into())
}

#[test]
fn witness_adapter_binds_caller_claim_and_rejects_malformed_transport() {
    let program = Program::from_code("read_io 1 push 3 add write_io 1 halt").unwrap();
    let (trace, output) = VM::trace_execution(
        program.clone(),
        vec![BFieldElement::new(2)].into(),
        NonDeterminism::default(),
    )
    .unwrap();
    let claim = Claim::about_program(&program)
        .with_input(vec![BFieldElement::new(2)])
        .with_output(output);
    let proof = Stark::default().prove(&claim, &trace).unwrap();
    let witness = recursive::encode(&claim, &proof).unwrap();
    let cycles =
        execute(&witness).expect("bounded loader and official verifier accept actual proof");
    eprintln!("recursive witness loader+verifier cycles: {cycles}");
    for mutation in 0..6 {
        let mut changed = claim.clone();
        match mutation {
            0 => changed.program_digest = Digest::default(),
            1 => changed.input[0] += BFieldElement::new(1),
            2 => changed.output[0] += BFieldElement::new(1),
            3 => changed.version += 1,
            4 => changed.input.push(BFieldElement::new(0)),
            _ => changed.output.push(BFieldElement::new(0)),
        }
        assert!(
            recursive::encode(&changed, &proof).is_err(),
            "host accepted altered claim"
        );
        // Bypass host verification: update both serialized claim and caller commitment.
        // The official VM verifier must still reject the original proof for this new claim.
        let mut bypass = witness.clone();
        let encoded = changed.encode();
        let old_length = bypass.secret[1] as usize;
        bypass.secret[1] = encoded.len() as u64;
        bypass.secret.splice(
            2..2 + old_length,
            encoded.into_iter().map(|value| value.value()),
        );
        bypass.public = recursive::claim_commitment(&changed)
            .values()
            .map(|v| v.value())
            .to_vec();
        assert!(
            execute(&bypass).is_err(),
            "VM accepted changed claim{mutation}"
        );
    }
    let proof_length_offset = 2 + witness.secret[1] as usize;
    for (offset, value) in [
        (0, 2),
        (1, 0),
        (1, recursive::MAX_CLAIM_WORDS as u64 + 1),
        (proof_length_offset, 0),
        (proof_length_offset, recursive::MAX_PROOF_WORDS as u64 + 1),
    ] {
        let mut malformed = witness.clone();
        malformed.secret[offset] = value;
        assert!(
            execute(&malformed).is_err(),
            "malformed envelope accepted at{offset}"
        );
    }
    let mut bad_commitment = witness.clone();
    bad_commitment.public[0] = (bad_commitment.public[0] + 1) % BFieldElement::P;
    assert!(execute(&bad_commitment).is_err());
    let mut bad_proof = witness.clone();
    bad_proof.secret[proof_length_offset + 1] += 1;
    assert!(
        execute(&bad_proof).is_err(),
        "internal proof length mismatch accepted"
    );
}

#[test]
fn compiled_sdk_verifies_real_proof_and_preserves_callers_values() {
    let inner = Program::from_code("read_io 1 push 3 add write_io 1 halt").unwrap();
    let (trace, output) = VM::trace_execution(
        inner.clone(),
        vec![BFieldElement::new(2)].into(),
        NonDeterminism::default(),
    )
    .unwrap();
    let claim = Claim::about_program(&inner)
        .with_input(vec![BFieldElement::new(2)])
        .with_output(output);
    let proof = Stark::default().prove(&claim, &trace).unwrap();
    let artifact = trident::runtime::ProofData {
        claim: trisha_rs::convert::to_trident_claim(&claim),
        proof_bytes: trisha_rs::convert::proof_to_bytes(&proof),
        format: "stark-triton-v7".into(),
    };
    let mut input = recursive::encode_proof_data(&claim, &artifact).unwrap();
    input.public.insert(0, 41);
    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("main.tri");
    std::fs::write(&source,"program recursive_sdk\nuse vm.triton.proof\nuse vm.io.io\nfn verify_one(claim: Digest) { proof.verify(claim) }\nfn main() { let kept=pub_read() let expected=io.read_digest() verify_one(expected) pub_write(kept+1) }\n").unwrap();
    let code = trisha_rs::build_tasm(&source, "triton", "release")
        .expect("owned intrinsic compiles through generic target ABI");
    let program = Program::from_code(&code).expect("official snippet linked completely");
    let execute_sdk = |input: &ProgramInput| {
        let (public, private) = trisha_rs::convert::to_triton_inputs(input).unwrap();
        let mut state = VMState::new(program.clone(), public, private);
        for _ in 0..3_000_000 {
            if state.halting {
                return Ok(state);
            }
            state.step().map_err(|_| "SDK rejected witness")?;
        }
        Err("SDK cycle budget exceeded")
    };
    let state = execute_sdk(&input).expect("compiled SDK verifies official proof");
    assert_eq!(state.public_output, vec![BFieldElement::new(42)]);
    eprintln!("compiled recursive SDK cycles: {}", state.cycle_count);
    input.public[1] = (input.public[1] + 1) % BFieldElement::P;
    assert!(
        execute_sdk(&input).is_err(),
        "changed outer public commitment accepted"
    );
    let mut trailing = artifact.clone();
    trailing.proof_bytes.push(0);
    assert!(recursive::encode_proof_data(&claim, &trailing).is_err());
    let mut aliased = artifact;
    let (index, value) = aliased
        .proof_bytes
        .chunks_exact(8)
        .enumerate()
        .skip(1)
        .map(|(index, word)| (index, u64::from_le_bytes(word.try_into().unwrap())))
        .find(|(_, value)| *value <= u64::MAX - BFieldElement::P)
        .expect("proof contains a small canonical field");
    aliased.proof_bytes[index * 8..index * 8 + 8]
        .copy_from_slice(&(value + BFieldElement::P).to_le_bytes());
    assert!(
        recursive::encode_proof_data(&claim, &aliased).is_err(),
        "noncanonical raw field alias accepted"
    );
}

#[test]
fn malformed_raw_target_calls_fail_before_lowering() {
    use trident::tir::TIROp;
    for (name, inputs, outputs) in [
        ("triton_stark_verify_v1", 4, 0),
        ("triton_stark_verify_v1", 5, 1),
        ("unknown_target_operation", 5, 0),
    ] {
        let ops = [TIROp::IfOnly {
            then_body: vec![TIROp::TargetCall {
                name: name.into(),
                inputs,
                outputs,
            }],
        }];
        assert!(trisha_rs::lower::lower_checked(&ops).is_err());
    }
}

#[test]
fn neptune_transaction_entry_requires_an_actual_proof() {
    let program = Program::from_code(include_str!(
        "../../baselines/triton/os/neptune/programs/transaction_validation.tasm"
    ))
    .unwrap();
    let input = PublicInput::new(vec![BFieldElement::new(0); 5]);
    assert!(
        VM::run(program, input, NonDeterminism::default()).is_err(),
        "empty witness cannot authorize a transaction"
    );
}

/// A release gate: expensive enough to run explicitly, always at default security.
#[test]
#[ignore = "full outer STARK proof; run explicitly in release mode with four Rayon threads"]
fn outer_proof_binds_compiled_recursive_sdk_to_public_claim() {
    let started = std::time::Instant::now();
    let inner = Program::from_code("read_io 1 push 3 add write_io 1 halt").unwrap();
    let (inner_trace, inner_output) = VM::trace_execution(
        inner.clone(),
        vec![BFieldElement::new(2)].into(),
        NonDeterminism::default(),
    )
    .unwrap();
    let inner_claim = Claim::about_program(&inner)
        .with_input(vec![BFieldElement::new(2)])
        .with_output(inner_output);
    let inner_proof = Stark::default().prove(&inner_claim, &inner_trace).unwrap();
    let input = recursive::encode(&inner_claim, &inner_proof).unwrap();
    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("main.tri");
    std::fs::write(&source, "program recursive_release\nuse vm.triton.proof\nuse vm.io.io\nfn main() { let expected=io.read_digest() proof.verify(expected) pub_write(1) }\n").unwrap();
    let code = trisha_rs::build_tasm(&source, "triton", "release").unwrap();
    let outer = Program::from_code(&code).unwrap();
    let (public, private) = trisha_rs::convert::to_triton_inputs(&input).unwrap();
    let (trace, output) = VM::trace_execution(outer.clone(), public, private).unwrap();
    assert_eq!(output, vec![BFieldElement::new(1)]);
    let outer_claim = Claim::about_program(&outer)
        .with_input(
            input
                .public
                .iter()
                .copied()
                .map(BFieldElement::new)
                .collect::<Vec<_>>(),
        )
        .with_output(output);
    eprintln!(
        "outer recursive trace ready after {:?}; cycles {}; padded height {}",
        started.elapsed(),
        trace.processor_trace.nrows(),
        trace.padded_height()
    );
    let prove_started = std::time::Instant::now();
    let proof = Stark::default().prove(&outer_claim, &trace).unwrap();
    eprintln!(
        "outer recursive proof generated in {:?}; {} encoded fields",
        prove_started.elapsed(),
        proof.encode().len()
    );
    drop(trace);
    Stark::default()
        .verify(&outer_claim, &proof)
        .expect("fresh verifier accepts outer recursive proof");
    for mutation in 0..3 {
        let mut changed = outer_claim.clone();
        match mutation {
            0 => changed.input[0] += BFieldElement::new(1),
            1 => changed.output[0] += BFieldElement::new(1),
            _ => changed.program_digest = Digest::default(),
        }
        assert!(
            Stark::default().verify(&changed, &proof).is_err(),
            "outer proof accepted changed claim {mutation}"
        );
    }
    eprintln!(
        "outer recursive release gate passed in {:?}",
        started.elapsed()
    );
}
