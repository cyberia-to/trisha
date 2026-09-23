//! Caller-selected fixed Neptune policy claims. Proof metadata cannot select policy.
use crate::{
    error::TrishaError,
    input_file::{read_bounded, Field},
};
use clap::ValueEnum;
use serde::Deserialize;
use std::path::Path;
use trisha_rs::recursive::{
    NativeClaim as Claim, NativeDigest as Digest, NativeField as BFieldElement,
};

#[derive(Clone, Copy, ValueEnum)]
pub enum Policy {
    NeptuneTransaction,
    NeptuneNativeCurrency,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Commitments {
    schema_version: u32,
    kernel: [Field; 5],
    inputs: Option<[Field; 5]>,
    outputs: Option<[Field; 5]>,
}
fn invalid() -> TrishaError {
    TrishaError::Verify("invalid policy commitments: version1 requires kernel Digest; native currency additionally requires inputs and outputs Digests".into())
}
fn digest(fields: [Field; 5]) -> Result<Digest, TrishaError> {
    let words = fields
        .into_iter()
        .map(Field::value)
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Digest::new(
        words
            .into_iter()
            .map(BFieldElement::new)
            .collect::<Vec<_>>()
            .try_into()
            .expect("five canonical fields"),
    ))
}
pub fn expected(policy: Policy, path: &Path) -> Result<(Claim, Vec<u64>), TrishaError> {
    let document: Commitments =
        serde_json::from_slice(&read_bounded(path)?).map_err(|_| invalid())?;
    if document.schema_version != 1 {
        return Err(invalid());
    }
    let kernel = digest(document.kernel)?;
    let mut public = kernel.values().map(|v| v.value()).to_vec();
    let claim = match policy {
        Policy::NeptuneTransaction => {
            if document.inputs.is_some() || document.outputs.is_some() {
                return Err(invalid());
            }
            trisha_rs::recursive::neptune::transaction_claim(kernel)
        }
        Policy::NeptuneNativeCurrency => {
            let inputs = digest(document.inputs.ok_or_else(invalid)?)?;
            let outputs = digest(document.outputs.ok_or_else(invalid)?)?;
            public.extend(inputs.values().map(|v| v.value()));
            public.extend(outputs.values().map(|v| v.value()));
            trisha_rs::recursive::neptune::native_currency_claim(kernel, inputs, outputs)
        }
    };
    Ok((claim, public))
}
