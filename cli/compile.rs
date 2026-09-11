use crate::error::TrishaError;
use std::path::Path;
use trident::runtime::{artifact::BundleCost, ProgramBundle};

/// Explicit CLI target wins; otherwise use the enclosing project, then Triton.
pub fn resolve_target(input: Option<&Path>, explicit: Option<&str>) -> Result<String, TrishaError> {
    let target = if let Some(target) = explicit {
        target.to_owned()
    } else {
        let current = std::env::current_dir()?;
        let input = input.map(|path| current.join(path)).unwrap_or(current);
        let start = if input.is_dir() {
            input.as_path()
        } else {
            input.parent().unwrap_or(Path::new("."))
        };
        match trident::config::project::Project::find(start) {
            Some(path) => trident::config::project::Project::load(&path)
                .map_err(|error| TrishaError::Compile(error.message))?
                .target
                .unwrap_or_else(|| "triton".into()),
            None => "triton".into(),
        }
    };
    trisha_rs::target::package(&target).map_err(TrishaError::Compile)?;
    Ok(target)
}

pub fn selected_target(input: Option<&Path>, explicit: Option<&str>) -> String {
    resolve_target(input, explicit).unwrap_or_else(|error| {
        eprintln!("error: {error}");
        std::process::exit(1);
    })
}

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
