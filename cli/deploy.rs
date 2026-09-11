use std::path::PathBuf;
use std::process;

use clap::{Args, Subcommand};

use trident::runtime::Deployer;
use trisha_rs::Warrior;

use crate::batch;
use crate::compile::compile_source;
use crate::error::TrishaError;
use crate::NetworkArgs;

use super::load_proof_data;

#[derive(Args)]
#[command(args_conflicts_with_subcommands = true)]
pub struct DeployArgs {
    #[command(subcommand)]
    pub mode: Option<DeployMode>,

    pub input: Option<PathBuf>,
    #[arg(long, default_value = "triton")]
    pub vm: String,
    #[arg(long, default_value = "release")]
    pub profile: String,
    #[arg(long)]
    pub proof: Option<PathBuf>,
    #[arg(long)]
    pub dry_run: bool,
    #[command(flatten)]
    pub network: NetworkArgs,
}

#[derive(Subcommand)]
pub enum DeployMode {
    Batch(DeployBatchArgs),
}

#[derive(Args)]
pub struct DeployBatchArgs {
    pub inputs: Vec<PathBuf>,
    #[arg(long, default_value = "triton")]
    pub vm: String,
    #[arg(long, default_value = "release")]
    pub profile: String,
    #[arg(long)]
    pub dry_run: bool,
    #[arg(long, default_value = "4")]
    pub max_parallel: usize,
    #[command(flatten)]
    pub network: NetworkArgs,
}

pub fn cmd_deploy(args: DeployArgs) {
    let (state, _rpc_port) = args.network.resolve().unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });
    match args.mode {
        Some(DeployMode::Batch(batch_args)) => cmd_deploy_batch(batch_args),
        None => {
            let input = match args.input {
                Some(p) => p,
                None => {
                    eprintln!("error: no input file specified");
                    process::exit(1);
                }
            };
            cmd_deploy_single(
                input,
                &args.vm,
                state.union,
                state.name,
                &args.profile,
                args.proof,
                args.dry_run,
            );
        }
    }
}

fn cmd_deploy_single(
    input: PathBuf,
    vm: &str,
    union: &str,
    state: &str,
    profile: &str,
    proof_path: Option<PathBuf>,
    dry_run: bool,
) {
    let bundle = match compile_source(&input, vm, profile) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let proof_data = if let Some(ref pp) = proof_path {
        match load_proof_data(pp) {
            Ok(p) => Some(p),
            Err(e) => {
                eprintln!("error: cannot load proof: {}", e);
                process::exit(1);
            }
        }
    } else {
        None
    };
    let digest = trident::hash::content_hash_bytes(bundle.assembly.as_bytes());
    let digest_hex = trident::hash::ContentHash(digest).to_hex();
    if dry_run {
        eprintln!("Dry run — would deploy:");
        eprintln!("  Program : {}", bundle.name);
        eprintln!("  Union   : {}", union);
        eprintln!("  State   : {}", state);
        eprintln!("  Digest  : {}", digest_hex);
        eprintln!(
            "  Proof   : {}",
            if proof_path.is_some() {
                "attached"
            } else {
                "none"
            }
        );
        return;
    }
    let warrior = Warrior::new();
    match warrior.deploy(&bundle, proof_data.as_ref()) {
        Ok(result) => println!("{}", result),
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_deploy_batch(args: DeployBatchArgs) {
    if args.inputs.is_empty() {
        eprintln!("error: no input files specified");
        process::exit(1);
    }
    let (state, _rpc_port) = args.network.resolve().unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });
    let vm = args.vm.clone();
    let profile = args.profile.clone();
    let dry_run = args.dry_run;
    let union = state.union;
    let state_name = state.name;
    let count = args.inputs.len();
    eprintln!(
        "Deploying {} programs to {}/{} (max {} parallel)...",
        count, union, state_name, args.max_parallel
    );
    let results = batch::run_batch(args.inputs, args.max_parallel, |path| {
        let bundle = compile_source(&path, &vm, &profile)?;
        let digest = trident::hash::content_hash_bytes(bundle.assembly.as_bytes());
        let digest_hex = trident::hash::ContentHash(digest).to_hex();
        if dry_run {
            return Ok::<String, TrishaError>(format!("dry-run: {} ({})", bundle.name, digest_hex));
        }
        let warrior = Warrior::new();
        warrior.deploy(&bundle, None).map_err(TrishaError::Deploy)
    });
    let mut failures = 0;
    for r in &results {
        match &r.result {
            Ok(msg) => eprintln!("  [{}] {} ({} ms)", r.index, msg, r.elapsed_ms),
            Err(e) => {
                eprintln!("  [{}] FAIL: {}", r.index, e);
                failures += 1;
            }
        }
    }
    eprintln!("{}/{} deployed", count - failures, count);
    if failures > 0 {
        process::exit(1);
    }
}
