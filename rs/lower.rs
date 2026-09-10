//! TIR → TASM: the last mile, owned by the warrior.
//!
//! trident stops at TIR — `trident::build_tir_modules` hands over typed,
//! optimized, monomorphized TIR with module boundaries intact
//! (trident/reference/warrior-api.md). Turning that into Triton assembly
//! and linking the modules is knowledge about one machine, so it lives
//! here rather than in the language.
//!
//! Output is byte-identical to `trident build --target triton`, because
//! both still run the same lowering code; what changed is who drives it.
//! `tests/build_matches_trident.rs` pins that equality so the move can
//! finish (trident's copy going away) without silently changing output.

use std::path::Path;

use trident::tir::linker::{link, ModuleTasm};
use trident::tir::lower::create_stack_lowering;
use trident::CompileOptions;

/// Lower a project to linked TASM.
///
/// `target` names a terrain (`triton`) or a battlefield (`neptune`);
/// `profile` selects cfg flags (`debug` / `release`).
pub fn build_tasm(input: &Path, target: &str, profile: &str) -> Result<String, String> {
    let mut options = CompileOptions::for_profile(profile);
    // The warrior's own terrain, not the compiler's default (which is nox).
    options.target_config = trident::target::TerrainConfig::triton();
    if let Ok(resolved) = trident::target::ResolvedTarget::resolve(target) {
        options.target_config = resolved.vm;
    }

    let modules = trident::build_tir_modules(input, &options).map_err(|diagnostics| {
        diagnostics
            .iter()
            .map(|d| d.message.clone())
            .collect::<Vec<_>>()
            .join("; ")
    })?;

    let lowering = create_stack_lowering(&options.target_config.name);
    let lowered: Vec<ModuleTasm> = modules
        .into_iter()
        .map(|m| ModuleTasm {
            module_name: m.name,
            is_program: m.is_program,
            tasm: lowering.lower(&m.ops).join("\n"),
        })
        .collect();

    Ok(link(lowered))
}
