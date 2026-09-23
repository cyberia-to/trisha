//! Real proofs check fixed-program Neptune-style claim binding independently of host validation.
use trident::runtime::ProgramInput;
use trisha_rs::recursive;
use triton_vm::prelude::*;

fn run(program_hash: Digest, digests: &[Digest], witness: &ProgramInput) -> Result<(), String> {
    let mut code = String::from("push 123\n");
    for digest in digests {
        for value in digest.values() {
            code.push_str(&format!("push {}\n", value.value()));
        }
    }
    code.push_str("call fixed_protocol\npush 123\neq\nassert\nhalt\n");
    code.push_str(&recursive::fixed_claim_assembly(
        "fixed_protocol",
        program_hash,
        digests.len(),
    ));
    code.push_str(&recursive::assembly());
    let program = Program::from_code(&code).unwrap();
    let mut input = witness.clone();
    input.public.clear();
    let (public, secret) = trisha_rs::convert::to_triton_inputs(&input).unwrap();
    let mut state = VMState::new(program, public, secret);
    for _ in 0..5_000_000 {
        if state.halting {
            return Ok(());
        }
        state.step().map_err(|error| error.to_string())?;
    }
    Err("fixed claim verifier exceeded cycle budget".into())
}

#[test]
fn fixed_program_and_reversed_digest_inputs_are_bound_inside_vm() {
    for count in [1, 3] {
        let source = "read_io 5 pop 5\n".repeat(count) + "halt";
        let program = Program::from_code(&source).unwrap();
        let digests: Vec<_> = (0..count)
            .map(|i| {
                Digest::new(std::array::from_fn(|j| {
                    BFieldElement::new((i * 10 + j + 1) as u64)
                }))
            })
            .collect();
        let expected = recursive::expected_claim(program.hash(), &digests);
        let (trace, output) = VM::trace_execution(
            program.clone(),
            expected.input.clone().into(),
            NonDeterminism::default(),
        )
        .unwrap();
        assert!(output.is_empty());
        let proof = Stark::default().prove(&expected, &trace).unwrap();
        let witness = recursive::encode(&expected, &proof).unwrap();
        run(program.hash(), &digests, &witness)
            .expect("actual proof accepted by fixed claim binder");
        assert!(
            run(Digest::default(), &digests, &witness).is_err(),
            "witness selected a different program"
        );
        for index in 0..count {
            let mut changed = digests.clone();
            let mut values = changed[index].values();
            values[2] += BFieldElement::new(1);
            changed[index] = Digest::new(values);
            assert!(
                run(program.hash(), &changed, &witness).is_err(),
                "changed public digest accepted"
            );
        }
        let mut wrong_version = expected.clone();
        wrong_version.version += 1;
        let encoded = wrong_version.encode();
        let mut bypass = witness.clone();
        let old_len = bypass.secret[1] as usize;
        bypass.secret.splice(
            2..2 + old_len,
            encoded.into_iter().map(|value| value.value()),
        );
        assert!(run(program.hash(), &digests, &bypass).is_err());
    }
}
