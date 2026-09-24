//! Only continuing paths contribute function result words.
use triton_vm::prelude::*;

fn run(source: &str, input: u64, profile: &str) -> Result<Vec<u64>, Vec<u64>> {
    run_with_modules(source, &[], input, profile)
}

fn run_with_modules(
    source: &str,
    modules: &[(&str, &str)],
    input: u64,
    profile: &str,
) -> Result<Vec<u64>, Vec<u64>> {
    let directory = tempfile::tempdir().unwrap();
    for (name, content) in modules {
        let path = directory.path().join(name);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, content).unwrap();
    }
    let path = directory.path().join("entry.tri");
    std::fs::write(&path, source).unwrap();
    let assembly = trisha_rs::build_tasm(&path, "triton", profile).unwrap();
    let mut state = VMState::new(
        Program::from_code(&assembly).unwrap(),
        PublicInput::new(vec![BFieldElement::new(input)]),
        NonDeterminism::default(),
    );
    for _ in 0..100_000 {
        if state.halting {
            return Ok(state.public_output.iter().map(|n| n.value()).collect());
        }
        if let Err(error) = state.step() {
            assert!(
                matches!(
                    error,
                    triton_vm::error::InstructionError::AssertionFailed(_)
                ),
                "unexpected VM failure for {source}: {error:?}"
            );
            return Err(state.public_output.iter().map(|n| n.value()).collect());
        }
    }
    panic!("halting fixture exceeded independent instruction limit");
}

#[test]
fn failing_branches_do_not_discard_live_scalar_or_aggregate_results() {
    for profile in ["debug", "release"] {
        for body in [
            "if n==0 {assert(false)} else {7}",
            "if n==1 {7} else {assert(false)}",
            "if n==0 {return assert(false)} else {return 7}",
            "match n {0=>{assert(false)} _=>{7}}",
            "match n {1=>{7} _=>{assert(false)}}",
            "if n==0 {for i in 0..2 {assert(false)}} else {7}",
            "if n==0 {if true {assert(false)}} else {7}",
            "if n==0 {if 1 {assert(false)}} else {7}",
            "if n==0 {if 18446744069414584321 {} else {assert(false)}} else {7}",
        ] {
            let source=format!("program halt\nfn choose(n:Field)->Field {{ {body} }}\nfn main(n:Field) {{ let sentinel=97 pub_write(choose(n)) pub_write(sentinel) }}");
            assert_eq!(
                run(&source, 1, profile).unwrap(),
                [7, 97],
                "{profile}: {body}"
            );
            assert_eq!(run(&source, 0, profile), Err(vec![]), "{profile}: {body}");
        }
        for body in [
            "if n==0 {assert(false)} else {Pair{a:7,b:11}}",
            "if n==0 {return assert(false)} else {return Pair{a:7,b:11}}",
            "match n {0=>{assert(false)} _=>{Pair{a:7,b:11}}}",
        ] {
            let source=format!("program halt\nstruct Pair {{a:Field,b:Field}}\nfn choose(n:Field)->Pair {{ {body} }}\nfn main(n:Field) {{ let sentinel=97 let pair=choose(n) pub_write(pair.a) pub_write(pair.b) pub_write(sentinel) }}");
            assert_eq!(
                run(&source, 1, profile).unwrap(),
                [7, 11, 97],
                "{profile}: {body}"
            );
            assert_eq!(run(&source, 0, profile), Err(vec![]), "{profile}: {body}");
        }
    }
}

#[test]
fn ordinary_assert_function_executes_and_continues() {
    for profile in ["debug", "release"] {
        for declaration in [
            "fn assert(c:Bool)->Field {7}",
            "fn assert<N>(c:Bool)->Field {7}",
        ] {
            let call = if declaration.contains('<') {
                "assert<2>(false)"
            } else {
                "assert(false)"
            };
            let source=format!("program ordinary\n{declaration}\nfn main(n:Field) {{ let sentinel=97 {call} pub_write({call}) pub_write(sentinel) }}");
            assert_eq!(run(&source, 0, profile).unwrap(), [7, 97]);
        }
    }
}

