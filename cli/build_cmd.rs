//! `trisha build` — lower a Trident program to linked TASM.
//!
//! Named `build_cmd.rs`, not `build.rs`: cargo reserves that name for a
//! package build script (same reason `state_cmd.rs` sits beside `state.rs`).
//!
//! The lowering itself lives in `trisha_rs::lower`; this is the CLI skin.

use std::path::PathBuf;

use clap::Args;

use crate::error::TrishaError;

#[derive(Args)]
pub struct BuildArgs {
    /// .tri file (or project entry point)
    #[arg()]
    pub input: PathBuf,

    /// Terrain to build for
    #[arg(long)]
    pub target: Option<String>,

    /// Compilation profile for cfg flags
    #[arg(long, default_value = "debug")]
    pub profile: String,

    /// Output file (default: <input>.tasm next to the source)
    #[arg(short = 'o', long)]
    pub output: Option<PathBuf>,

    /// Print the AET-table cost report (single-file only — see
    /// trisha_rs::cost::analyze_source)
    #[arg(long)]
    pub costs: bool,
}

pub fn cmd_build(args: BuildArgs) -> Result<(), TrishaError> {
    let target = crate::compile::resolve_target(Some(&args.input), args.target.as_deref())?;
    let options =
        trisha_rs::lower::compile_options(&target, &args.profile).map_err(TrishaError::Compile)?;
    let (entry, _) = trident::source_options(&args.input, &options).map_err(|errors| {
        TrishaError::Compile(
            errors
                .into_iter()
                .map(|error| error.message)
                .collect::<Vec<_>>()
                .join("; "),
        )
    })?;
    let tasm =
        trisha_rs::build_tasm(&entry, &target, &args.profile).map_err(TrishaError::Compile)?;

    let out = args.output.unwrap_or_else(|| entry.with_extension("tasm"));
    std::fs::write(&out, &tasm)
        .map_err(|e| TrishaError::Io(format!("cannot write '{}': {}", out.display(), e)))?;

    eprintln!("Compiled -> {}", out.display());

    if args.costs {
        let source = std::fs::read_to_string(&entry)
            .map_err(|e| TrishaError::Io(format!("cannot read '{}': {}", entry.display(), e)))?;
        match trisha_rs::cost::analyze_source(&source, &entry.to_string_lossy()) {
            Ok(cost) => eprintln!("\n{}", cost.format_report()),
            Err(e) => eprintln!("warning: cost analysis failed: {}", e),
        }
    }

    Ok(())
}
