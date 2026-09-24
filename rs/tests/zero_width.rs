//! Empty source values keep their logical identity without occupying VM words.
use triton_vm::prelude::*;

fn compile(source: &str, profile: &str) -> Program {
    let directory = tempfile::tempdir().unwrap();
    std::fs::write(
        directory.path().join("zero_width.tri"),
        include_str!("../../../trident/tests/fixtures/zero_width.tri"),
    )
    .unwrap();
    let path = directory.path().join("entry.tri");
    std::fs::write(&path, source).unwrap();
    let assembly = trisha_rs::build_tasm(&path, "triton", profile).unwrap();
    Program::from_code(&assembly).unwrap()
}

fn execute(program: Program, input: &[u64]) -> Result<Vec<u64>, Vec<u64>> {
    let mut state = VMState::new(
        program,
        PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    );
    for _ in 0..100_000 {
        if state.halting {
            return Ok(state.public_output.iter().map(|x| x.value()).collect());
        }
        if state.step().is_err() {
            return Err(state.public_output.iter().map(|x| x.value()).collect());
        }
    }
    panic!("zero-width execution exceeded independent instruction limit")
}

#[test]
fn zero_width_values_preserve_caller_words_and_declared_array_bounds() {
    let source = "program zero\nuse zero_width\nfn main(n:Field) { let sentinel=97\npub_write(zero_width.keep(n))\npub_write(sentinel) }";
    for profile in ["debug", "release"] {
        let program = compile(source, profile);
        for (input, expected) in [(0, 17), (1, 20)] {
            assert_eq!(execute(program.clone(), &[input]).unwrap(), [expected, 97]);
        }
        assert_eq!(execute(program, &[2]), Err(vec![]));
    }
}

#[test]
fn zero_width_operands_keep_effect_order_and_execute_once() {
    let source = "program effects
struct Empty {}
fn make(tag:Field)->Empty { pub_write(tag) Empty {} }
fn unit(tag:Field) { pub_write(tag) }
fn consume(a:Empty,n:Field,b:Empty)->Field { n }
fn early(n:Field)->Empty { for i in 0..2 { if n==0 { return make(31) } } make(37) }
fn main(n:Field) {
 let sentinel=97
 let empty=make(11)
 let u=unit(13)
 let pair=(make(17),make(19))
 let (left,right)=pair
 pub_write(consume(make(23),43,make(29)))
 let returned=early(n)
 assert(make(41)==make(47))
 assert(unit(53)==unit(59))
 let mut values=[empty,returned]
 values[as_u32(n)]=make(61)
 pub_write(sentinel)
}";
    for profile in ["debug", "release"] {
        let program = compile(source, profile);
        for n in [0, 1] {
            assert_eq!(
                execute(program.clone(), &[n]).unwrap(),
                [
                    11,
                    13,
                    17,
                    19,
                    23,
                    29,
                    43,
                    if n == 0 { 31 } else { 37 },
                    41,
                    47,
                    53,
                    59,
                    61,
                    97
                ]
            );
        }
        assert_eq!(
            execute(program, &[2]),
            Err(vec![11, 13, 17, 19, 23, 29, 43, 37, 41, 47, 53, 59])
        );
    }
}

#[test]
fn zero_width_array_access_uses_declared_count_without_expanding_empty_copies() {
    let source = "program large
struct Empty {}
fn main(values:[Empty;1048576],i:U32) {
 let sentinel=97
 let picked=values[i]
 let mut items=values
 items[i]=picked
 pub_write(sentinel)
}";
    for profile in ["debug", "release"] {
        let program = compile(source, profile);
        assert!(
            program.instructions.len() < 1000,
            "empty copies must not expand with array length"
        );
        for i in [0, 1048575] {
            assert_eq!(execute(program.clone(), &[i]).unwrap(), [97]);
        }
        assert_eq!(execute(program, &[1048576]), Err(vec![]));
    }
}

#[test]
fn assembly_word_effects_preserve_interleaved_empty_bindings() {
    let source = "program assembly
struct Empty {}
fn main() {
 let sentinel=97
 asm(+1) { push 7 }
 let empty=Empty {}
 asm(+1) { push 11 }
 let another=Empty {}
 asm(-2) { write_io 2 }
 let copy=empty
 assert(copy==another)
 pub_write(sentinel)
}";
    for profile in ["debug", "release"] {
        assert_eq!(execute(compile(source, profile), &[]).unwrap(), [11, 7, 97]);
    }
}

#[test]
fn array_extents_resolve_local_and_defining_module_constants() {
    let local = "program constants
const N:U32=2
fn main(i:U32) {
 let mut values:[Field;N+1]=[5,9,13]
 values[i]=17
 pub_write(values[i])
}";
    let imported = "program imported
use zero_width
const N:U32=3
fn main(i:U32) {
 let holder=zero_width.holder()
 let empty=holder.values[i]
 let mut values=holder.values
 values[i]=empty
 pub_write(97)
}";
    let generic = "program generic
use zero_width
const N:U32=7
fn main(i:U32) {
 let values=zero_width.pass<3>([zero_width.Empty {},zero_width.Empty {},zero_width.Empty {}])
 let selected=values[i]
 pub_write(101)
}";
    for profile in ["debug", "release"] {
        for (source, count, expected) in [(local, 3, 17), (imported, 2, 97), (generic, 3, 101)] {
            let program = compile(source, profile);
            for i in 0..count {
                assert_eq!(execute(program.clone(), &[i]).unwrap(), [expected]);
            }
            assert_eq!(execute(program, &[count]), Err(vec![]));
        }
    }
}

#[test]
fn mixed_unit_layouts_preserve_effects_and_scalar_components() {
    let source = "program inferred
fn unit(tag:Field) { pub_write(tag) }
fn main(n:U32) {
 let sentinel=97
 let (u,x)=(unit(11),7)
 let (v,y)=(u,13)
 let units=[unit(17),unit(19)]
 let selected=units[n]
 let rows=[[],[]]
 let row=rows[n]
 pub_write(x+y)
 pub_write(sentinel)
}";
    for profile in ["debug", "release"] {
        let program = compile(source, profile);
        for i in [0, 1] {
            assert_eq!(
                execute(program.clone(), &[i]).unwrap(),
                [11, 17, 19, 20, 97]
            );
        }
        assert_eq!(execute(program, &[2]), Err(vec![11, 17, 19]));
    }
}

#[test]
fn array_extent_beyond_u32_rejects_without_wrapping_or_expanding_entry() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("entry.tri");
    for ty in [
        "[Empty;4294967296]",
        "[[Empty;4294967296];1]",
        "[[Empty;4294967296];0]",
    ] {
        std::fs::write(
            &path,
            format!("program too_large\nstruct Empty {{}}\nfn main(values:{ty}) {{}}"),
        )
        .unwrap();
        for profile in ["debug", "release"] {
            let error = trisha_rs::build_tasm(&path, "triton", profile).unwrap_err();
            assert!(
                error.contains("array length must resolve to a U32 count"),
                "{ty}: {error}"
            );
        }
    }
}