#[test]
fn imported_assertions_and_active_aliases_keep_resolved_semantics() {
    let ordinary="program ordinary\nuse assert\nfn main(n:Field) { assert.is_true(false) pub_write(assert.is_true(false)) pub_write(97) }";
    let library = "module assert\npub fn is_true(c:Bool)->Field {7}";
    let cfg="module std.failure\n#[cfg(debug)] #[intrinsic(assert)] pub fn stop(c:Bool)\n#[cfg(release)] pub fn stop(c:Bool)->Field {7}";
    let source="program configured\nuse failure\nfn choose()->Field {failure.stop(false)}\nfn main(n:Field) {let sentinel=97 pub_write(choose()) pub_write(sentinel)}";
    for profile in ["debug", "release"] {
        assert_eq!(
            run_with_modules(ordinary, &[("assert.tri", library)], 0, profile).unwrap(),
            [7, 97]
        );
        let result = run_with_modules(source, &[("failure.tri", cfg)], 0, profile);
        assert_eq!(
            result,
            if profile == "debug" {
                Err(vec![])
            } else {
                Ok(vec![7, 97])
            }
        );
        for call in ["assert.is_true(false)", "vm.core.assert.is_true(false)"] {
            let source=format!("program imported\nuse vm.core.assert\nfn choose(n:Field)->Field {{ if n==0 {{ {call} }} else {{7}} }}\nfn main(n:Field) {{let sentinel=97 pub_write(choose(n)) pub_write(sentinel)}}");
            assert_eq!(run(&source, 1, profile).unwrap(), [7, 97]);
            assert_eq!(run(&source, 0, profile), Err(vec![]));
        }
    }
}

#[test]
fn pattern_and_local_bindings_shadow_loop_constants_in_divergence_analysis() {
    let source = "program shadow
const END:U32=1
struct Limit { end:U32 }
fn choose(n:U32)->Field {
 match Limit{end:n} {
  Limit{end:END}=>{for i in 0..END bounded 2 {assert(false)} 7}
 }
}
fn main(n:U32) {let sentinel=97 pub_write(choose(n)) pub_write(sentinel)}";
    // Struct-literal scrutinees use the explicit delimiter rule.
    let source = source.replace("match Limit{end:n}", "match (Limit{end:n})");
    for profile in ["debug", "release"] {
        assert_eq!(run(&source, 0, profile).unwrap(), [7, 97]);
        assert_eq!(run(&source, 1, profile), Err(vec![]));
    }
}

#[test]
fn imported_private_intrinsics_do_not_capture_caller_builtins() {
    let library =
        "module std.other\n#[intrinsic(pub_write)] fn assert(value:Field)\npub fn ok()->Field {7}";
    let source =
        "program private\nuse other\nfn main(n:Field) {pub_write(other.ok()) assert(false)}";
    for profile in ["debug", "release"] {
        assert_eq!(
            run_with_modules(source, &[("other.tri", library)], 0, profile),
            Err(vec![7])
        );
    }
}

#[test]
fn canonical_loop_bounds_preserve_the_continuing_result() {
    for profile in ["debug", "release"] {
        for (end, expected) in [
            ("18446744069414584321", Ok(vec![7, 97])),
            ("18446744069414584322", Err(vec![])),
        ] {
            let source = format!("program wrap\nfn choose()->Field {{for i in 0..{end} {{assert(false)}} 7}}\nfn main(n:Field) {{let sentinel=97 pub_write(choose()) pub_write(sentinel)}}");
            assert_eq!(run(&source, 0, profile), expected, "{profile}: {end}");
        }
    }
}

