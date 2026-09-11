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
    #[arg(long, default_value = "triton")]
    pub target: String,

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
    let tasm = trisha_rs::build_tasm(&args.input, &args.target, &args.profile)
        .map_err(TrishaError::Compile)?;

    let out = args
        .output
        .unwrap_or_else(|| args.input.with_extension("tasm"));
    std::fs::write(&out, &tasm)
        .map_err(|e| TrishaError::Io(format!("cannot write '{}': {}", out.display(), e)))?;

    eprintln!("Compiled -> {}", out.display());

    if args.costs {
        let source = std::fs::read_to_string(&args.input)
            .map_err(|e| TrishaError::Io(format!("cannot read '{}': {}", args.input.display(), e)))?;
        match trisha_rs::cost::analyze_source(&source, &args.input.to_string_lossy()) {
            Ok(cost) => eprintln!("\n{}", cost.format_report()),
            Err(e) => eprintln!("warning: cost analysis failed: {}", e),
        }
    }

    Ok(())
}
