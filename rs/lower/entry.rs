//! Triton owns the public-stream adapter for generic typed entry metadata.
use trident::tir::{EntryLeaf, TIROp};

pub(super) fn validate(ops: &[TIROp]) -> Result<(), String> {
    validate_structure(ops, true)
}

fn validate_structure(ops: &[TIROp], top_level: bool) -> Result<(), String> {
    let mut seen_entry = false;
    let mut in_function = false;
    let mut seen = false;
    for (index, op) in ops.iter().enumerate() {
        match op {
            TIROp::FnStart(_) => in_function = true,
            TIROp::FnEnd => in_function = false,
            TIROp::EntryParameters(leaves) => {
                if !top_level
                    || in_function
                    || seen
                    || seen_entry
                    || !matches!(ops.get(index + 1), Some(TIROp::Entry(_)))
                {
                    return Err("typed entry metadata must precede the program entry".into());
                }
                seen = true;
                if let Some(reason) = leaves.iter().find_map(|leaf| match leaf {
                    EntryLeaf::Unresolved(reason) => Some(reason),
                    _ => None,
                }) {
                    return Err(format!(
                        "unresolved type in program entry signature: {reason}"
                    ));
                }
            }
            TIROp::Entry(_) => {
                if !top_level || in_function || seen_entry {
                    return Err("program entry must occur once at top level".into());
                }
                seen_entry = true;
            }
            TIROp::IfElse {
                then_body,
                else_body,
            } => {
                validate_structure(then_body, false)?;
                validate_structure(else_body, false)?;
            }
            TIROp::IfOnly { then_body } => validate_structure(then_body, false)?,
            TIROp::Loop { body, .. } | TIROp::ProofBlock { body, .. } => {
                validate_structure(body, false)?
            }
            _ => {}
        }
    }
    Ok(())
}

pub(super) fn emit(leaves: &[EntryLeaf], out: &mut Vec<String>) {
    for leaf in leaves {
        out.push("    read_io 1".into());
        match leaf {
            EntryLeaf::Field => {}
            EntryLeaf::Bool => {
                // x(x-1)=0 over the field accepts exactly zero or one.
                out.extend(
                    [
                        "dup 0", "dup 0", "push -1", "add", "mul", "push 0", "eq", "assert",
                    ]
                    .map(|line| format!("    {line}")),
                );
            }
            EntryLeaf::U32 => {
                // Preserve the low limb, require the canonical field's high limb zero.
                out.extend(
                    ["split", "swap 1", "push 0", "eq", "assert"].map(|line| format!("    {line}")),
                );
            }
            EntryLeaf::Unresolved(_) => panic!("unresolved entry ABI; use checked lowering"),
        }
    }
}
