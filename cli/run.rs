use std::path::PathBuf;
use std::process;

use clap::{Args, Subcommand};

use trident::runtime::Runner;
use trisha_rs::Warrior;

use crate::batch;
use crate::compile::compile_source;
use crate::error::TrishaError;

use super::{bundle_from_tasm, make_input};

#[derive(Args)]
#[command(args_conflicts_with_subcommands = true)]
pub struct RunArgs {
    #[command(subcommand)]
    pub mode: Option<RunMode>,

    pub input: Option<PathBuf>,
    #[arg(long)]
    pub tasm: Option<PathBuf>,
    #[arg(long, default_value = "triton")]
    pub target: String,
    #[arg(long, default_value = "debug")]
    pub profile: String,
    #[arg(long, value_delimiter = ',')]
    pub input_values: Option<Vec<u64>>,
    #[arg(long, value_delimiter = ',')]
    pub secret: Option<Vec<u64>>,
    #[arg(long, value_delimiter = ',')]
    pub digests: Option<Vec<u64>>,
}

#[derive(Subcommand)]
pub enum RunMode {
    Batch(RunBatchArgs),
}

#[derive(Args)]
pub struct RunBatchArgs {
    pub inputs: Vec<PathBuf>,
    #[arg(long, default_value = "triton")]
    pub target: String,
    #[arg(long, default_value = "debug")]
    pub profile: String,
    #[arg(long, value_delimiter = ',')]
    pub input_values: Option<Vec<u64>>,
    #[arg(long, value_delimiter = ',')]
    pub secret: Option<Vec<u64>>,
    #[arg(long, value_delimiter = ',')]
    pub digests: Option<Vec<u64>>,
    #[arg(long, default_value = "4")]
    pub max_parallel: usize,
}

pub fn cmd_run(args: RunArgs) {
    match args.mode {
        Some(RunMode::Batch(batch_args)) => cmd_run_batch(batch_args),
        None => {
            if let Some(ref tasm_path) = args.tasm {
                cmd_run_tasm(tasm_path, &args.input_values, &args.secret, &args.digests);
                return;
            }
            let input = match args.input {
                Some(p) => p,
                None => {
                    eprintln!("error: no input file specified");
                    process::exit(1);
                }
            };
            cmd_run_single(
                input,
                &args.target,
                &args.profile,
                &args.input_values,
                &args.secret,
                &args.digests,
            );
        }
    }
}

fn cmd_run_single(
    input: PathBuf,
    target: &str,
    profile: &str,
    input_values: &Option<Vec<u64>>,
    secret: &Option<Vec<u64>>,
    digests: &Option<Vec<u64>>,
) {
    let bundle = match compile_source(&input, target, profile) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let pi = make_input(input_values, secret, digests);
    let warrior = Warrior::new();
    match warrior.run(&bundle, &pi) {
        Ok(result) => {
            for val in &result.output {
                println!("{}", val);
            }
            eprintln!("Executed in {} cycles", result.cycle_count);
        }
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_run_tasm(
    tasm_path: &std::path::Path,
    input_values: &Option<Vec<u64>>,
    secret: &Option<Vec<u64>>,
    digests: &Option<Vec<u64>>,
) {
    let bundle = match bundle_from_tasm(tasm_path) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let pi = make_input(input_values, secret, digests);
    let warrior = Warrior::new();
    match warrior.run(&bundle, &pi) {
        Ok(result) => {
            for val in &result.output {
                println!("{}", val);
            }
            eprintln!("Executed in {} cycles", result.cycle_count);
        }
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_run_batch(args: RunBatchArgs) {
    if args.inputs.is_empty() {
        eprintln!("error: no input files specified");
        process::exit(1);
    }
    let target = args.target.clone();
    let profile = args.profile.clone();
    let input_values = args.input_values.clone();
    let secret = args.secret.clone();
    let digests = args.digests.clone();
    let count = args.inputs.len();
    eprintln!(
        "Running {} programs (max {} parallel)...",
        count, args.max_parallel
    );
    let results = batch::run_batch(args.inputs, args.max_parallel, |path| {
        let bundle = compile_source(&path, &target, &profile)?;
        let pi = make_input(&input_values, &secret, &digests);
        let warrior = Warrior::new();
        warrior.run(&bundle, &pi).map_err(TrishaError::Execute)
    });
    let mut failures = 0;
    for r in &results {
        match &r.result {
            Ok(exec) => {
                let output: Vec<String> = exec.output.iter().map(|v| v.to_string()).collect();
                eprintln!(
                    "  [{}] {} cycles, {} ms → {}",
                    r.index,
                    exec.cycle_count,
                    r.elapsed_ms,
                    output.join(", ")
                );
            }
            Err(e) => {
                eprintln!("  [{}] FAIL: {}", r.index, e);
                failures += 1;
            }
        }
    }
    eprintln!("{}/{} succeeded", count - failures, count);
    if failures > 0 {
        process::exit(1);
    }
}
