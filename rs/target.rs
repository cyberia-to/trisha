//! Embedded, version-matched Triton and Neptune target package.
use std::path::Path;
use trident::target::{
    RuntimeCapabilities, StateConfig, TargetPackage, TerrainConfig, UnionConfig,
};

pub fn terrain() -> Result<TerrainConfig, String> {
    TerrainConfig::parse_toml(
        include_str!("../targets/triton/target.toml"),
        Path::new("trisha:targets/triton/target.toml"),
    )
    .map_err(|error| error.message)
}

pub fn package(target: &str) -> Result<TargetPackage, String> {
    if !matches!(target, "triton" | "neptune") {
        return Err(format!("Trisha does not provide target '{target}'"));
    }
    let union = if target == "neptune" {
        Some(
            UnionConfig::parse_toml(
                include_str!("../networks/neptune/target.toml"),
                Path::new("trisha:networks/neptune/target.toml"),
            )
            .map_err(|error| error.message)?,
        )
    } else {
        None
    };
    let mut states = Vec::new();
    if union.is_some() {
        for (name, source) in crate::resources::FILES {
            if name.starts_with("networks/neptune/states/") {
                states.push(
                    StateConfig::parse_toml(source, Path::new(name))
                        .map_err(|error| error.message)?,
                );
            }
        }
    }
    TargetPackage {
        schema_version: 1,
        compiler_api: 1,
        owner: "trisha".into(),
        version: env!("CARGO_PKG_VERSION").into(),
        terrain: terrain()?,
        union,
        states,
        modules: crate::resources::modules()
            .filter(|(name, _)| target == "neptune" || !name.starts_with("os."))
            .collect(),
        module_hashes: Default::default(),
        intrinsics: include_str!("../targets/triton/intrinsics.txt")
            .lines().map(str::to_owned).collect(),
        instructions: include_str!("../targets/triton/instructions.txt")
            .split_whitespace()
            .map(str::to_owned)
            .collect(),
        runtime: RuntimeCapabilities {
            run: true,
            prove: true,
            verify: true,
            deploy: false,
            proof_formats: vec!["stark-triton-v2".into()],
            restrictions: vec![
                "CPU proving backend; mining GPU features do not select a GPU prover".into(),
                "Live Neptune deployment is unsupported".into(),
                "Recursive STARK verification and Neptune transaction validation are unavailable"
                    .into(),
            ],
        },
    }
    .seal()
}
