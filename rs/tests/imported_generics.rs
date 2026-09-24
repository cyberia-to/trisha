//! Independent execution oracles for generic bodies owned by foreign modules.
use triton_vm::prelude::*;

fn project(modules: &[(&str, &str)], source: &str) -> (tempfile::TempDir, std::path::PathBuf) {
    let directory = tempfile::tempdir().unwrap();
    for (name, body) in modules {
        std::fs::write(directory.path().join(format!("{name}.tri")), body).unwrap();
    }
    let entry = directory.path().join("entry.tri");
    std::fs::write(&entry, source).unwrap();
    (directory, entry)
}

fn execute(path: &std::path::Path, profile: &str, input: &[u64]) -> Vec<u64> {
    let text = trisha_rs::build_tasm(path, "triton", profile).unwrap();
    let program = Program::from_code(&text)
        .unwrap_or_else(|_| panic!("emitted TASM is invalid for profile {profile}"));
    VM::run(
        program,
        PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    )
    .unwrap()
    .iter()
    .map(|word| word.value())
    .collect()
}

const ALPHA: &str = "module alpha
const OFFSET:Field=7
const N:U32=9
const FIXED:U32=2
pub struct Pair { pub left:Field, pub right:Field }
fn helper(x:Field)->Field { x+OFFSET }
pub fn fold<N>(x:[Field;N])->Field {
 let mut sum:Field=0
 for i in 0..N {sum=sum*10+x[i]}
 helper(sum)
}
pub fn nested<N>(x:[Field;N])->Field { fold<N>(x)+fold<3>([7,1,9]) }
pub fn typed<N>(x:[Field;N],p:Pair)->Field {fold<N>(x)+p.left*100+p.right}
pub fn identity<N>(x:[Field;N])->[Field;N] {x}
pub fn padded<N>(x:[Field;N+FIXED])->Field {x[0]*100+x[2]}
";

#[test]
fn imported_instances_keep_lexical_helpers_types_and_distinct_module_names() {
    let beta = "module beta\nconst OFFSET:Field=19\nfn helper(x:Field)->Field{x+OFFSET}\npub fn fold<N>(x:[Field;N])->Field {let mut sum:Field=0\nfor i in 0..N {sum=sum*10+x[i]}\nhelper(sum)}";
    let source = "program entry
use alpha
use beta
const OFFSET:Field=1000
const FIXED:U32=17
fn helper(x:Field)->Field{x+2000}
fn shadow(OFFSET:Field)->Field{OFFSET+1}
fn main() {
 pub_write(alpha.fold<2>([3,5]))
 pub_write(beta.fold<2>([3,5]))
 pub_write(alpha.fold<3>([4,1,9]))
 pub_write(alpha.nested<2>([3,5]))
 pub_write(alpha.typed<2>([3,5],alpha.Pair {left:11,right:13}))
 pub_write(helper(1)+OFFSET)
 pub_write(alpha.padded<1>([3,5,7]))
 pub_write(shadow(5))
}";
    let (_directory, path) = project(&[("alpha", ALPHA), ("beta", beta)], source);
    for profile in ["debug", "release"] {
        assert_eq!(
            execute(&path, profile, &[]),
            [42, 54, 426, 768, 1155, 3001, 307, 6]
        );
        assert_eq!(
            trisha_rs::build_tasm(&path, "triton", profile).unwrap(),
            trisha_rs::build_tasm(&path, "triton", profile).unwrap(),
            "specialization output must be deterministic"
        );
    }
}

#[test]
fn imported_generic_aggregate_return_keeps_wide_frame_and_input_order() {
    let mut source = "program entry\nuse alpha\nfn main(words:[Field;20]) {let result=alpha.identity<20>(words)\n".to_string();
    for index in 0..20 {
        source.push_str(&format!("pub_write(result[{index}])\n"));
    }
    source.push_str("}");
    let (_directory, path) = project(&[("alpha", ALPHA)], &source);
    let words: Vec<u64> = (0..20).map(|index| 101 + index * 7).collect();
    for profile in ["debug", "release"] {
        assert_eq!(execute(&path, profile, &words), words);
    }
}

