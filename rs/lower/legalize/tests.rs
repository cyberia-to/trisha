use super::*;
use triton_vm::prelude::*;

fn machine(code: &str) -> VMState {
    VMState::new(
        Program::from_code(code).unwrap(),
        PublicInput::default(),
        NonDeterminism::default(),
    )
}

#[test]
fn scratch_search_accepts_a_zero_run_ending_at_the_last_field_address() {
    let mut code = vec![format!(
        "push 4 push {} push 0 call scan write_io 3 halt",
        BFieldElement::P - 4
    )];
    scan("scan", &mut code);
    let mut vm = machine(&code.join("\n"));
    vm.run().unwrap();
    assert_eq!(
        vm.public_output,
        [bfe!(4), bfe!(BFieldElement::P - 1), bfe!(4)]
    );
    assert!(vm.ram.values().all(|value| value.value() == 0));
}

#[test]
fn scratch_search_rejects_address_wrap_before_any_write() {
    let mut code = vec![format!(
        "push 5 push {} push 0 call scan halt",
        BFieldElement::P - 4
    )];
    scan("scan", &mut code);
    let mut vm = machine(&code.join("\n"));
    // A falsely wrapped search would find these cells and incorrectly succeed.
    while !vm.halting && vm.cycle_count < 200 {
        if let Err(error) = vm.step() {
            assert!(
                matches!(
                    error,
                    triton_vm::error::InstructionError::AssertionFailed(_)
                ),
                "{error:?}"
            );
            assert!(vm.ram.values().all(|value| value.value() == 0));
            return;
        }
    }
    panic!("exhausted search must reject instead of wrapping or hanging");
}

#[test]
fn deep_access_restores_ram_when_its_end_pointer_wraps() {
    for depth in [16, 17, 31, 64] {
        for duplicate in [false, true] {
            let mut code: Vec<_> = (0..=depth).map(|value| format!("push {value}")).collect();
            access(depth, duplicate, "scan_from_end", &mut code);
            batch("write_io", depth + 1 + u32::from(duplicate), &mut code);
            code.push("halt".into());
            // Feed the unmodified scanner a run ending at p-1, so the native
            // write pointer wraps to zero while every allocated cell is valid.
            let cells = depth - 13;
            code.push(format!(
                "scan_from_end:\npop 2\npush {}\npush 0\ncall scan\nreturn",
                BFieldElement::P - u64::from(cells)
            ));
            scan("scan", &mut code);
            let mut vm = machine(&code.join("\n"));
            // Force the production fast path to use our controlled scanner.
            vm.ram.insert(bfe!(1u64 << 31), bfe!(999));
            vm.run().unwrap();
            let mut expected: Vec<_> = (0..=depth).rev().map(|v| bfe!(v)).collect();
            if duplicate {
                expected.insert(0, bfe!(0));
            } else {
                expected.swap(0, depth as usize);
            }
            assert_eq!(vm.public_output, expected);
            assert!(vm.ram.iter().all(|(address, value)| {
                if address.value() == 1u64 << 31 {
                    value.value() == 999
                } else {
                    value.value() == 0
                }
            }));
        }
    }
}
