use std::path::PathBuf;
use std::process;

use clap::{Args, Parser, Subcommand};

use crate::compile::compile_source;
use crate::warrior::TrishaWarrior;
use trident::runtime::{ProgramInput, Prover, Runner, Verifier};

#[derive(Parser)]
#[command(
    name = "trisha",
    about = "Triton VM warrior — execute, prove, verify, deploy"
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand)]
pub enum Command {
    /// Execute a Trident program on Triton VM
    Run(RunArgs),
    /// Generate a STARK proof of correct execution
    Prove(ProveArgs),
    /// Verify a STARK proof
    Verify(VerifyArgs),
}

#[derive(Args)]
pub struct RunArgs {
    /// Input .tri file
    pub input: PathBuf,
    /// Target VM (default: triton)
    #[arg(long, default_value = "triton")]
    pub target: String,
    /// Compilation profile
    #[arg(long, default_value = "debug")]
    pub profile: String,
    /// Public input values (comma-separated)
    #[arg(long, value_delimiter = ',')]
    pub input_values: Option<Vec<u64>>,
    /// Secret input values (comma-separated)
    #[arg(long, value_delimiter = ',')]
    pub secret: Option<Vec<u64>>,
    /// Chain state name
    #[arg(long)]
    pub state: Option<String>,
}

#[derive(Args)]
pub struct ProveArgs {
    /// Input .tri file
    pub input: PathBuf,
    /// Target VM (default: triton)
    #[arg(long, default_value = "triton")]
    pub target: String,
    /// Compilation profile
    #[arg(long, default_value = "release")]
    pub profile: String,
    /// Public input values (comma-separated)
    #[arg(long, value_delimiter = ',')]
    pub input_values: Option<Vec<u64>>,
    /// Secret input values (comma-separated)
    #[arg(long, value_delimiter = ',')]
    pub secret: Option<Vec<u64>>,
    /// Output path for proof file
    #[arg(long)]
    pub output: Option<PathBuf>,
    /// Chain state name
    #[arg(long)]
    pub state: Option<String>,
}

#[derive(Args)]
pub struct VerifyArgs {
    /// Path to the proof file (.proof.toml)
    pub proof: PathBuf,
    /// Target VM (default: triton)
    #[arg(long, default_value = "triton")]
    pub target: String,
    /// Chain state name
    #[arg(long)]
    pub state: Option<String>,
}

pub fn cmd_run(args: RunArgs) {
    let bundle = match compile_source(&args.input, &args.target, &args.profile) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };

    let input = ProgramInput {
        public: args.input_values.unwrap_or_default(),
        secret: args.secret.unwrap_or_default(),
    };

    let warrior = TrishaWarrior::new();
    match warrior.run(&bundle, &input) {
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

pub fn cmd_prove(args: ProveArgs) {
    let bundle = match compile_source(&args.input, &args.target, &args.profile) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };

    let input = ProgramInput {
        public: args.input_values.unwrap_or_default(),
        secret: args.secret.unwrap_or_default(),
    };

    let warrior = TrishaWarrior::new();
    match warrior.prove(&bundle, &input) {
        Ok(_proof) => {
            eprintln!("Proof generated successfully");
            // TODO: write proof to output path
        }
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

pub fn cmd_verify(args: VerifyArgs) {
    // TODO: load proof from file
    let _ = args;
    eprintln!("error: verification not yet implemented");
    process::exit(1);
}
