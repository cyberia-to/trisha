use std::path::PathBuf;
use std::process;

use clap::{Args, Subcommand};

use trisha_rs::Warrior;

use crate::batch;
use crate::compile::compile_source;
use crate::error::TrishaError;
use crate::proof_file::{ClaimSection, DataSection, ProofFile, ProofMeta};

use super::{bundle_from_tasm, make_input};

#[derive(Args)]
#[command(args_conflicts_with_subcommands = true)]
pub struct ProveArgs {
    #[command(subcommand)]
    pub mode: Option<ProveMode>,

    pub input: Option<PathBuf>,
    #[arg(long)]
    pub tasm: Option<PathBuf>,
    #[arg(long, default_value = "triton")]
    pub target: String,
    #[arg(long, default_value = "release")]
    pub profile: String,
    #[arg(long, value_delimiter = ',')]
    pub input_values: Option<Vec<u64>>,
    #[arg(long, value_delimiter = ',')]
    pub secret: Option<Vec<u64>>,
    #[arg(long, value_delimiter = ',')]
    pub digests: Option<Vec<u64>>,
    #[arg(long)]
    pub output: Option<PathBuf>,
}

#[derive(Subcommand)]
pub enum ProveMode {
    Batch(ProveBatchArgs),
}

#[derive(Args)]
pub struct ProveBatchArgs {
    pub inputs: Vec<PathBuf>,
    #[arg(long, default_value = "triton")]
    pub target: String,
    #[arg(long, default_value = "release")]
    pub profile: String,
    #[arg(long, value_delimiter = ',')]
    pub input_values: Option<Vec<u64>>,
    #[arg(long, value_delimiter = ',')]
    pub secret: Option<Vec<u64>>,
    #[arg(long, value_delimiter = ',')]
    pub digests: Option<Vec<u64>>,
    #[arg(long, default_value = ".")]
    pub output: PathBuf,
    #[arg(long, default_value = "4")]
    pub max_parallel: usize,
}

pub fn cmd_prove(args: ProveArgs) {
    match args.mode {
        Some(ProveMode::Batch(batch_args)) => cmd_prove_batch(batch_args),
        None => {
            if let Some(ref tasm_path) = args.tasm {
                cmd_prove_tasm(
                    tasm_path,
                    &args.input_values,
                    &args.secret,
                    &args.digests,
                    args.output,
                );
                return;
            }
            let input = match args.input {
                Some(p) => p,
                None => {
                    eprintln!("error: no input file specified");
                    process::exit(1);
                }
            };
            cmd_prove_single(
                input,
                &args.target,
                &args.profile,
                &args.input_values,
                &args.secret,
                &args.digests,
                args.output,
            );
        }
    }
}

fn write_proof_file(
    proof_file: ProofFile,
    output_path: &PathBuf,
    proving_time_ms: u64,
    cycle_count: u64,
) {
    if let Err(e) = proof_file.save(output_path) {
        eprintln!("error: {}", e);
        process::exit(1);
    }
    eprintln!(
        "Proof written to {} ({} ms, {} cycles)",
        output_path.display(),
        proving_time_ms,
        cycle_count,
    );
}

fn cmd_prove_single(
    input: PathBuf,
    target: &str,
    profile: &str,
    input_values: &Option<Vec<u64>>,
    secret: &Option<Vec<u64>>,
    digests: &Option<Vec<u64>>,
    output: Option<PathBuf>,
) {
    let bundle = match compile_source(&input, target, profile) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let pi = make_input(input_values, secret, digests);
    let start = std::time::Instant::now();
    let warrior = Warrior::new();
    let result = match warrior.prove_full(&bundle, &pi) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let proving_time_ms = start.elapsed().as_millis() as u64;

    let output_path = output.unwrap_or_else(|| {
        let stem = input.file_stem().unwrap_or_default().to_string_lossy();
        let dir = PathBuf::from("target/proofs");
        let _ = std::fs::create_dir_all(&dir);
        dir.join(format!("{}.proof.toml", stem))
    });

    let proof_file = ProofFile {
        proof: ProofMeta {
            format: result.proof_data.format.clone(),
            program_name: bundle.name.clone(),
            cycle_count: result.cycle_count,
            padded_height: result.padded_height,
            proving_time_ms,
        },
        claim: ClaimSection {
            program_hash: result.proof_data.claim.program_hash.clone(),
            public_input: result.proof_data.claim.public_input.clone(),
            public_output: result.proof_data.claim.public_output.clone(),
        },
        data: DataSection {
            proof: ProofFile::encode_proof_bytes(&result.proof_data.proof_bytes),
        },
    };
    for val in &result.proof_data.claim.public_output {
        println!("{}", val);
    }
    write_proof_file(proof_file, &output_path, proving_time_ms, result.cycle_count);
}

