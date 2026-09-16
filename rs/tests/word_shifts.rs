//! Check the shared TIR word ABI against native integer arithmetic on Triton.
use trident::tir::TIROp;
use trisha_rs::lower::{StackLowering, TritonLowering};
use triton_vm::prelude::*;

fn execute(op: TIROp, value: u32, shift: u32) -> Vec<u64> {
    let ops = [
        TIROp::Push(97),
        TIROp::Push(u64::from(value)),
        TIROp::Push(u64::from(shift)),
        op,
        TIROp::WriteIo(2),
    ];
    let assembly = TritonLowering::new().lower(&ops).join("\n") + "\nhalt";
    VM::run(
        Program::from_code(&assembly).unwrap(),
        PublicInput::default(),
        NonDeterminism::default(),
    )
    .unwrap()
    .into_iter()
    .map(|v| v.value())
    .collect()
}

#[test]
fn right_shift_returns_floor_quotient_and_preserves_neighboring_words() {
    for value in [0, 1, 2, 3, 9, 0x8000_0000, 0xabcd_ef01, u32::MAX] {
        for shift in 0..32 {
            assert_eq!(
                execute(TIROp::Shr, value, shift),
                [u64::from(value >> shift), 97],
                "{value} >> {shift}"
            );
        }
    }
}

#[test]
fn left_shift_multiplies_by_the_requested_power_of_two() {
    for value in [0, 1, 2, 3, 9, 0x8000_0000, 0xabcd_ef01, u32::MAX] {
        for shift in 0..32 {
            assert_eq!(
                execute(TIROp::Shl, value, shift),
                [u64::from(value) << shift, 97],
                "{value} << {shift}"
            );
        }
    }
}
