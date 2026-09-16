//! Bounded witness loader and linkage to the official default-security verifier.
use super::witness::*;
use tasm_lib::hashing::algebraic_hasher::hash_varlen::HashVarlen;
use tasm_lib::library::Library;
use tasm_lib::verifier::stark_verify::StarkVerify;
use triton_vm::prelude::Stark;

pub const ENTRYPOINT: &str = "trisha_recursive_verify_v1";

fn length_guard(max: usize, control: u64) -> String {
    format!("\n    divine 1\n    dup 0\n    push 0\n    eq\n    push 0\n    eq\n    assert error_id 8002\n    push {}\n    dup 1\n    lt\n    assert error_id 8003\n    dup 0\n    push {control}\n    write_mem 1\n    pop 1\n",max+1)
}

/// Fixed native verifier plus a loader that authenticates all claim bytes.
pub fn assembly() -> String {
    let mut library = Library::new();
    let hash = library.import(Box::new(HashVarlen));
    let verify = library.import(Box::new(StarkVerify::new_with_dynamic_layout(
        Stark::default(),
    )));
    let mut code=format!("{ENTRYPOINT}:\n    divine 1\n    push {SCHEMA_VERSION}\n    eq\n    assert error_id 8001\n");
    code.push_str(&length_guard(MAX_CLAIM_WORDS, CONTROL_ADDRESS));
    code.push_str(&format!("    push {CLAIM_ADDRESS}\n    call trisha_recursive_load_words\n    pop 2\n    push {CLAIM_ADDRESS}\n    push {CONTROL_ADDRESS}\n    read_mem 1\n    pop 1\n    call {hash}\n"));
    // HashVarlen produces native d0-on-top; expected argument uses source d4-on-top.
    code.push_str("    swap 4\n    swap 1\n    swap 3\n    swap 1\n    assert_vector error_id 8004\n    pop 5\n");
    code.push_str(&length_guard(MAX_PROOF_WORDS, CONTROL_ADDRESS + 1));
    code.push_str(&format!("    push {PROOF_ADDRESS}\n    call trisha_recursive_load_words\n    pop 2\n    push {PROOF_ADDRESS}\n    read_mem 1\n    pop 1\n    push {}\n    read_mem 1\n    pop 1\n    push -1\n    add\n    eq\n    assert error_id 8005\n    push {CLAIM_ADDRESS}\n    push {PROOF_ADDRESS}\n    call {verify}\n    return\n",CONTROL_ADDRESS+1));
    code.push_str("trisha_recursive_load_words:\n    call trisha_recursive_load_five\n    call trisha_recursive_load_tail\n    return\ntrisha_recursive_load_five:\n    push 5\n    dup 2\n    lt\n    skiz\n    return\n    divine 5\n    swap 5\n    swap 1\n    swap 4\n    swap 1\n    swap 2\n    swap 3\n    swap 2\n    write_mem 5\n    swap 1\n    push -5\n    add\n    swap 1\n    recurse\ntrisha_recursive_load_tail:\n    dup 1\n    push 0\n    eq\n    skiz\n    return\n    divine 1\n    swap 1\n    write_mem 1\n    swap 1\n    push -1\n    add\n    swap 1\n    recurse\n");
    for instruction in library.all_imports() {
        code.push_str(&instruction.to_string());
        code.push('\n');
    }
    code
}
