//! Real-VM checks that compiler stack operations preserve arbitrary source RAM.
use std::collections::BTreeMap;
use trident::tir::TIROp;
use trisha_rs::lower::{StackLowering, TritonLowering};
use triton_vm::prelude::*;

fn execute(program: Program, input: &[u64], memory: &BTreeMap<u64, u64>) -> VMState {
    let mut vm = VMState::new(
        program,
        PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    );
    vm.ram.extend(
        memory
            .iter()
            .map(|(&address, &value)| (BFieldElement::new(address), BFieldElement::new(value))),
    );
    while !vm.halting && vm.cycle_count < 1_000_000 {
        vm.step().unwrap();
    }
    assert!(vm.halting, "stack operation exceeded execution budget");
    vm
}

fn nonzero_ram(vm: &VMState) -> BTreeMap<u64, u64> {
    vm.ram
        .iter()
        .filter(|(_, value)| value.value() != 0)
        .map(|(address, value)| (address.value(), value.value()))
        .collect()
}

fn output(vm: &VMState) -> Vec<u64> {
    vm.public_output.iter().map(|value| value.value()).collect()
}

#[test]
fn deep_access_preserves_all_ram_including_fragmented_zero_runs() {
    for pattern in 0..4 {
        let mut memory = BTreeMap::new();
        for address in 0..256u64 {
            if pattern == 0 || (pattern == 1 && address % 17 == 0) {
                memory.insert(address, address + 101);
            }
        }
        for base in [1 << 29, 1 << 30, 1 << 31, BFieldElement::P - 32] {
            for offset in 0..32 {
                memory.insert(base + offset, 997 + offset);
            }
        }
        if pattern == 3 {
            // A zero field sum does not imply a zero block. This must take
            // the fallback even though these two occupied cells cancel.
            for offset in 0..32 {
                memory.remove(&((1 << 31) + offset));
            }
            memory.insert(1 << 31, BFieldElement::P - 1);
            memory.insert((1 << 31) + 1, 1);
        }
        for depth in [0, 1, 14, 15, 16, 17, 18, 19, 20, 21, 31, 32, 63, 64, 127] {
            for duplicate in [false, true] {
                // Include zero payloads: occupied scratch cannot be identified
                // by whether the stack value stored there was nonzero.
                let values: Vec<u64> = (0..depth + 4).map(|i| (i % 7) as u64).collect();
                let mut expected = values.clone();
                let top = expected.len() - 1;
                if duplicate {
                    expected.push(expected[top - depth as usize]);
                } else {
                    expected.swap(top, top - depth as usize);
                }
                let mut ops: Vec<_> = values.into_iter().map(TIROp::Push).collect();
                ops.push(if duplicate {
                    TIROp::Dup(depth)
                } else {
                    TIROp::Swap(depth)
                });
                ops.push(TIROp::WriteIo(expected.len() as u32));
                let code = TritonLowering::new().lower(&ops).join("\n") + "\nhalt";
                let vm = execute(Program::from_code(&code).unwrap(), &[], &memory);
                expected.reverse();
                assert_eq!(
                    output(&vm),
                    expected,
                    "pattern={pattern}, depth={depth}, dup={duplicate}"
                );
                assert_eq!(
                    nonzero_ram(&vm),
                    memory,
                    "pattern={pattern}, depth={depth}, dup={duplicate}"
                );
            }
        }
    }
}

fn source_program(source: &str, profile: &str) -> Program {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("stack_ram.tri");
    std::fs::write(&path, source).unwrap();
    Program::from_code(&trisha_rs::build_tasm(&path, "triton", profile).unwrap()).unwrap()
}

#[test]
fn stack_sequences_preserve_ram_at_every_source_memory_observation() {
    for seed in 1..=32u64 {
        for occupied in [false, true] {
            let mut random = seed;
            let mut expected: Vec<u64> = (0..80).map(|i| i % 11).collect();
            let mut ops: Vec<_> = expected.iter().copied().map(TIROp::Push).collect();
            let mut public = Vec::new();
            for _ in 0..2 {
                for _ in 0..64 {
                    random = random.wrapping_mul(6364136223846793005).wrapping_add(1);
                    let top = expected.len() - 1;
                    let depth = (random >> 8) as usize % expected.len();
                    match random % 3 {
                        0 => {
                            ops.push(TIROp::Dup(depth as u32));
                            expected.push(expected[top - depth]);
                        }
                        1 if expected.len() > 40 => {
                            ops.push(TIROp::Pop(1));
                            expected.pop();
                        }
                        _ => {
                            ops.push(TIROp::Swap(depth as u32));
                            expected.swap(top, top - depth);
                        }
                    }
                }
                // A source-visible read ends the temporary frame, even when
                // another profitable stack sequence follows it immediately.
                ops.extend([
                    TIROp::Push(1 << 31),
                    TIROp::RamRead { width: 1 },
                    TIROp::WriteIo(1),
                ]);
                public.push(if occupied { 999 } else { 0 });
            }
            ops.push(TIROp::WriteIo(expected.len() as u32));
            public.extend(expected.into_iter().rev());
            let memory = if occupied {
                (0..47)
                    .map(|i| (i, 101 + i))
                    .chain([(1 << 31, 999)])
                    .collect()
            } else {
                BTreeMap::new()
            };
            let code = TritonLowering::new().lower(&ops).join("\n") + "\nhalt";
            let vm = execute(Program::from_code(&code).unwrap(), &[], &memory);
            assert_eq!(output(&vm), public, "seed={seed}, occupied={occupied}");
            assert_eq!(nonzero_ram(&vm), memory, "seed={seed}, occupied={occupied}");
        }
    }
}

