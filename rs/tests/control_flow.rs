use triton_vm::prelude::*;

fn execute(body: &str, input: &[u64]) -> Vec<u64> {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("control.tri");
    std::fs::write(&path, format!("program control\n{body}")).unwrap();
    let asm = trisha_rs::build_tasm(&path, "triton", "debug").unwrap();
    VM::run(
        Program::from_code(&asm).unwrap(),
        PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    )
    .unwrap()
    .into_iter()
    .map(|v| v.value())
    .collect()
}

#[test]
fn literal_match_executes_only_the_first_selected_arm() {
    let source = "fn main() {
        let sentinel: Field = 97
        match pub_read() {
            0 => { pub_write(11) }
            1 => { pub_write(13) }
            _ => { pub_write(17) }
        }
        pub_write(sentinel)
    }";
    for (input, output) in [(0, 11), (1, 13), (2, 17)] {
        assert_eq!(execute(source, &[input]), [output, 97]);
    }
}

#[test]
fn struct_match_checks_literals_and_scopes_field_bindings() {
    let source = "struct Pair { x: Field, y: Field }
    fn main() {
        let p: Pair = Pair { x: pub_read(), y: pub_read() }
        let y: Field = 97
        match p {
            Pair { x: 0, y } => { pub_write(y) }
            Pair { x, y: 0 } => { pub_write(x) }
            _ => { pub_write(p.x + p.y) }
        }
        pub_write(y)
    }";
    for (input, output) in [([0, 3], 3), ([5, 0], 5), ([7, 11], 18)] {
        assert_eq!(execute(source, &input), [output, 97]);
    }
}

#[test]
fn match_return_keeps_tuple_order_and_discards_arm_locals() {
    let source = "fn choose(x: Field) -> (Field, Field) {
        match x {
            0 => { let a: Field = 11\n (a, 13) }
            _ => { let a: Field = 17\n let b: Field = 19\n (a, b) }
        }
    }
    fn main() {
        let sentinel: Field = 97
        let (a, b) = choose(pub_read())
        pub_write(a)
        pub_write(b)
        pub_write(sentinel)
    }";
    assert_eq!(execute(source, &[0]), [11, 13, 97]);
    assert_eq!(execute(source, &[1]), [17, 19, 97]);
}

#[test]
fn guarded_struct_pattern_requires_an_exhaustive_fallback() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("partial.tri");
    std::fs::write(&path, "program partial\nstruct Pair { x: Field, y: Field }\nfn main() {\n let p: Pair = Pair { x: pub_read(), y: 7 }\n match p { Pair { x: 0, y } => { pub_write(y) } }\n}").unwrap();
    let error = trisha_rs::build_tasm(&path, "triton", "debug").unwrap_err();
    assert!(error.contains("non-exhaustive match"), "{error}");
}

#[test]
fn branch_local_type_shadowing_does_not_change_outer_field_layout() {
    let source = "struct Inner { value: Field }\nstruct Outer { value: Inner, tail: Field }\nfn main() {\n let item: Outer = Outer { value: Inner { value: 11 }, tail: 13 }\n if pub_read() == 0 { let item: Inner = Inner { value: 17 }\n pub_write(item.value) }\n else { pub_write(item.value.value) }\n pub_write(item.value.value)\n pub_write(item.tail)\n}";
    assert_eq!(execute(source, &[0]), [17, 11, 13]);
    assert_eq!(execute(source, &[1]), [11, 11, 13]);
}
