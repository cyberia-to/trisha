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
        compiler_api: trident::COMPILER_API,
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
            .lines()
            .map(str::to_owned)
            .chain((target == "neptune").then_some(["neptune_transaction_verify_v1", "neptune_native_currency_verify_v1"]).into_iter().flatten().map(str::to_owned))
            .collect(),
        intrinsic_abis: std::collections::BTreeMap::from([(
            "triton_program_digest".into(),
            trident::target::IntrinsicAbi { params:vec![], results:vec![trident::target::IntrinsicType::Digest] },
        ),(
            "triton_stark_verify_v1".into(),
            trident::target::IntrinsicAbi {
                params: vec![trident::target::IntrinsicType::Digest],
                results: vec![],
            },
        )]).into_iter().chain((target == "neptune").then_some([
            ("neptune_transaction_verify_v1".into(), trident::target::IntrinsicAbi { params: vec![trident::target::IntrinsicType::Digest], results: vec![] }),
            ("neptune_native_currency_verify_v1".into(), trident::target::IntrinsicAbi { params: vec![trident::target::IntrinsicType::Digest;3], results: vec![] }),
        ]).into_iter().flatten()).collect(),
        instructions: include_str!("../targets/triton/instructions.txt")
            .split_whitespace()
            .map(str::to_owned)
            .collect(),
        runtime: RuntimeCapabilities {
            run: true,
            prove: true,
            verify: true,
            deploy: false,
            proof_formats: vec!["stark-triton-v7".into()],
            restrictions: vec![
                "CPU proving backend; mining GPU features do not select a GPU prover".into(),
                "Generic bundle deployment is unsupported; Neptune transaction prepare/submit uses the separate validated-intent CLI".into(),
                "Triton VM 7.0.0 / native proof version 5; Neptune protocol reference 0.15.1, incompatible with legacy 0.10.2 nodes".into(),
                "Triton recursive verification requires a caller-authenticated full-claim commitment; Neptune checks pin 0.15.1 HardforkGamma policy and require caller-authenticated kernel/UTXO commitments"
                    .into(),
            ],
        },
    }
    .seal()
}