#[test]
fn imported_generic_body_is_checked_at_the_concrete_call() {
    let bad = "module bad\npub fn broken<N>(x:[Field;N])->Field {true}";
    let (_directory, path) = project(
        &[("bad", bad)],
        "program entry\nuse bad\nfn main(){pub_write(bad.broken<2>([7,19]))}",
    );
    for profile in ["debug", "release"] {
        let error = trisha_rs::build_tasm(&path, "triton", profile).unwrap_err();
        assert!(
            error.contains("Field") && error.contains("Bool"),
            "wrong rejection: {error}"
        );
    }
}

#[test]
fn imported_generic_cfg_selects_the_owned_body() {
    let module = "module selected\n#[cfg(debug)] pub fn pick<N>(x:[Field;N])->Field {x[0]+7}\n#[cfg(release)] pub fn pick<N>(x:[Field;N])->Field {x[0]+19}";
    let (_directory, path) = project(
        &[("selected", module)],
        "program entry\nuse selected\nfn main(){pub_write(selected.pick<2>([3,5]))}",
    );
    for (profile, expected) in [("debug", 10), ("release", 22)] {
        assert_eq!(execute(&path, profile, &[]), [expected]);
    }
}

#[test]
fn inferred_nested_sizes_follow_arguments_and_specializations_do_not_alias_user_names() {
    let module = "module sizes
pub fn value<M>(x:[Field;M])->Field {let mut result:Field=0\nfor i in 0..M {result=result*10+x[i]}\nresult}
pub fn value__N2(x:Field)->Field {x+1000}
pub fn trident_mono_0(x:Field)->Field{x+2000}
pub fn outer<N>(x:[Field;N])->Field {value([7,1,9])+value(x)}";
    let (_directory, path) = project(
        &[("sizes", module)],
        "program entry\nuse sizes\nfn main(){pub_write(sizes.outer<2>([3,5]))\npub_write(sizes.outer<3>([4,1,9]))\npub_write(sizes.value__N2(7))\npub_write(sizes.trident_mono_0(7))}",
    );
    for profile in ["debug", "release"] {
        assert_eq!(execute(&path, profile, &[]), [754, 1138, 1007, 2007]);
    }
}

#[test]
#[ignore = "serialized default-security proof gate; run with the release proof slot"]
fn genuine_proof_binds_imported_generic_to_program_input_and_output() {
    let (_directory, path) = project(
        &[("alpha", ALPHA)],
        "program entry\nuse alpha\nfn main(words:[Field;2]) {pub_write(alpha.fold<2>(words))}",
    );
    let program =
        Program::from_code(&trisha_rs::build_tasm(&path, "triton", "release").unwrap()).unwrap();
    let input = PublicInput::new(vec![bfe!(3), bfe!(5)]);
    let (trace, output) =
        VM::trace_execution(program.clone(), input.clone(), NonDeterminism::default()).unwrap();
    assert_eq!(output, vec![bfe!(42)]);
    let claim = Claim::about_program(&program)
        .with_input(input.individual_tokens)
        .with_output(output);
    let proof = Stark::default().prove(&claim, &trace).unwrap();
    trisha_rs::convert::verify_native_proof(&claim, &proof).unwrap();
    let mut changed = claim.clone();
    changed.input[0] = bfe!(4);
    assert!(trisha_rs::convert::verify_native_proof(&changed, &proof).is_err());
    let mut changed = claim.clone();
    changed.output[0] = bfe!(43);
    assert!(trisha_rs::convert::verify_native_proof(&changed, &proof).is_err());
    let mut changed = claim;
    changed.program_digest = Program::from_code("halt").unwrap().hash();
    assert!(trisha_rs::convert::verify_native_proof(&changed, &proof).is_err());
}