#[test]
fn source_deep_access_preserves_runtime_address_and_block_neighbors() {
    let source = "program stack_ram
use vm.io.mem
fn main() {
    let words: [Field; 20] = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
    let address = pub_read()
    mem.write(address, 999)
    mem.write(address + 1, 1001)
    mem.write(address + 2, 1003)
    mem.write(address + 3, 1007)
    mem.write(address + 4, 1009)
    let block = mem.read_block(address)
    pub_write(words[0])
    mem.write_block(address + 5, block)
    pub_write(mem.read(address))
    pub_write(mem.read(address + 1))
    pub_write(mem.read(address + 2))
    pub_write(mem.read(address + 3))
    pub_write(mem.read(address + 4))
    pub_write(mem.read(address + 5))
    pub_write(mem.read(address + 6))
    pub_write(mem.read(address + 7))
    pub_write(mem.read(address + 8))
    pub_write(mem.read(address + 9))
}";
    for profile in ["debug", "release"] {
        let program = source_program(source, profile);
        for address in [
            0,
            14,
            (1 << 30) - 2,
            (1 << 31) - 2,
            1 << 31,
            BFieldElement::P - 10,
        ] {
            let vm = execute(program.clone(), &[address], &BTreeMap::new());
            assert_eq!(
                output(&vm),
                [1, 999, 1001, 1003, 1007, 1009, 999, 1001, 1003, 1007, 1009],
                "{profile}, {address}"
            );
            let expected: BTreeMap<_, _> = [999, 1001, 1003, 1007, 1009]
                .into_iter()
                .cycle()
                .take(10)
                .enumerate()
                .map(|(offset, value)| (address + offset as u64, value))
                .collect();
            assert_eq!(nonzero_ram(&vm), expected, "{profile}, {address}");
        }
    }
}

#[test]
fn multiword_return_cleanup_preserves_ram_across_repeated_calls() {
    let source = "program stack_ram
use vm.io.mem
fn pair(x: Field) -> (Field, Field) { (x, x + 1) }
fn main() {
    let address = pub_read()
    mem.write(address, 999)
    let (x, y) = pair(7)
    let (a, b) = pair(y)
    pub_write(x)
    pub_write(y)
    pub_write(a)
    pub_write(b)
    pub_write(mem.read(address))
}";
    for profile in ["debug", "release"] {
        let program = source_program(source, profile);
        for address in [0, 1 << 29, 1 << 30, 1 << 31, BFieldElement::P - 1] {
            let vm = execute(program.clone(), &[address], &BTreeMap::new());
            assert_eq!(output(&vm), [7, 8, 8, 9, 999], "{profile}, {address}");
            assert_eq!(nonzero_ram(&vm), BTreeMap::from([(address, 999)]));
        }
    }
}

#[test]
fn inline_assembly_observes_source_ram_and_preserves_named_locals() {
    let source = "program stack_ram
use vm.io.mem
fn main() {
    let values: [Field; 20] = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
    let sentinel = pub_read()
    mem.write(1073741824, 999)
    asm { push 1073741824 read_mem 1 pop 1 write_io 1 }
    asm(+1) { push 41 }
    asm { push 1 add }
    asm(-1) { write_io 1 }
    asm { push 1009 push 1073741824 write_mem 1 pop 1 }
    pub_write(sentinel)
    pub_write(values[0])
    pub_write(values[19])
    pub_write(mem.read(1073741824))
}";
    for profile in ["debug", "release"] {
        let vm = execute(source_program(source, profile), &[97], &BTreeMap::new());
        assert_eq!(output(&vm), [999, 42, 97, 1, 20, 1009], "{profile}");
        assert_eq!(nonzero_ram(&vm), BTreeMap::from([(1 << 30, 1009)]));
    }
}

#[test]
fn inline_assembly_cannot_declare_consumption_of_a_named_binding() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("bad_asm.tri");
    std::fs::write(
        &path,
        "program bad_asm\nfn main() { let x = pub_read()\nasm(-1) { pop 1 }\npub_write(x) }",
    )
    .unwrap();
    for profile in ["debug", "release"] {
        let error = trisha_rs::build_tasm(&path, "triton", profile).unwrap_err();
        assert!(error.contains("inline assembly stack effect"), "{error}");
    }
}
