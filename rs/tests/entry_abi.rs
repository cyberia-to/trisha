use triton_vm::prelude::*;

fn compile(source: &str, profile: &str) -> Program {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("entry.tri");
    std::fs::write(&path, format!("program entry\n{source}")).unwrap();
    Program::from_code(&trisha_rs::build_tasm(&path, "triton", profile).unwrap()).unwrap()
}
fn execute(program: Program, input: &[u64]) -> Result<Vec<u64>, String> {
    VM::run(
        program,
        PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    )
    .map(|output| output.iter().map(|word| word.value()).collect())
    .map_err(|_| "execution rejected".into())
}

#[test]
fn parameters_use_declared_order_and_stream_remainder() {
    let source = "fn difference(a: Field, b: Field) -> Field { a * 100 + b }\nfn main(a: Field, b: Field) { assert(a == 7)\n assert(b == 19)\n pub_write(difference(a,b))\n pub_write(pub_read()) }";
    for profile in ["debug", "release"] {
        let program = compile(source, profile);
        assert_eq!(execute(program.clone(), &[7, 19, 31]).unwrap(), [719, 31]);
        assert!(execute(program, &[7, 19]).is_err());
        assert!(execute(
            compile("fn main(a: Field,b: Field) { pub_write(a+b) }", profile),
            &[7]
        )
        .is_err());
    }
}

#[test]
fn aggregates_wider_than_register_window_preserve_every_leaf() {
    let mut source = String::from("struct Pair { a: Field, n: U32, ok: Bool }\nfn main(pair: Pair, tuple: (Field, U32), array: [Field; 20], digest: Digest, extension: XField) {\n pub_write(pair.a)\n pub_write(as_field(pair.n))\n if pair.ok { pub_write(1) } else { pub_write(0) }\n let (t0,t1) = tuple\n pub_write(t0)\n pub_write(as_field(t1))\n");
    for i in 0..20 {
        source.push_str(&format!("pub_write(array[{i}])\n"));
    }
    source.push_str("let (d0,d1,d2,d3,d4) = digest\n");
    for i in 0..5 {
        source.push_str(&format!("pub_write(d{i})\n"));
    }
    source
        .push_str("let (x0,x1,x2) = extension\n pub_write(x0)\n pub_write(x1)\n pub_write(x2)\n}");
    let mut input = vec![11, 4294967295, 1, 17, 23];
    input.extend((0..20).map(|i| 100 + i * 7));
    input.extend([307, 311, 313, 317, 331, 337, 347, 349]);
    for profile in ["debug", "release"] {
        let program = compile(&source, profile);
        assert_eq!(execute(program.clone(), &input).unwrap(), input);
        for (index, value) in [(1, 4294967296), (2, 2), (4, 4294967296)] {
            let mut invalid = input.clone();
            invalid[index] = value;
            assert!(execute(program.clone(), &invalid).is_err());
        }
        assert!(execute(program, &input[..input.len() - 1]).is_err());
    }
}

#[test]
fn narrow_types_validate_even_when_unused_and_returns_are_not_public() {
    for profile in ["debug", "release"] {
        let program = compile("fn main(flag: Bool, n: U32) -> Field { 11 }", profile);
        for flag in [0, 1] {
            assert_eq!(
                execute(program.clone(), &[flag, 4294967295]).unwrap(),
                Vec::<u64>::new()
            );
        }
        for input in [[2, 0], [u64::from(u32::MAX), 0], [1, 4294967296]] {
            assert!(execute(program.clone(), &input).is_err());
        }
        assert_eq!(
            execute(compile("fn main() -> Field { 11 }", profile), &[]).unwrap(),
            Vec::<u64>::new()
        );
        assert_eq!(
            execute(
                compile("fn main() { pub_write(pub_read()) }", profile),
                &[41]
            )
            .unwrap(),
            [41]
        );
    }
}

#[test]
fn imported_library_main_keeps_normal_call_abi() {
    let directory = tempfile::tempdir().unwrap();
    std::fs::write(
        directory.path().join("helper.tri"),
        "module helper\npub fn main(a: Field,b: Field)->Field { a*100+b }\n",
    )
    .unwrap();
    let path = directory.path().join("entry.tri");
    std::fs::write(
        &path,
        "program entry\nuse helper\nfn main(a: Field,b: Field) { pub_write(helper.main(a,b)) }\n",
    )
    .unwrap();
    for profile in ["debug", "release"] {
        let program =
            Program::from_code(&trisha_rs::build_tasm(&path, "triton", profile).unwrap()).unwrap();
        assert_eq!(execute(program, &[7, 19]).unwrap(), [719]);
    }
}

