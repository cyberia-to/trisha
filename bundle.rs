//! Shared boundary validation for every implemented Triton backend.
pub(crate) fn validate(bundle: &trident::runtime::ProgramBundle) -> Result<(), String> {
    if bundle.target_vm != "triton" {
        return Err(format!(
            "Trisha requires a Triton bundle, received '{}'",
            bundle.target_vm
        ));
    }
    if bundle
        .target_os
        .as_deref()
        .is_some_and(|name| name != "neptune")
    {
        return Err("Trisha supports only the Neptune runtime".into());
    }
    if bundle.reads_state {
        return Err("Triton state witnesses are unsupported by this warrior".into());
    }
    Ok(())
}
