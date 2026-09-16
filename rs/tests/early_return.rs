use triton_vm::prelude::*;
fn execute(body: &str, input: &[u64], profile: &str) -> Vec<u64> {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("returns.tri");
    std::fs::write(&path, format!("program returns\n{body}")).unwrap();
    let asm = trisha_rs::build_tasm(&path, "triton", profile).unwrap();

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
fn conditional_return_exits_function_before_io_and_later_value() {
    let source = "fn choose(x: Field) -> Field { if x == 0 { return 1 }\n pub_write(99)\n x + x }\nfn main() { pub_write(choose(pub_read())) }";
    for profile in ["debug", "release"] {
        assert_eq!(execute(source, &[0], profile), [1]);
        assert_eq!(execute(source, &[7], profile), [99, 14]);
    }
}
#[test]
fn nested_returns_preserve_aggregate_results_and_shadowed_continuations() {
    let source = "struct Pair { a: Field, b: Field }\nfn choose(x: Field) -> Pair {\n let keep: Field = 17\n if x == 0 {\n let keep: Field = 23\n if keep == 23 { return Pair { a: keep, b: 29 } }\n pub_write(98)\n }\n let later: Field = keep + x\n if later == 18 { return Pair { a: later, b: 31 } }\n let keep: Field = later + 1\n Pair { a: keep, b: 37 }\n}\nfn main() {\n let sentinel: Field = 97\n let result: Pair = choose(pub_read())\n pub_write(result.a)\n pub_write(result.b)\n pub_write(sentinel)\n}";
    for profile in ["debug", "release"] {
        for (x, expected) in [(0, [23, 29, 97]), (1, [18, 31, 97]), (2, [20, 37, 97])] {
            assert_eq!(execute(source, &[x], profile), expected);
        }
    }
}
#[test]
fn return_from_nested_loops_skips_all_later_effects() {
    let source = "use vm.core.convert\nfn choose(x: Field) -> (Field, Field) {\n let mut sum: Field = 0\n for i in 0..3 {\n for j in 0..4 {\n if convert.as_field(i) + convert.as_field(j) == x { return (convert.as_field(i), convert.as_field(j)) }\n sum = sum + 1\n }\n }\n pub_write(sum)\n (7, 11)\n}\nfn main() { let (a,b) = choose(pub_read())\n pub_write(a)\n pub_write(b) }";
    for profile in ["debug", "release"] {
        assert_eq!(execute(source, &[2], profile), [0, 2]);
        assert_eq!(execute(source, &[9], profile), [12, 7, 11]);
    }
}
#[test]
fn void_return_and_unconditional_return_skip_io() {
    let source = "fn emit(x: Field) { if x == 0 { return }\n pub_write(13)\n return\n}\nfn main() { emit(pub_read())\n pub_write(17)\n return\n}";
    for profile in ["debug", "release"] {
        assert_eq!(execute(source, &[0], profile), [17]);
        assert_eq!(execute(source, &[1], profile), [13, 17]);
    }
}
#[test]
fn nested_calls_keep_each_invocations_return_slots() {
    let source = "fn inner(x: Field) -> Field { if x == 0 { return 7 }\n x + 1 }\nfn outer(x: Field) -> Field { if x == 0 { return inner(x) }\n let a: Field = inner(0)\n if x == 1 { return a + inner(x) }\n a + inner(x) + x }\nfn main() { pub_write(outer(pub_read())) }";
    for profile in ["debug", "release"] {
        for (x, y) in [(0, 7), (1, 9), (5, 18)] {
            assert_eq!(execute(source, &[x], profile), [y]);
        }
    }
}
#[test]
fn recursive_source_calls_remain_rejected() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("recursive.tri");
    std::fs::write(&path,"program recursive\nfn sum(x: Field) -> Field { if x == 0 { return 0 }\n sum(x + 18446744069414584320) + x }\nfn main() { pub_write(sum(pub_read())) }").unwrap();
    for profile in ["debug", "release"] {
        assert!(trisha_rs::build_tasm(&path, "triton", profile)
            .unwrap_err()
            .contains("recursive call cycle"));
    }
}
#[test]
fn match_early_arm_and_implicit_final_arm_preserve_result() {
    let source = "fn choose(x: Field) -> (Field, Field) {\n match x {\n 0 => { return (11,13) }\n _ => { let a: Field = 17\n (a,19) }\n }\n}\nfn main() { let (a,b) = choose(pub_read())\n pub_write(a)\n pub_write(b) }";
    for profile in ["debug", "release"] {
        assert_eq!(execute(source, &[0], profile), [11, 13]);
        assert_eq!(execute(source, &[1], profile), [17, 19]);
    }
}
#[test]
fn direct_return_cleans_locals_and_preserves_caller() {
    let source = "fn choose(x: Field) -> Field { let later: Field = x + 1\n return later }\nfn main() { let keep: Field = 97\n pub_write(choose(7))\n pub_write(keep) }";
    for profile in ["debug", "release"] {
        assert_eq!(execute(source, &[], profile), [8, 97]);
    }
}
#[test]
fn early_loop_return_does_not_execute_remaining_counter_iterations() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("bounded.tri");
    std::fs::write(&path,"program bounded_return\nfn choose() -> Field { for i in 0..1000000000 { return 7 }\n 9 }\nfn main() { pub_write(choose()) }").unwrap();
    for profile in ["debug", "release"] {
        let asm = trisha_rs::build_tasm(&path, "triton", profile).unwrap();
        let mut state = VMState::new(
            Program::from_code(&asm).unwrap(),
            PublicInput::default(),
            NonDeterminism::default(),
        );
        for _ in 0..1000 {
            if state.halting {
                break;
            }
            state.step().unwrap();
        }
        assert!(
            state.halting,
            "source return must terminate the counter loop"
        );
        assert_eq!(state.public_output, vec![BFieldElement::new(7)]);
    }
}
