mod transaction;
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
    /// Construct a canonical custom-lock UTXO and its addition commitment.
    Output(transaction::OutputArgs),
    /// Validate a complete transaction and write its exact RPC request offline.
    Prepare(transaction::PrepareArgs),
    /// Submit an independently revalidated complete transaction to an explicit gateway.
    Submit(transaction::SubmitArgs),
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
    let (state, rpc_port) = args.network.resolve().unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });
    match args.mode {
        Some(DeployMode::Output(args)) => finish(transaction::output(args)),
        Some(DeployMode::Prepare(args)) => finish(transaction::prepare(args)),
        Some(DeployMode::Submit(args)) => finish(transaction::submit(args)),
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
                rpc_port,
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
    rpc_port: u16,
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
    let inspection =
        trisha_rs::deployment::inspect(&bundle, proof_data.as_ref()).unwrap_or_else(|error| {
            eprintln!("error: {error}");
            process::exit(1)
        });
    if dry_run {
        println!(
            "{}",
            inspection_json(&bundle, &inspection, union, state, rpc_port)
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
    let (state, rpc_port) = args.network.resolve().unwrap_or_else(|e| {
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
        "{} {} programs for {}/{} (max {} parallel)...",
        if dry_run { "Inspecting" } else { "Deploying" },
        count,
        union,
        state_name,
        args.max_parallel
    );
    let results = batch::run_batch(args.inputs, args.max_parallel, |path| {
        let bundle = compile_source(&path, &vm, &profile)?;
        let inspection =
            trisha_rs::deployment::inspect(&bundle, None).map_err(TrishaError::Deploy)?;
        if dry_run {
            return Ok::<String, TrishaError>(
                inspection_json(&bundle, &inspection, union, state_name, rpc_port).to_string(),
            );
        }
        let warrior = Warrior::new();
        warrior.deploy(&bundle, None).map_err(TrishaError::Deploy)
    });
    let mut failures = 0;
    for r in &results {
        match &r.result {
            Ok(msg) => println!("{msg}"),
            Err(e) => {
                eprintln!("  [{}] FAIL: {}", r.index, e);
                failures += 1;
            }
        }
    }
    eprintln!(
        "{}/{} {}",
        count - failures,
        count,
        if dry_run { "inspected" } else { "deployed" }
    );
    if failures > 0 {
        process::exit(1);
    }
}

fn inspection_json(
    bundle: &trident::runtime::ProgramBundle,
    inspection: &trisha_rs::deployment::ProgramInspection,
    union: &str,
    state: &str,
    rpc_port: u16,
) -> serde_json::Value {
    serde_json::json!({
        "format": "trisha-neptune-program-plan-v1",
        "operation": "inspect-program",
        "program": bundle.name,
        "source_hash": bundle.source_hash,
        "target_vm": bundle.target_vm,
        "target_os": bundle.target_os,
        "union": union,
        "state": state,
        "rpc_port": rpc_port,
        "lock_script_hash": inspection.lock_script_hash.map(|v| v.to_string()),
        "execution_proof_verified": inspection.execution_proof_verified,
        "submission_supported": false,
        "transaction": null,
    })
}

fn finish(result: Result<(), String>) {
    if let Err(error) = result {
        eprintln!("error: {error}");
        process::exit(1);
    }
}
