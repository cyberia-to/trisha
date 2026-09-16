//! Source-level calling convention regressions exercised by the real VM.
use triton_vm::prelude::*;

fn execute(source: &str, input: &[u64]) -> Vec<u64> {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("frames.tri");
    std::fs::write(&path, source).unwrap();
    let assembly = trisha_rs::build_tasm(&path, "triton", "debug").unwrap();
    VM::run(
        Program::from_code(&assembly).unwrap(),
        PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    )
    .unwrap()
    .into_iter()
    .map(|v| v.value())
    .collect()
}

#[test]
fn conditional_tuple_return_discards_branch_locals_and_callee_frame() {
    let source = "program frames
fn choose(x: Field) -> (Field, Field) {
    let outer: Field = 7
    if x == 0 {
        let a: Field = 11
        (a, outer)
    } else {
        let a: Field = 21
        let b: Field = 22
        let c: Field = 23
        (a + b, c)
    }
}
fn main() {
    let sentinel: Field = 99
    let (a, b) = choose(pub_read())
    pub_write(a)
    pub_write(b)
    pub_write(sentinel)
}";
    assert_eq!(execute(source, &[0]), [11, 7, 99]);
    assert_eq!(execute(source, &[1]), [43, 23, 99]);
}

#[test]
fn nested_conditional_aggregate_return_preserves_assignment_neighbors() {
    let source = "program frames
struct Pair { x: Field, y: Field }
fn choose(x: Field) -> Pair {
    if x == 0 {
        let z: Field = 17
        Pair { x: z, y: 19 }
    } else {
        if x == 1 { Pair { x: 23, y: 29 } }
        else { let z: Field = 31
            let w: Field = 37
            Pair { x: z, y: w } }
    }
}
fn main() {
    let mut pair: Pair = Pair { x: 0, y: 0 }
    let sentinel: Field = 101
    pair = choose(pub_read())
    pub_write(pair.x)
    pub_write(pair.y)
    pub_write(sentinel)
}";
    for (input, expected) in [(0, [17, 19, 101]), (1, [23, 29, 101]), (2, [31, 37, 101])] {
        assert_eq!(execute(source, &[input]), expected);
    }
}

#[test]
fn mixed_width_tuple_wildcards_discard_exactly_the_ignored_fields() {
    let source = "program frames
struct Triple { x: Field, y: Field, z: Field }
fn data() -> (Triple, Field, Triple) {
    (Triple { x: 2, y: 3, z: 5 }, 7, Triple { x: 11, y: 13, z: 17 })
}
fn main() {
    let sentinel: Field = 97
    let (a, _, _) = data()
    pub_write(a.x)
    pub_write(a.y)
    pub_write(a.z)
    pub_write(sentinel)
}";
    assert_eq!(execute(source, &[]), [2, 3, 5, 97]);
}

#[test]
fn tuple_reassignment_replaces_each_target_at_its_actual_width() {
    let source = "program frames
struct Pair { x: Field, y: Field }
fn data() -> (Pair, Field) { (Pair { x: 3, y: 5 }, 7) }
fn main() {
    let mut pair: Pair = Pair { x: 0, y: 0 }
    let mut value: Field = 1
    let sentinel: Field = 97
    (pair, value) = data()
    pub_write(pair.x)
    pub_write(pair.y)
    pub_write(value)
    pub_write(sentinel)
}";
    assert_eq!(execute(source, &[]), [3, 5, 7, 97]);
}
