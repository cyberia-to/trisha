use triton_vm::prelude::*;

fn run(source: &str, helper: Option<&str>, input: &[u64], profile: &str) -> Vec<u64> {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("main.tri");
    std::fs::write(&path, source).unwrap();
    if let Some(helper) = helper {
        std::fs::write(directory.path().join("helper.tri"), helper).unwrap();
    }
    let assembly = trisha_rs::build_tasm(&path, "triton", profile).unwrap();
    VM::run(
        Program::from_code(&assembly).unwrap(),
        PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    )
    .unwrap()
    .iter()
    .map(|word| word.value())
    .collect()
}

#[test]
fn reordered_literal_uses_declaration_layout_for_locals_calls_and_returns() {
    let source = "program layout
struct Pair { a: Field, b: Field }
fn make() -> Pair { Pair { b: 19, a: 7 } }
fn value(p: Pair) -> Field { p.a * 100 + p.b }
fn main() {
 let p = Pair { b: 19, a: 7 }
 pub_write(p.a * 100 + p.b)
 pub_write(value(p))
 pub_write(value(make()))
}";
    for profile in ["debug", "release"] {
        assert_eq!(run(source, None, &[], profile), [719, 719, 719]);
    }
}

#[test]
fn nested_mixed_width_imported_structs_survive_returns_and_array_indexing() {
    let helper = "module helper
pub struct Pair { pub a: Field, pub b: Field }
pub struct Wide { pub pair: Pair, pub words: [Field; 3], pub tail: Field }
pub fn make(x: Field) -> Wide {
 Wide { tail: 31, words: [17, 19, 23], pair: Pair { b: 11, a: x } }
}
pub fn value(w: Wide) -> Field { w.pair.a * 100 + w.pair.b + w.words[2] + w.tail }
";
    let source = "program imported
use helper
fn main() {
 let mut values = [helper.make(7), helper.make(13)]
 let index = as_u32(pub_read())
 let chosen = values[index]
 pub_write(helper.value(chosen))
 pub_write(chosen.words[0])
}";
    for profile in ["debug", "release"] {
        assert_eq!(run(source, Some(helper), &[0], profile), [765, 17]);
        assert_eq!(run(source, Some(helper), &[1], profile), [1365, 17]);
    }
}

#[test]
fn field_effects_are_evaluated_once_in_recursive_declaration_order() {
    let source = "program effects
struct Pair { a: Field, b: Field }
struct Outer { first: Pair, last: Field }
fn take(tag: Field) -> Field { pub_write(tag)\n pub_read() }
fn main() {
 let p = Outer { last: take(3), first: Pair { b: take(2), a: take(1) } }
 pub_write(p.first.a)
 pub_write(p.first.b)
 pub_write(p.last)
 pub_write(pub_read())
}";
    for profile in ["debug", "release"] {
        assert_eq!(
            run(source, None, &[7, 19, 31, 43], profile),
            [1, 2, 3, 7, 19, 31, 43]
        );
    }
}

#[test]
fn unchecked_builder_errors_cannot_become_executable_stack_values() {
    use trident::tir::builder::TIRBuilder;
    for source in [
        "program bad\nfn main() { pub_write(missing) }",
        "program bad\nconst VALUE: Field = 77\nfn main() { pub_write(missing.VALUE) }",
        "program bad\nstruct Pair { a: Field, b: Field }\nfn main() { let p = Pair { a: 7 } }",
        "program bad\nstruct Pair { a: Field, b: Field }\nfn main() { let p = Pair { a: 7, a: 19 } }",
    ] {
        let file = trident::parse_source_silent(source, "bad.tri").unwrap();
        let ops = TIRBuilder::new(trisha_rs::target::package("triton").unwrap().terrain)
            .build_file(&file).unwrap();
        let error = trisha_rs::lower::lower_checked(&ops).unwrap_err();
        assert!(error.contains("ERROR:"), "{error}");
    }
}
