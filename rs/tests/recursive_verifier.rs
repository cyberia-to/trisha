//! Official Triton7 verifier, including upstream Fiat-Shamir and size-bound guards.
use tasm_lib::library::Library;
use tasm_lib::memory::encode_to_memory;
use tasm_lib::structure::tasm_object::TasmObject;
use tasm_lib::verifier::stark_verify::StarkVerify;
use tasm_lib::verifier::vm_proof_iter::dequeue_next_as::DequeueNextAs;
use tasm_lib::verifier::vm_proof_iter::new::New;
use triton_vm::prelude::*;
use triton_vm::proof_item::{ProofItem, ProofItemVariant};
use triton_vm::proof_stream::ProofStream;
use twenty_first::prelude::Polynomial;

fn run(program: Program, input: NonDeterminism) -> Result<VMState, String> {
    let mut state = VMState::new(program, PublicInput::default(), input);
    for _ in 0..10_000_000 {
        if state.halting {
            return Ok(state);
        }
        state.step().map_err(|e| e.to_string())?;
    }
    Err("recursive verifier exceeded bounded test execution".into())
}

#[test]
fn upstream_fiat_shamir_size_word_forgery_is_rejected() {
    let mut library = Library::new();
    let new = library.import(Box::new(New));
    let dequeue = library.import(Box::new(DequeueNextAs::new(ProofItemVariant::MerkleRoot)));
    let code = triton_asm!(push 0 call {new} sponge_init call {dequeue} pop 1 halt {&library.all_imports()});
    let program = Program::new(&code);
    let test = |root: Digest, size: Option<u64>| {
        let mut stream = ProofStream::new();
        stream.enqueue(ProofItem::MerkleRoot(root));
        let proof: Proof = stream.into();
        let mut nd = NonDeterminism::default();
        encode_to_memory(&mut nd.ram, BFieldElement::new(0), &proof);
        assert_eq!(
            nd.ram[&BFieldElement::new(4)].value(),
            6,
            "canonical static item length"
        );
        if let Some(size) = size {
            nd.ram
                .insert(BFieldElement::new(4), BFieldElement::new(size));
        }
        run(program.clone(), nd)
    };
    let a = Digest::new([1, 2, 3, 4, 5].map(BFieldElement::new));
    let b = Digest::new([9, 9, 9, 9, 9].map(BFieldElement::new));
    assert_ne!(
        test(a, None).unwrap().sponge.unwrap().state,
        test(b, None).unwrap().sponge.unwrap().state
    );
    for root in [a, b] {
        for size in [0, 1, 5, 7] {
            assert!(test(root, Some(size)).is_err());
        }
    }
}

#[test]
fn modular_wrap_cannot_fake_vector_encoding_length() {
    let mut library = Library::new();
    let body = <Vec<Digest>>::compute_size_and_assert_valid_size_indicator(&mut library);
    let program = Program::new(&triton_asm!(push 100 {&body} pop 1 halt {&library.all_imports()}));
    let mut nd = NonDeterminism::default();
    nd.ram
        .insert(BFieldElement::new(100), BFieldElement::new(2));
    assert!(run(program.clone(), nd.clone()).is_ok());
    //5*len==6 (modp), but len is huge. Prior modular size arithmetic accepted it.
    nd.ram.insert(
        BFieldElement::new(100),
        BFieldElement::new(5).inverse() * BFieldElement::new(6),
    );
    assert!(run(program, nd).is_err());

    let mut library = Library::new();
    let body = <Polynomial<'static, XFieldElement>>::compute_size_and_assert_valid_size_indicator(
        &mut library,
    );
    let program = Program::new(&triton_asm!(push 100 {&body} pop 1 halt {&library.all_imports()}));
    let mut nd = NonDeterminism::default();
    // Canonical size7 = 1 + 3*2 coefficients. Only the size validator is exercised.
    nd.ram
        .insert(BFieldElement::new(100), BFieldElement::new(7));
    nd.ram
        .insert(BFieldElement::new(101), BFieldElement::new(2));
    assert!(run(program.clone(), nd.clone()).is_ok());
    // Prior modular arithmetic also accepted size8 when 3*len == 7 mod p.
    nd.ram
        .insert(BFieldElement::new(100), BFieldElement::new(8));
    nd.ram.insert(
        BFieldElement::new(101),
        BFieldElement::new(3).inverse() * BFieldElement::new(7),
    );
    assert!(run(program, nd).is_err());
}

#[test]
fn official_recursive_verifier_accepts_real_proof_and_binds_complete_claim() {
    let inner = Program::from_code("read_io 1 push 3 add write_io 1 halt").unwrap();
    let input = PublicInput::new(vec![BFieldElement::new(2)]);
    let (trace, output) =
        VM::trace_execution(inner.clone(), input.clone(), NonDeterminism::default()).unwrap();
    let claim = Claim::about_program(&inner)
        .with_input(input.individual_tokens)
        .with_output(output);
    let stark = Stark::default();
    let proof = stark.prove(&claim, &trace).unwrap();
    assert!(stark.verify(&claim, &proof).is_ok());
    let snippet = StarkVerify::new_with_dynamic_layout(stark);
    let mut library = Library::new();
    let label = library.import(Box::new(snippet));
    let claim_address = BFieldElement::new(1 << 30);
    let program = Program::new(
        &triton_asm!(push {claim_address} push 0 call {label} halt {&library.all_imports()}),
    );
    let mut nd = NonDeterminism::default();
    snippet.update_nondeterminism(&mut nd, &proof, &claim);
    encode_to_memory(&mut nd.ram, BFieldElement::new(0), &proof);
    encode_to_memory(&mut nd.ram, claim_address, &claim);
    let state =
        run(program.clone(), nd.clone()).expect("official verifier accepts actual256-row proof");
    eprintln!("recursive verifier actual cycles: {}", state.cycle_count);
    for mutation in 0..3 {
        let mut altered = claim.clone();
        match mutation {
            0 => altered.program_digest = Digest::default(),
            1 => altered.input[0] += BFieldElement::new(1),
            _ => altered.output[0] += BFieldElement::new(1),
        }
        let mut invalid = nd.clone();
        encode_to_memory(&mut invalid.ram, claim_address, &altered);
        assert!(
            run(program.clone(), invalid).is_err(),
            "claim mutation{mutation} accepted"
        );
    }
    let mut invalid = nd;
    invalid
        .ram
        .insert(BFieldElement::new(4), BFieldElement::new(1));
    assert!(
        run(program, invalid).is_err(),
        "noncanonical proof item accepted"
    );
}

#[test]
fn official_minimum_trace_height_guard_is_enforced() {
    let mut library = Library::new();
    let label = library.import(Box::new(StarkVerify::new_with_dynamic_layout(
        Stark::default(),
    )));
    let program = Program::new(
        &triton_asm!(push 1073741824 push 0 call {label} halt {&library.all_imports()}),
    );
    for height in 0..8 {
        let mut stream = ProofStream::new();
        stream.enqueue(ProofItem::Log2PaddedHeight(height));
        let proof: Proof = stream.into();
        let mut nd = NonDeterminism::default();
        encode_to_memory(&mut nd.ram, BFieldElement::new(0), &proof);
        encode_to_memory(
            &mut nd.ram,
            BFieldElement::new(1 << 30),
            &Claim::new(Digest::default()),
        );
        let error = run(program.clone(), nd).unwrap_err();
        assert!(
            error.contains("239"),
            "wrong rejection for log2height{height}: {error}"
        );
    }
}
