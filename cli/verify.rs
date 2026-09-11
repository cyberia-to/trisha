use std::path::PathBuf;
use std::process;

use clap::{Args, Subcommand};

use trident::runtime::Verifier;
use trisha_rs::Warrior;

use crate::batch;
use crate::error::TrishaError;

use super::load_proof_data;

#[derive(Args)]
#[command(args_conflicts_with_subcommands = true)]
pub struct VerifyArgs {
    #[command(subcommand)]
    pub mode: Option<VerifyMode>,

    pub proof: Option<PathBuf>,
    #[arg(long, default_value = "triton")]
    pub target: String,
}

#[derive(Subcommand)]
pub enum VerifyMode {
    Batch(VerifyBatchArgs),
}

#[derive(Args)]
pub struct VerifyBatchArgs {
    pub proofs: Vec<PathBuf>,
    #[arg(long, default_value = "triton")]
    pub target: String,
    #[arg(long, default_value = "4")]
    pub max_parallel: usize,
}

pub fn cmd_verify(args: VerifyArgs) {
    let target = match &args.mode {
        Some(VerifyMode::Batch(batch)) => &batch.target,
        None => &args.target,
    };
    crate::require_target(target);
    match args.mode {
        Some(VerifyMode::Batch(batch_args)) => cmd_verify_batch(batch_args),
        None => {
            let proof = match args.proof {
                Some(p) => p,
                None => {
                    eprintln!("error: no proof file specified");
                    process::exit(1);
                }
            };
            cmd_verify_single(proof);
        }
    }
}

fn cmd_verify_single(proof_path: PathBuf) {
    let proof_data = match load_proof_data(&proof_path) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let warrior = Warrior::new();
    match warrior.verify(&proof_data) {
        Ok(true) => println!("Verification: PASS"),
        Ok(false) => {
            println!("Verification: FAIL");
            process::exit(1);
        }
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_verify_batch(args: VerifyBatchArgs) {
    if args.proofs.is_empty() {
        eprintln!("error: no proof files specified");
        process::exit(1);
    }
    let count = args.proofs.len();
    eprintln!(
        "Verifying {} proofs (max {} parallel)...",
        count, args.max_parallel
    );
    let results = batch::run_batch(args.proofs, args.max_parallel, |path| {
        let proof_data = load_proof_data(&path)?;
        let warrior = Warrior::new();
        let valid = warrior.verify(&proof_data).map_err(TrishaError::Verify)?;
        Ok::<(PathBuf, bool), TrishaError>((path, valid))
    });
    let mut failures = 0;
    for r in &results {
        match &r.result {
            Ok((path, true)) => {
                eprintln!("  {} PASS ({} ms)", path.display(), r.elapsed_ms);
            }
            Ok((path, false)) => {
                eprintln!("  {} FAIL", path.display());
                failures += 1;
            }
            Err(e) => {
                eprintln!("  [{}] ERROR: {}", r.index, e);
                failures += 1;
            }
        }
    }
    eprintln!("{}/{} verified", count - failures, count);
    if failures > 0 {
        process::exit(1);
    }
}