#[test]
fn callable_aliases_follow_each_modules_typechecked_scope() {
    let first = "module std.same\n#[intrinsic(assert)] pub fn stop(c:Bool)";
    let second = "module os.same\npub fn stop(c:Bool)->Field {7}";
    let entry = "program aliases\nuse first\nuse second\nfn main(n:Field) {pub_write(same.stop(false)) pub_write(97)}";
    let early = "module os.same\npub fn stop(c:Bool)->Field {7}\npub const FLAG:Field=0";
    let helper = "module helper\nuse early\npub fn value()->Field {if same.FLAG {assert(false)} else {same.stop(false)}}";
    let late = "module std.same\n#[intrinsic(assert)] pub fn stop(c:Bool)\npub const FLAG:Field=1";
    let scope = "program scopes\nuse helper\nuse late\nfn main(n:Field) {pub_write(helper.value()) same.stop(false)}";
    let parts = "program parts\nuse first\nuse second\nfn main(n:Field) {let p=same.a() pub_write(p.a) pub_write(p.b) pub_write(same.b())}";
    let aggregate = "module std.same\npub struct Pair {pub a:Field,pub b:Field}\npub fn a()->Pair {Pair{a:7,b:11}}";
    let scalar = "module os.same\npub fn b()->Field {13}";
    for profile in ["debug", "release"] {
        assert_eq!(
            run_with_modules(
                entry,
                &[("first.tri", first), ("second.tri", second)],
                0,
                profile
            ),
            Ok(vec![7, 97])
        );
        let generic = "module os.same\npub fn stop<N>(c:Bool)->Field {7}";
        let generic_entry = entry.replace("same.stop(false)", "same.stop<2>(false)");
        assert_eq!(
            run_with_modules(
                &generic_entry,
                &[("first.tri", first), ("second.tri", generic)],
                0,
                profile
            ),
            Ok(vec![7, 97])
        );
        let early_generic = "module std.same\npub fn stop<N>(c:Bool)->Field {19}";
        assert_eq!(
            run_with_modules(
                entry,
                &[("first.tri", early_generic), ("second.tri", second)],
                0,
                profile
            ),
            Ok(vec![7, 97])
        );
        assert_eq!(
            run_with_modules(
                scope,
                &[
                    ("early.tri", early),
                    ("helper.tri", helper),
                    ("late.tri", late)
                ],
                0,
                profile
            ),
            Err(vec![7])
        );
        assert_eq!(
            run_with_modules(
                parts,
                &[("first.tri", aggregate), ("second.tri", scalar)],
                0,
                profile
            ),
            Ok(vec![7, 11, 13])
        );
    }
}

#[test]
fn private_later_constant_cannot_change_a_proved_halting_condition() {
    let first = "module os.same\npub const FLAG:Field=1";
    let second = "module std.same\nconst FLAG:Field=0";
    let source="program constants\nuse first\nuse second\nfn choose(n:Field)->Field {if n==0 {if same.FLAG {assert(false)}} else {7}}\nfn main(n:Field) {let sentinel=97 pub_write(choose(n)) pub_write(sentinel)}";
    for profile in ["debug", "release"] {
        let modules = [("first.tri", first), ("second.tri", second)];
        assert_eq!(run_with_modules(source, &modules, 0, profile), Err(vec![]));
        assert_eq!(
            run_with_modules(source, &modules, 1, profile),
            Ok(vec![7, 97])
        );
    }
}

#[test]
fn local_struct_roots_shadow_module_constants_before_branch_joins() {
    let library = "module constants\npub const FLAG:Field=1\npub const END:U32=1";
    for body in [
        "if constants.FLAG {assert(false)}",
        "for i in 0..constants.END bounded 1 {assert(false)}",
    ] {
        let source=format!("program shadow\nuse constants\nstruct Dynamic {{FLAG:Field,END:U32}}\nfn choose(n:Field)->Field {{let constants=Dynamic{{FLAG:n,END:as_u32(n)}} if n==0 {{{body} 7}} else {{11}}}}\nfn main(n:Field) {{let sentinel=97 pub_write(choose(n)) pub_write(sentinel)}}");
        for profile in ["debug", "release"] {
            assert_eq!(
                run_with_modules(&source, &[("constants.tri", library)], 0, profile),
                Ok(vec![7, 97])
            );
            assert_eq!(
                run_with_modules(&source, &[("constants.tri", library)], 1, profile),
                Ok(vec![11, 97])
            );
        }
    }
}

#[test]
fn local_field_type_takes_precedence_over_module_constant_type() {
    let source="program local_type\nuse constants\nstruct Dynamic {FLAG:Bool}\nfn main(n:Field) {let constants=Dynamic{FLAG:n==0} assert(constants.FLAG) pub_write(7)}";
    for profile in ["debug", "release"] {
        let modules = [("constants.tri", "module constants\npub const FLAG:Field=1")];
        assert_eq!(run_with_modules(source, &modules, 0, profile), Ok(vec![7]));
        assert_eq!(run_with_modules(source, &modules, 1, profile), Err(vec![]));
    }
}
