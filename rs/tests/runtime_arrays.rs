use triton_vm::prelude::*;
fn program(source: &str, profile: &str) -> Program {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("arrays.tri");
    let imports = if source.contains("convert.") {
        "use vm.core.convert\n"
    } else {
        ""
    };
    std::fs::write(&path, format!("program arrays\n{imports}{source}")).unwrap();
    Program::from_code(&trisha_rs::build_tasm(&path, "triton", profile).unwrap()).unwrap()
}
fn run(program: &Program, input: &[u64]) -> Result<Vec<u64>, String> {
    VM::run(
        program.clone(),
        PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    )
    .map(|v| v.into_iter().map(|x| x.value()).collect())
    .map_err(|e| e.to_string())
}
#[test]
fn runtime_scalar_read_write_and_neighbors() {
    let source="fn main() { let keep: Field = 97\n let mut a: [Field; 3] = [11,13,17]\n let index: U32 = convert.as_u32(pub_read())\n pub_write(a[index])\n a[index] = 19\n pub_write(a[0])\n pub_write(a[1])\n pub_write(a[2])\n pub_write(keep) }";
    for profile in ["debug", "release"] {
        let p = program(source, profile);
        for (i, want) in [
            (0, [11, 19, 13, 17, 97]),
            (1, [13, 11, 19, 17, 97]),
            (2, [17, 11, 13, 19, 97]),
        ] {
            assert_eq!(run(&p, &[i]).unwrap(), want);
        }
    }
}
#[test]
fn array_of_structs_supports_whole_element_and_nested_field_store() {
    let source="struct Pair { a: Field, b: Field }\nstruct Other { b: Field, a: Field }\nfn make() -> [Pair; 2] { [Pair { a: 11, b: 13 },Pair { a: 17, b: 19 }] }\nfn main() { let keep: Field = 97\n let mut array: [Pair; 2] = make()\n let index: U32 = convert.as_u32(pub_read())\n let before: Pair = array[index]\n pub_write(before.a)\n pub_write(before.b)\n array[index] = Pair { a: 23, b: 29 }\n array[index].b = 31\n pub_write(array[0].a)\n pub_write(array[0].b)\n pub_write(array[1].a)\n pub_write(array[1].b)\n pub_write(keep) }";
    for profile in ["debug", "release"] {
        let p = program(source, profile);
        assert_eq!(run(&p, &[0]).unwrap(), [11, 13, 23, 31, 17, 19, 97]);
        assert_eq!(run(&p, &[1]).unwrap(), [17, 19, 11, 13, 23, 31, 97]);
    }
}
#[test]
fn nested_arrays_and_struct_array_fields_preserve_layout() {
    let source="struct Boxed { before: Field, items: [[Field; 2]; 2], after: Field }\nfn main() { let mut box: Boxed = Boxed { before: 7, items: [[11,13],[17,19]], after: 23 }\n let i: U32 = convert.as_u32(pub_read())\n let j: U32 = convert.as_u32(pub_read())\n pub_write(box.items[i][j])\n box.items[i][j] = 31\n pub_write(box.items[0][0])\n pub_write(box.items[0][1])\n pub_write(box.items[1][0])\n pub_write(box.items[1][1])\n pub_write(box.before)\n pub_write(box.after) }";
    for profile in ["debug", "release"] {
        let p = program(source, profile);
        assert_eq!(run(&p, &[1, 0]).unwrap(), [17, 11, 13, 31, 19, 7, 23]);
        assert_eq!(run(&p, &[0, 1]).unwrap(), [13, 11, 31, 17, 19, 7, 23]);
    }
}
#[test]
fn array_read_and_write_reject_out_of_bounds_indices() {
    for operation in ["pub_write(a[index])", "a[index] = 19"] {
        let source=format!("fn main() {{ let keep: Field = 97\n let mut a: [Field; 3] = [11,13,17]\n let index: U32 = convert.as_u32(pub_read())\n {operation}\n pub_write(keep) }}");
        for profile in ["debug", "release"] {
            let p = program(&source, profile);
            for i in [3, 4, u32::MAX as u64] {
                assert!(run(&p, &[i]).is_err(), "index {i} must fail");
            }
        }
    }
}
#[test]
fn runtime_indices_inside_nested_loops_preserve_locals() {
    let source="fn main() { let keep: Field = 97\n let mut a: [Field; 3] = [11,13,17]\n let input: Field = pub_read()\n for i in 0..3 { let local: Field = convert.as_field(i)\n for j in 0..2 { a[i] = a[i] + input + local }\n }\n pub_write(a[0])\n pub_write(a[1])\n pub_write(a[2])\n pub_write(keep) }";
    for profile in ["debug", "release"] {
        assert_eq!(
            run(&program(source, profile), &[3]).unwrap(),
            [17, 21, 27, 97]
        );
    }
}
#[test]
fn multiword_struct_field_assignment_preserves_other_fields() {
    let source="struct Pair { a: Field, b: Field }\nstruct Container { pre: Field, pair: Pair, post: Field }\nfn main() { let mut value: Container = Container { pre: 7, pair: Pair { a: 11, b: 13 }, post: 17 }\n value.pair = Pair { a: 19, b: 23 }\n pub_write(value.pre)\n pub_write(value.pair.a)\n pub_write(value.pair.b)\n pub_write(value.post) }";
    for profile in ["debug", "release"] {
        assert_eq!(
            run(&program(source, profile), &[]).unwrap(),
            [7, 19, 23, 17]
        );
    }
}
#[test]
fn indexed_assignment_evaluates_index_once_before_rhs_and_checks_first() {
    let source="fn publish(x: Field) -> Field { pub_write(x)\n x }\nfn main() { let mut a: [Field; 2] = [11,13]\n a[convert.as_u32(pub_read())] = publish(pub_read())\n pub_write(a[0])\n pub_write(a[1]) }";
    for profile in ["debug", "release"] {
        let p = program(source, profile);
        assert_eq!(run(&p, &[1, 23]).unwrap(), [23, 11, 23]);
        let mut state = VMState::new(
            p,
            PublicInput::new(vec![BFieldElement::new(2), BFieldElement::new(23)]),
            NonDeterminism::default(),
        );
        let mut rejected = false;
        for _ in 0..1000 {
            if state.step().is_err() {
                rejected = true;
                break;
            }
            if state.halting {
                break;
            }
        }
        assert!(rejected);
        assert!(
            state.public_output.is_empty(),
            "invalid index must not execute RHS effects"
        );
    }
}
#[test]
fn inferred_array_layout_uses_canonical_builtin_and_expression_types() {
    let source="fn main() { let mut a = [pub_read(),pub_read()]\n let mut nested = [[pub_read(),pub_read()],[pub_read(),pub_read()]]\n let mut expressions = [1 + 2, 3 + 4]\n let index: U32 = convert.as_u32(pub_read())\n a[index] = 23\n nested[index][index] = 29\n expressions[index] = 31\n pub_write(a[0])\n pub_write(a[1])\n pub_write(nested[1][1])\n pub_write(expressions[0])\n pub_write(expressions[1]) }";
    for profile in ["debug", "release"] {
        assert_eq!(
            run(&program(source, profile), &[7, 11, 13, 17, 19, 21, 1]).unwrap(),
            [7, 23, 29, 3, 31]
        );
    }
}
#[test]
fn inferred_digest_arrays_use_selected_abi_element_width() {
    let source="fn main() { let mut hashes = [pub_read5(),pub_read5()]\n let index: U32 = convert.as_u32(pub_read())\n hashes[index] = pub_read5()\n assert_digest(hashes[0], pub_read5())\n assert_digest(hashes[1], pub_read5())\n pub_write(42) }";
    let input: Vec<_> = (1..=10)
        .chain([1])
        .chain(11..=15)
        .chain(1..=5)
        .chain(11..=15)
        .collect();
    let expected = [42];
    for profile in ["debug", "release"] {
        assert_eq!(run(&program(source, profile), &input).unwrap(), expected);
    }
}
