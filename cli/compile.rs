use crate::error::TrishaError;
use std::path::Path;
use trident::runtime::{artifact::BundleCost, ProgramBundle};

pub fn compile_source(
    input: &Path,
    target: &str,
    profile: &str,
) -> Result<ProgramBundle, TrishaError> {
    let options =
        trisha_rs::lower::compile_options(target, profile).map_err(TrishaError::Compile)?;
    let (entry, options) = trident::source_options(input, &options).map_err(|errors| {
        TrishaError::Compile(
            errors
                .into_iter()
                .map(|e| e.message)
                .collect::<Vec<_>>()
                .join("; "),
        )
    })?;
    let source = std::fs::read_to_string(&entry)?;
    let parsed =
        trident::parse_source_silent(&source, &entry.to_string_lossy()).map_err(|errors| {
            TrishaError::Compile(
                errors
                    .into_iter()
                    .map(|e| e.message)
                    .collect::<Vec<_>>()
                    .join("; "),
            )
        })?;
    if parsed.kind != trident::ast::FileKind::Program {
        return Err(TrishaError::Compile(
            "execution requires a program entry; use build for a library module".to_string(),
        ));
    }
    let assembly = trisha_rs::build_tasm(input, target, profile).map_err(TrishaError::Compile)?;
    // Runtime traces provide actual costs; an empty estimate is not a fabricated measurement.
    let cost = BundleCost {
        table_values: Vec::new(),
        table_names: Vec::new(),
        padded_height: 0,
        estimated_proving_ns: 0,
    };
    trident::bundle_with_assembly(&entry, &options, assembly, cost).map_err(|diagnostics| {
        TrishaError::Compile(
            diagnostics
                .iter()
                .map(|d| d.message.clone())
                .collect::<Vec<_>>()
                .join("; "),
        )
    })
}