fn cmd_prove_tasm(
    tasm_path: &std::path::Path,
    input_values: &Option<Vec<u64>>,
    secret: &Option<Vec<u64>>,
    digests: &Option<Vec<u64>>,
    output: Option<PathBuf>,
) {
    let bundle = match bundle_from_tasm(tasm_path) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let pi = make_input(input_values, secret, digests);
    let start = std::time::Instant::now();
    let warrior = Warrior::new();
    let result = match warrior.prove_full(&bundle, &pi) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let proving_time_ms = start.elapsed().as_millis() as u64;

    let output_path = output.unwrap_or_else(|| {
        let stem = tasm_path.file_stem().unwrap_or_default().to_string_lossy();
        let dir = PathBuf::from("target/proofs");
        let _ = std::fs::create_dir_all(&dir);
        dir.join(format!("{}.proof.toml", stem))
    });

    let proof_file = ProofFile {
        proof: ProofMeta {
            format: result.proof_data.format.clone(),
            program_name: bundle.name.clone(),
            cycle_count: result.cycle_count,
            padded_height: result.padded_height,
            proving_time_ms,
        },
        claim: ClaimSection {
            program_hash: result.proof_data.claim.program_hash.clone(),
            public_input: result.proof_data.claim.public_input.clone(),
            public_output: result.proof_data.claim.public_output.clone(),
        },
        data: DataSection {
            proof: ProofFile::encode_proof_bytes(&result.proof_data.proof_bytes),
        },
    };
    for val in &result.proof_data.claim.public_output {
        println!("{}", val);
    }
    write_proof_file(proof_file, &output_path, proving_time_ms, result.cycle_count);
}

fn cmd_prove_batch(args: ProveBatchArgs) {
    if args.inputs.is_empty() {
        eprintln!("error: no input files specified");
        process::exit(1);
    }
    if let Err(e) = std::fs::create_dir_all(&args.output) {
        eprintln!("error: cannot create output directory: {}", e);
        process::exit(1);
    }
    let target = args.target.clone();
    let profile = args.profile.clone();
    let input_values = args.input_values.clone();
    let secret = args.secret.clone();
    let digests = args.digests.clone();
    let output_dir = args.output.clone();
    let count = args.inputs.len();
    eprintln!(
        "Proving {} programs (max {} parallel)...",
        count, args.max_parallel
    );
    let results = batch::run_batch(args.inputs, args.max_parallel, |path| {
        let bundle = compile_source(&path, &target, &profile)?;
        let pi = make_input(&input_values, &secret, &digests);
        let warrior = Warrior::new();
        let start = std::time::Instant::now();
        let result = warrior.prove_full(&bundle, &pi).map_err(TrishaError::Prove)?;
        let proving_time_ms = start.elapsed().as_millis() as u64;

        let stem = path.file_stem().unwrap_or_default().to_string_lossy();
        let out_path = output_dir.join(format!("{}.proof.toml", stem));

        let proof_file = ProofFile {
            proof: ProofMeta {
                format: result.proof_data.format.clone(),
                program_name: bundle.name.clone(),
                cycle_count: result.cycle_count,
                padded_height: result.padded_height,
                proving_time_ms,
            },
            claim: ClaimSection {
                program_hash: result.proof_data.claim.program_hash.clone(),
                public_input: result.proof_data.claim.public_input.clone(),
                public_output: result.proof_data.claim.public_output.clone(),
            },
            data: DataSection {
                proof: ProofFile::encode_proof_bytes(&result.proof_data.proof_bytes),
            },
        };
        proof_file.save(&out_path)?;
        Ok::<(PathBuf, u64), TrishaError>((out_path, proving_time_ms))
    });
    let mut failures = 0;
    for r in &results {
        match &r.result {
            Ok((path, prove_ms)) => {
                eprintln!("  {} ({} ms)", path.display(), prove_ms);
            }
            Err(e) => {
                eprintln!("  [{}] FAIL: {}", r.index, e);
                failures += 1;
            }
        }
    }
    eprintln!("{}/{} proofs generated", count - failures, count);
    if failures > 0 {
        process::exit(1);
    }
}
