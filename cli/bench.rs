//! Execute unchanged classic and hand programs against explicit reference vectors.
use crate::error::TrishaError;
use clap::Args;
use serde::Deserialize;
use std::path::{Path, PathBuf};
use trident::runtime::{ProgramInput, Runner, Verifier};
use trisha_rs::Warrior;

#[derive(Args)]
pub struct BenchArgs {
    /// Directory containing .bench.toml reference fixtures and hand baselines
    #[arg(default_value = "baselines/triton")]
    pub dir: PathBuf,
    /// Also prove and verify both programs
    #[arg(long)]
    pub full: bool,
    /// Retained for compatibility; neural candidates need independent verified fixtures
    #[arg(long)]
    pub skip_neural: bool,
}

#[derive(Deserialize)]
struct Fixture {
    source: PathBuf,
    hand: PathBuf,
    input: Vec<u64>,
    output: Vec<u64>,
    #[serde(default)]
    secret: Vec<u64>,
    /// Exact wrapper for library baselines. No instructions are replaced.
    #[serde(default)]
    hand_prefix: String,
}

fn collect(dir: &Path, extension: &str, result: &mut Vec<PathBuf>) -> Result<(), TrishaError> {
    for entry in std::fs::read_dir(dir)? {
        let path = entry?.path();
        if path.is_dir() {
            collect(&path, extension, result)?;
        } else if path.to_string_lossy().ends_with(extension) {
            result.push(path);
        }
    }
    Ok(())
}

pub fn cmd_bench(args: BenchArgs) -> Result<(), TrishaError> {
    let mut fixtures = Vec::new();
    let mut baselines = Vec::new();
    collect(&args.dir, ".bench.toml", &mut fixtures)?;
    collect(&args.dir, ".tasm", &mut baselines)?;
    fixtures.sort();
    let mut covered = std::collections::BTreeSet::new();
    let mut failed = 0;
    println!("fixture\tclassic_cycles\thand_cycles\thand/classic\tstatus");
    for path in &fixtures {
        match measure(path, args.full) {
            Ok((classic, hand, baseline)) => {
                covered.insert(baseline);
                // Integer fraction: same verified input/output vector in both dimensions.
                println!(
                    "{}\t{}\t{}\t{}/{}\tPASS",
                    path.display(),
                    classic,
                    hand,
                    hand,
                    classic
                );
            }
            Err(e) => {
                failed += 1;
                eprintln!("{}: {}", path.display(), e);
            }
        }
    }
    for baseline in &baselines {
        if !covered.contains(&baseline.canonicalize()?) {
            eprintln!(
                "UNVERIFIED {}: no passing reference fixture",
                baseline.display()
            );
        }
    }
    eprintln!(
        "{} / {} fixtures passed; {} / {} baselines verified",
        fixtures.len() - failed,
        fixtures.len(),
        covered.len(),
        baselines.len()
    );
    eprintln!("Neural: no verified reference fixtures");
    if fixtures.is_empty() || failed > 0 || covered.len() < baselines.len() {
        return Err(TrishaError::Execute(
            "benchmark coverage is incomplete or a reference check failed".to_string(),
        ));
    }
    Ok(())
}

fn measure(path: &Path, full: bool) -> Result<(u64, u64, PathBuf), TrishaError> {
    let fixture: Fixture = toml::from_str(&std::fs::read_to_string(path)?)
        .map_err(|e| TrishaError::Compile(format!("invalid benchmark fixture: {}", e)))?;
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    let source = parent.join(&fixture.source);
    let hand_path = parent.join(&fixture.hand);
    let classic = crate::compile::compile_source(&source, "triton", "release")?;
    let mut hand = crate::bundle_from_tasm(&hand_path)?;
    hand.assembly = fixture.hand_prefix + &hand.assembly;
    let input = ProgramInput {
        public: fixture.input,
        secret: fixture.secret,
        digests: Vec::new(),
    };
    let warrior = Warrior::new();
    let mut cycles = Vec::new();
    for (name, bundle) in [("classic", &classic), ("hand", &hand)] {
        let run = warrior.run(bundle, &input).map_err(TrishaError::Execute)?;
        if run.output != fixture.output {
            return Err(TrishaError::Execute(format!(
                "{} output {:?}, reference {:?}",
                name, run.output, fixture.output
            )));
        }
        if full {
            let proof = warrior
                .prove_full(bundle, &input)
                .map_err(TrishaError::Prove)?;
            if proof.proof_data.claim.public_output != fixture.output
                || !warrior
                    .verify(&proof.proof_data)
                    .map_err(TrishaError::Verify)?
            {
                return Err(TrishaError::Verify(format!(
                    "{} proof/reference validation failed",
                    name
                )));
            }
        }
        cycles.push(run.cycle_count);
    }
    Ok((cycles[0], cycles[1], hand_path.canonicalize()?))
}
