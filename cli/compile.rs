use std::path::Path;

use trident::runtime::ProgramBundle;
use trident::{compile_to_bundle, CompileOptions};

use crate::error::TrishaError;

pub fn compile_source(
    input: &Path,
    target: &str,
    profile: &str,
) -> Result<ProgramBundle, TrishaError> {
    let mut options = CompileOptions::for_profile(profile);

    if let Ok(resolved) = trident::target::ResolvedTarget::resolve(target) {
        options.target_config = resolved.vm;
    }

    compile_to_bundle(input, &options).map_err(|diagnostics| {
        let messages: Vec<String> = diagnostics.iter().map(|d| d.message.clone()).collect();
        TrishaError::Compile(messages.join("; "))
    })
}
