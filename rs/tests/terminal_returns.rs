//! Terminal branch values must use the ordinary function return ABI.
use triton_vm::prelude::*;

fn run(source: &str, helper: Option<&str>, input: &[u64], profile: &str) -> Vec<u64> {
    let directory = tempfile::tempdir().unwrap();
    if let Some(helper) = helper {
        std::fs::write(directory.path().join("helper.tri"), helper).unwrap();
    }
    let path = directory.path().join("entry.tri");
    std::fs::write(&path, source).unwrap();
    let assembly = trisha_rs::build_tasm(&path, "triton", profile).unwrap();
    let mut state = VMState::new(
        Program::from_code(&assembly).unwrap(),
        PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    );
    for _ in 0..100_000 {
        if state.halting {
            return state
                .public_output
                .iter()
                .map(|word| word.value())
                .collect();
        }
        state.step().expect("terminal return execution failed");
    }
    panic!("terminal return exceeded the independent instruction limit");
}

#[test]
fn terminal_nested_if_tails_and_explicit_returns_preserve_caller_locals() {
    let source = "program entry
fn choose(n:Field)->Field {
 let keep:Field=43
 if n==0 {let keep:Field=11\n keep}
 else {let keep:Field=19\n if n==1 {return keep} else {keep+n}}
}
fn main(n:Field) {let keep:Field=97\n pub_write(choose(n))\n pub_write(keep)}";
    for profile in ["debug", "release"] {
        for (input, value) in [(0, 11), (1, 19), (7, 26)] {
            assert_eq!(run(source, None, &[input], profile), [value, 97]);
        }
    }
}

#[test]
fn imported_terminal_match_and_nested_if_return_full_aggregate() {
    let helper = "module helper
pub struct Pair {pub a:Field,pub b:Field}
pub struct Wide {pub pair:Pair,pub words:[Field;20]}
pub fn choose(n:Field,words:[Field;20])->Wide {
 let keep:Field=43
 match n {
 0=>{let keep:Field=11\n Wide{pair:Pair{a:keep,b:13},words:words}}
 1=>{let keep:Field=17\n return Wide{pair:Pair{a:keep,b:19},words:words}}
 _=>{if n==2 {let keep:Field=23\n Wide{pair:Pair{a:keep,b:29},words:words}}
 else {Wide{pair:Pair{a:keep,b:31},words:words}}}
 }
}";
    let mut source = "program entry\nuse helper\nfn main(n:Field,words:[Field;20]) {let keep:Field=97\nlet value=helper.choose(n,words)\npub_write(value.pair.a)\npub_write(value.pair.b)\n".to_string();
    for index in 0..20 {
        source.push_str(&format!("pub_write(value.words[{index}])\n"));
    }
    source.push_str("pub_write(keep)\n}");
    let words: Vec<u64> = (0..20).map(|i| 101 + i * 7).collect();
    for profile in ["debug", "release"] {
        for (n, pair) in [(0, [11, 13]), (1, [17, 19]), (2, [23, 29]), (9, [43, 31])] {
            let mut input = vec![n];
            input.extend(&words);
            let mut expected = pair.to_vec();
            expected.extend(&words);
            expected.push(97);
            assert_eq!(run(&source, Some(helper), &input, profile), expected);
        }
    }
}

#[test]
fn intermediate_branches_and_loop_tails_discard_values_but_keep_effects() {
    let source = "program entry
fn pair(tag:Field)->(Field,Field) {pub_write(tag)\n (7,11)}
fn scalar(tag:Field)->Field {pub_write(tag)\n 13}
fn choose(n:Field)->Field {
 if n==0 {pair(11)} else {scalar(13)}
 match n {0=>{pair(17)} _=>{scalar(19)}}
 for i in 0..2 {pair(23)}
 31
}
fn main(n:Field) {let keep:Field=97\n pub_write(choose(n))\n pub_write(keep)}";
    for profile in ["debug", "release"] {
        for (n, expected) in [(0, [11, 17, 23, 23, 31, 97]), (1, [13, 19, 23, 23, 31, 97])] {
            assert_eq!(run(source, None, &[n], profile), expected);
        }
    }
}
