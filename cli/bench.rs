//! Execute unchanged classic and hand programs against explicit reference vectors.
use crate::error::TrishaError;
use clap::Args;
#[path = "bench_fixture.rs"]
mod fixture;
use fixture::Fixture;
use std::path::{Path, PathBuf};
use trident::runtime::{ProgramInput, Verifier};
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
    baselines = baselines
        .into_iter()
        .map(|p| p.canonicalize())
        .collect::<Result<_, _>>()?;
    let mut covered = std::collections::BTreeSet::new();
    let mut failed = 0;
    println!("fixture\tclassic_cycles\thand_cycles\thand/classic\tstatus");
    for path in &fixtures {
        match measure(path, args.full) {
            Ok((classic, hand, baseline)) => {
                if !baselines.contains(&baseline) {
                    baselines.push(baseline.clone());
                }
                if classic.is_some() {
                    covered.insert(baseline);
                }
                match (classic, hand) {
                    (Some(classic), Some(hand)) => println!(
                        "{}\t{}\t{}\t{}/{}\tPASS",
                        path.display(),
                        classic,
                        hand,
                        hand,
                        classic
                    ),
                    _ => println!(
                        "{}\t-\t-\t-\tPASS (both executions rejected)",
                        path.display()
                    ),
                }
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

fn measure(path: &Path, full: bool) -> Result<(Option<u64>, Option<u64>, PathBuf), TrishaError> {
    let mut fixture: Fixture = toml::from_str(&std::fs::read_to_string(path)?)
        .map_err(|e| TrishaError::Compile(format!("invalid benchmark fixture: {}", e)))?;
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    for witness_path in &fixture.witness_files {
        let witness: fixture::Witness =
            toml::from_str(&std::fs::read_to_string(parent.join(witness_path))?).map_err(|e| {
                TrishaError::Compile(format!("invalid private benchmark witness: {e}"))
            })?;
        if witness.digests.len() % 5 != 0 {
            return Err(TrishaError::Compile(
                "private witness contains incomplete digest".into(),
            ));
        }
        fixture.secret.extend(witness.secret);
        fixture.digests.extend(witness.digests);
    }
    let source = parent.join(&fixture.source);
    let hand_path = parent.join(&fixture.hand);
    let classic = crate::compile::compile_source(&source, &fixture.target, "release")?;
    let mut hand = crate::bundle_from_tasm(&hand_path)?;
    hand.assembly = fixture.hand_prefix + &hand.assembly;
    for library in &fixture.hand_libraries {
        hand.assembly.push('\n');
        hand.assembly
            .push_str(&std::fs::read_to_string(parent.join(library))?);
    }
    if fixture.digests.len() % 5 != 0
        || fixture
            .hand_digests
            .as_ref()
            .is_some_and(|d| d.len() % 5 != 0)
    {
        return Err(TrishaError::Compile(
            "fixture digest queue must contain complete five-field digests".into(),
        ));
    }
    if !fixture.reference.is_empty() {
        eprintln!("Reference: {}", fixture.reference);
    }
    let has_hand_override = fixture.hand_input.is_some()
        || fixture.hand_secret.is_some()
        || fixture.hand_digests.is_some();
    if has_hand_override && fixture.implementation_bound_identity.trim().is_empty() {
        return Err(TrishaError::Compile("implementation-specific inputs require an explicit implementation_bound_identity reference".into()));
    }
    if !fixture.implementation_bound_identity.is_empty() {
        eprintln!(
            "Implementation-bound public statements: {}",
            fixture.implementation_bound_identity
        );
    }
    let hand_input = ProgramInput {
        public: fixture.hand_input.unwrap_or_else(|| fixture.input.clone()),
        secret: fixture
            .hand_secret
            .unwrap_or_else(|| fixture.secret.clone()),
        digests: fixture
            .hand_digests
            .as_ref()
            .unwrap_or(&fixture.digests)
            .chunks_exact(5)
            .map(|d| [d[0], d[1], d[2], d[3], d[4]])
            .collect(),
    };
    let input = ProgramInput {
        public: fixture.input,
        secret: fixture.secret,
        digests: fixture
            .digests
            .chunks_exact(5)
            .map(|d| [d[0], d[1], d[2], d[3], d[4]])
            .collect(),
    };
    let warrior = Warrior::new();
    let mut cycles = Vec::new();
    for (name, bundle, input) in [("classic", &classic, &input), ("hand", &hand, &hand_input)] {
        let execution = warrior.run_bounded(bundle, input, fixture.max_cycles);
        if fixture.expect_failure {
            match execution {
                Err(error) if error.starts_with("execution error:") => continue,
                Err(error) => {
                    return Err(TrishaError::Execute(format!(
                        "{name} did not reach execution: {error}"
                    )));
                }
                Ok(_) => {
                    return Err(TrishaError::Execute(format!(
                        "{name} accepted a rejection vector"
                    )));
                }
            }
        }
        let run = execution.map_err(|error| TrishaError::Execute(format!("{name}: {error}")))?;
        if run.output != fixture.output {
            return Err(TrishaError::Execute(format!(
                "{} output {:?}, reference {:?}",
                name, run.output, fixture.output
            )));
        }
        if full {
            let expected_program = trisha_rs::deployment::inspect(bundle, None)
                .map_err(TrishaError::Compile)?
                .lock_script_hash;
            let proof = warrior
                .prove_full(bundle, input)
                .map_err(TrishaError::Prove)?;
            if proof.proof_data.claim.program_hash != expected_program
                || proof.proof_data.claim.public_input != input.public
                || proof.proof_data.claim.public_output != fixture.output
                || !warrior
                    .verify(&proof.proof_data)
                    .map_err(TrishaError::Verify)?
            {
                return Err(TrishaError::Verify(format!(
                    "{} proof/reference validation failed",
                    name
                )));
            }
            // Emitted only after this invocation generated and verified the proof.
            // Full release gates consume one exact classic/hand pair per fixture.
            let proof_hash = trident::hash::content_hash_bytes(&proof.proof_data.proof_bytes);
            println!(
                "TRISHA_PROOF_VERIFIED\t{}",
                serde_json::json!({
                    "schema_version": 1,
                    "fixture": path.canonicalize()?,
                    "implementation": name,
                    "format": proof.proof_data.format,
                    "program_hash": proof.proof_data.claim.program_hash,
                    "public_input": proof.proof_data.claim.public_input,
                    "public_output": proof.proof_data.claim.public_output,
                    "proof_hemera": proof_hash.iter().map(|byte| format!("{byte:02x}")).collect::<String>(),
                    "proof_bytes": proof.proof_data.proof_bytes.len(),
                    "generated_and_verified": true,
                })
            );
        }
        cycles.push(run.cycle_count);
    }
    if fixture.expect_failure {
        Ok((None, None, hand_path.canonicalize()?))
    } else {
        Ok((Some(cycles[0]), Some(cycles[1]), hand_path.canonicalize()?))
    }
}
