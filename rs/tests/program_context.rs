//! Source code obtains its authenticated VM program digest without embedding its own hash.
use triton_vm::prelude::*;
#[test]
fn current_program_digest_matches_native_hash_and_survives_nested_calls() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("main.tri");
    std::fs::write(&path,"program identity\nuse vm.triton.context\nfn current() -> Digest { context.program_digest() }\nfn main() { let kept=42 let (a,b,c,d,e)=current() pub_write(a) pub_write(b) pub_write(c) pub_write(d) pub_write(e) let (f,g,h,i,j)=current() pub_write(f) pub_write(g) pub_write(h) pub_write(i) pub_write(j) pub_write(kept) }\n").unwrap();
    let code = trisha_rs::build_tasm(&path, "triton", "release").unwrap();
    let program = Program::from_code(&code).unwrap();
    let digest = program.hash().values();
    let output = VM::run(program, PublicInput::default(), NonDeterminism::default()).unwrap();
    let expected: Vec<_> = digest.into_iter().chain(digest).chain([bfe!(42)]).collect();
    assert_eq!(output, expected);
}