#[test]
fn imported_nested_aggregate_entry_layout_and_leaf_validation() {
    let directory = tempfile::tempdir().unwrap();
    std::fs::write(directory.path().join("helper.tri"), "module helper\npub struct Inner { pub value: U32, pub flag: Bool }\npub struct Outer { pub head: Field, pub inner: Inner, pub tail: Field }\npub fn echo(x: Field) -> Field { x }\n").unwrap();
    let path = directory.path().join("entry.tri");
    std::fs::write(&path,"program entry\nuse helper\nfn main(value: helper.Outer) { pub_write(helper.echo(value.head))\n pub_write(as_field(value.inner.value))\n assert(value.inner.flag)\n pub_write(value.tail) }\n").unwrap();
    for profile in ["debug", "release"] {
        let program =
            Program::from_code(&trisha_rs::build_tasm(&path, "triton", profile).unwrap()).unwrap();
        assert_eq!(
            execute(program.clone(), &[7, 19, 1, 31]).unwrap(),
            [7, 19, 31]
        );
        assert!(execute(program.clone(), &[7, 4294967296, 1, 31]).is_err());
        assert!(execute(program, &[7, 19, 2, 31]).is_err());
    }
}

#[test]
#[ignore = "serialized real proof gate; run when the release proof slot is free"]
fn actual_proof_binds_typed_entry_input_and_explicit_output() {
    let program = compile(
        "fn main(a: Field,b: U32,flag: Bool) { assert(flag)\n pub_write(a*100+as_field(b)) }",
        "release",
    );
    let input = PublicInput::new(vec![bfe!(7), bfe!(19), bfe!(1)]);
    let (trace, output) =
        VM::trace_execution(program.clone(), input.clone(), NonDeterminism::default()).unwrap();
    assert_eq!(output, vec![bfe!(719)]);
    let claim = Claim::about_program(&program)
        .with_input(input.individual_tokens)
        .with_output(output);
    let proof = Stark::default().prove(&claim, &trace).unwrap();
    trisha_rs::convert::verify_native_proof(&claim, &proof).unwrap();
    let mut changed = claim.clone();
    changed.input[0] = bfe!(8);
    assert!(trisha_rs::convert::verify_native_proof(&changed, &proof).is_err());
    let mut changed = claim.clone();
    changed.output[0] = bfe!(718);
    assert!(trisha_rs::convert::verify_native_proof(&changed, &proof).is_err());
    let mut changed = claim;
    changed.program_digest = Program::from_code("halt").unwrap().hash();
    assert!(trisha_rs::convert::verify_native_proof(&changed, &proof).is_err());
}

#[test]
fn checked_lowering_rejects_nested_or_misplaced_program_entry_metadata() {
    use trident::tir::{EntryLeaf, TIROp};
    use trisha_rs::lower::lower_checked;
    let entry = || {
        vec![
            TIROp::EntryParameters(vec![EntryLeaf::Field]),
            TIROp::Entry("main".into()),
        ]
    };
    let mut valid = entry();
    valid.extend([
        TIROp::FnStart("main".into()),
        TIROp::Pop(1),
        TIROp::Return,
        TIROp::FnEnd,
    ]);
    assert!(lower_checked(&valid).is_ok());
    for payload in [entry(), vec![TIROp::Entry("main".into())]] {
        let containers = vec![
            TIROp::IfOnly {
                then_body: payload.clone(),
            },
            TIROp::IfElse {
                then_body: payload.clone(),
                else_body: vec![],
            },
            TIROp::IfElse {
                then_body: vec![],
                else_body: payload.clone(),
            },
            TIROp::Loop {
                label: "loop".into(),
                body: payload.clone(),
            },
            TIROp::ProofBlock {
                program_hash: "fixture".into(),
                body: payload,
            },
        ];
        for container in containers {
            assert!(lower_checked(std::slice::from_ref(&container)).is_err());
            assert!(
                lower_checked(&[TIROp::FnStart("main".into()), container, TIROp::FnEnd]).is_err()
            );
        }
    }
    assert!(lower_checked(&[TIROp::Entry("main".into()), TIROp::Entry("main".into())]).is_err());
    assert!(lower_checked(&[
        TIROp::EntryParameters(vec![EntryLeaf::Unresolved("missing".into())]),
        TIROp::Entry("main".into())
    ])
    .is_err());
    assert!(lower_checked(&[TIROp::EntryParameters(vec![EntryLeaf::Field]), TIROp::Halt]).is_err());
}
