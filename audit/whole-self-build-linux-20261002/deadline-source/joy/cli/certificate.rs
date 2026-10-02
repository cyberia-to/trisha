use crate::{artifact_run::Emit, error::JoyError};
use clap::Args;
use joy_rs::structured::{
    certificate::{self, CertificateLimits},
    RunLimits,
};
use std::path::PathBuf;

#[derive(Args)]
pub struct ProofLimits {
    /// Maximum encoded certificate file bytes
    #[arg(long, default_value_t = 64 << 20)]
    pub proof_bytes: u64,
    /// Maximum decoded certificate payload bytes
    #[arg(long, default_value_t = 256 << 20)]
    pub proof_decoded_bytes: u64,
    /// Maximum payload records, including noun definitions and resets
    #[arg(long, default_value_t = 4_000_000)]
    pub proof_records: u64,
    /// Maximum expanded semantic steps, including cached derivations
    #[arg(long, default_value_t = 2_000_000)]
    pub proof_steps: u64,
    #[arg(long, default_value_t = 65_536)]
    pub proof_cache_slots: u32,
}
impl ProofLimits {
    fn values(&self, host: RunLimits) -> CertificateLimits {
        CertificateLimits {
            nouns: host
                .compaction
                .map_or(host.arena_nodes, |p| p.resident_nodes.min(host.arena_nodes)),
            cache_slots: self.proof_cache_slots,
            records: self.proof_records,
            steps: self.proof_steps,
            wire_bytes: self.proof_bytes,
            decoded_bytes: self.proof_decoded_bytes,
        }
    }
}

#[derive(Args)]
pub struct ProveArgs {
    /// Complete nox ART1 program, including compiler-profile programs
    pub program: PathBuf,
    #[arg(long)]
    pub input: PathBuf,
    /// Public disclosed certificate destination
    #[arg(short, long)]
    pub output: PathBuf,
    #[arg(long)]
    pub force: bool,
    #[command(flatten)]
    pub limits: crate::artifact_limits::LimitArgs,
    #[command(flatten)]
    pub proof_limits: ProofLimits,
}

#[derive(Args)]
pub struct VerifyArgs {
    /// Expected complete nox ART1 program
    pub program: PathBuf,
    #[arg(long)]
    pub input: PathBuf,
    #[arg(long)]
    pub proof: PathBuf,
    /// Optionally publish the verified result or extracted compiler program
    #[arg(short, long)]
    pub output: Option<PathBuf>,
    #[arg(long, requires = "output")]
    pub force: bool,
    #[arg(long, value_enum, default_value = "result")]
    pub emit: Emit,
    #[command(flatten)]
    pub limits: crate::artifact_limits::LimitArgs,
    #[command(flatten)]
    pub proof_limits: ProofLimits,
}

pub fn prove(args: ProveArgs) -> Result<serde_json::Value, JoyError> {
    let host = args.limits.values();
    let caps = args.proof_limits.values(host);
    let result = crate::publication::atomic_produce(&args.output, args.force, |file| {
        certificate::prove_files(&args.program, &args.input, file, host, caps)
            .map_err(JoyError::Execute)
    })?;
    Ok(
        serde_json::json!({"schema":"joy/artifact-proof/v1","ok":true,
        "certificate":args.output.to_string_lossy(),"verification":result.report}),
    )
}

pub fn verify(args: VerifyArgs) -> Result<serde_json::Value, JoyError> {
    let host = args.limits.values();
    let caps = args.proof_limits.values(host);
    let result = certificate::verify_files(&args.program, &args.input, &args.proof, host, caps)
        .map_err(JoyError::Execute)?;
    let (bytes, particle) = match args.emit {
        Emit::Result => (&result.output, result.report.output_particle.as_str()),
        Emit::Program => {
            let job = result.report.compiler_job.as_ref().ok_or_else(|| {
                JoyError::Execute("--emit program requires compiler profile(1,1)".into())
            })?;
            let bytes = result.compiled.as_ref().ok_or_else(|| {
                JoyError::Execute(format!("guest compilation failed: {:?}", job.diagnostics))
            })?;
            (
                bytes,
                job.compiled_particle
                    .as_deref()
                    .ok_or_else(|| JoyError::Execute("missing compiled particle".into()))?,
            )
        }
    };
    if let Some(path) = &args.output {
        crate::publication::atomic_write(path, bytes, args.force)?;
    }
    Ok(
        serde_json::json!({"schema":"joy/artifact-verification/v1","ok":true,
        "artifact":args.output.as_ref().map(|p|p.to_string_lossy()),
        "published_particle":args.output.as_ref().map(|_|particle),"verification":result.report}),
    )
}
