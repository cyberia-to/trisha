use triton_vm::prelude::*;
#[test]
fn relu_and_argmax_use_all_canonical_bits() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("tensor.tri");
    std::fs::write(&path,"program tensor_test\nuse vm.io.mem\nuse std.nn.tensor\nfn main(){let a:Field=pub_read()\nlet b:Field=pub_read()\nmem.write(100,a)\nmem.write(101,b)\npub_write(tensor.argmax(100,2))\npub_write(tensor.relu(a))\npub_write(tensor.relu(b))}").unwrap();
    let hand = include_str!("../../baselines/triton/std/nn/tensor.tasm");
    let prefix="read_io 1 dup 0 push 100 write_mem 1 pop 1 read_io 1 dup 0 push 101 write_mem 1 pop 1 pop 2 push 100 push 2 call __argmax write_io 1 push 100 read_mem 1 pop 1 call __relu write_io 1 push 101 read_mem 1 pop 1 call __relu write_io 1 halt\n";
    let manual = Program::from_code(&format!("{prefix}{hand}")).unwrap();
    let half = (BFieldElement::P - 1) / 2;
    for profile in ["debug", "release"] {
        let compiled =
            Program::from_code(&trisha_rs::build_tasm(&path, "triton", profile).unwrap()).unwrap();
        for (a, b) in [
            (1, 2),
            (2, 1),
            (1u64 << 32, (1u64 << 32) + 1),
            ((1u64 << 32) - 1, 1u64 << 32),
            (half - 1, half),
            (half, half - 1),
            (BFieldElement::P - 1, 7),
        ] {
            let expected = vec![
                u64::from(b < half && (a >= half || b > a)),
                if a < half { a } else { 0 },
                if b < half { b } else { 0 },
            ];
            for program in [&compiled, &manual] {
                let out = VM::run(
                    program.clone(),
                    PublicInput::new(vec![BFieldElement::new(a), BFieldElement::new(b)]),
                    NonDeterminism::default(),
                )
                .unwrap();
                assert_eq!(
                    out.iter().map(|x| x.value()).collect::<Vec<_>>(),
                    expected,
                    "{profile} {a} {b}"
                );
            }
        }
    }
}
