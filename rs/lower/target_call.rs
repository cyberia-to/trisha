//! Validate and implement the owner's opaque target calls.
use super::StackLowering;
use trident::tir::TIROp;

fn validate(name: &str, inputs: u32, outputs: u32) -> Result<(), String> {
    if matches!(
        (name, inputs, outputs),
        ("triton_program_digest", 0, 5)
            | ("triton_stark_verify_v1", 5, 0)
            | ("neptune_transaction_verify_v1", 5, 0)
            | ("neptune_native_currency_verify_v1", 15, 0)
    ) {
        Ok(())
    } else {
        Err(format!(
            "unsupported Triton target call '{name}' with ABI {inputs}->{outputs}"
        ))
    }
}

pub fn validate_target_calls(ops: &[TIROp]) -> Result<(), String> {
    super::entry::validate(ops)?;
    validate_calls(ops)
}

fn validate_calls(ops: &[TIROp]) -> Result<(), String> {
    for op in ops {
        match op {
            TIROp::Comment(message) if message.starts_with("ERROR:") => {
                return Err(message.clone());
            }
            TIROp::TargetCall {
                name,
                inputs,
                outputs,
            } => validate(name, *inputs, *outputs)?,
            TIROp::IfElse {
                then_body,
                else_body,
            } => {
                validate_calls(then_body)?;
                validate_calls(else_body)?;
            }
            TIROp::IfOnly { then_body } => validate_calls(then_body)?,
            TIROp::Loop { body, .. } | TIROp::ProofBlock { body, .. } => validate_calls(body)?,
            _ => {}
        }
    }
    Ok(())
}

/// Fallible lowering for callers supplying raw TIR rather than checked source.
pub fn lower_checked(ops: &[TIROp]) -> Result<Vec<String>, String> {
    validate_target_calls(ops)?;
    Ok(super::TritonLowering::new().lower(ops))
}

pub(super) fn emit(name: &str, inputs: u32, outputs: u32, out: &mut Vec<String>) {
    // The low-level StackLowering trait accepts already validated TIR. Never emit
    // a success artifact for a forged or unsupported operation even if bypassed.
    assert!(
        validate(name, inputs, outputs).is_ok(),
        "invalid raw target call; use lower_checked"
    );
    let entrypoint = match name {
        "triton_program_digest" => crate::recursive::program_context::ENTRYPOINT,
        "triton_stark_verify_v1" => crate::recursive::ENTRYPOINT,
        "neptune_transaction_verify_v1" => crate::recursive::neptune::TRANSACTION_ENTRYPOINT,
        "neptune_native_currency_verify_v1" => {
            crate::recursive::neptune::NATIVE_CURRENCY_ENTRYPOINT
        }
        _ => unreachable!("validated target call"),
    };
    out.push(format!("    call @{entrypoint}"));
}
