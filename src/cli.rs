use std::path::PathBuf;
use std::process;

use clap::{Args, Parser, Subcommand};

use crate::compile::compile_source;
use crate::proof_file::{ClaimSection, DataSection, ProofFile, ProofMeta};
use crate::warrior::TrishaWarrior;
use trident::runtime::{Deployer, ProgramInput, ProofData, Prover, Runner, Verifier};

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
    /// Prove multiple programs in parallel
    ProveBatch(ProveBatchArgs),
    /// Verify a STARK proof
    Verify(VerifyArgs),
    /// Deploy a program (package artifact + optional on-chain)
    Deploy(DeployArgs),
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
pub struct ProveBatchArgs {
    /// Input .tri files
    pub inputs: Vec<PathBuf>,
    /// Target VM (default: triton)
    #[arg(long, default_value = "triton")]
    pub target: String,
    /// Compilation profile
    #[arg(long, default_value = "release")]
    pub profile: String,
    /// Output directory for proof files
    #[arg(long, default_value = ".")]
    pub output: PathBuf,
    /// Maximum parallel proving jobs
    #[arg(long, default_value = "4")]
    pub max_parallel: usize,
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

#[derive(Args)]
pub struct DeployArgs {
    /// Input .tri file
    pub input: PathBuf,
    /// Target (default: neptune)
    #[arg(long, default_value = "neptune")]
    pub target: String,
    /// Chain state (mainnet, testnet)
    #[arg(long, default_value = "testnet")]
    pub state: String,
    /// Compilation profile
    #[arg(long, default_value = "release")]
    pub profile: String,
    /// Path to proof file to attach
    #[arg(long)]
    pub proof: Option<PathBuf>,
    /// Show what would happen without deploying
    #[arg(long)]
    pub dry_run: bool,
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

    let start = std::time::Instant::now();
    let warrior = TrishaWarrior::new();
    let proof_data = match warrior.prove(&bundle, &input) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let proving_time_ms = start.elapsed().as_millis() as u64;

    let output_path = args.output.unwrap_or_else(|| {
        let stem = args.input.file_stem().unwrap_or_default().to_string_lossy();
        PathBuf::from(format!("{}.proof.toml", stem))
    });

    let proof_file = ProofFile {
        proof: ProofMeta {
            format: proof_data.format.clone(),
            program_name: bundle.name.clone(),
            cycle_count: 0,
            padded_height: 0,
            proving_time_ms,
        },
        claim: ClaimSection {
            program_hash: proof_data.claim.program_hash.clone(),
            public_input: proof_data.claim.public_input.clone(),
            public_output: proof_data.claim.public_output.clone(),
        },
        data: DataSection {
            proof: ProofFile::encode_proof_bytes(&proof_data.proof_bytes),
        },
    };

    if let Err(e) = proof_file.save(&output_path) {
        eprintln!("error: {}", e);
        process::exit(1);
    }

    for val in &proof_data.claim.public_output {
        println!("{}", val);
    }
    eprintln!(
        "Proof written to {} ({} ms)",
        output_path.display(),
        proving_time_ms
    );
}

pub fn cmd_prove_batch(args: ProveBatchArgs) {
    if args.inputs.is_empty() {
        eprintln!("error: no input files specified");
        process::exit(1);
    }

    // Create output directory if needed
    if let Err(e) = std::fs::create_dir_all(&args.output) {
        eprintln!("error: cannot create output directory: {}", e);
        process::exit(1);
    }

    let jobs =
        match crate::batch::build_jobs(&args.inputs, &args.target, &args.profile, &args.output) {
            Ok(j) => j,
            Err(e) => {
                eprintln!("error: {}", e);
                process::exit(1);
            }
        };

    let count = jobs.len();
    eprintln!(
        "Proving {} programs (max {} parallel)...",
        count, args.max_parallel
    );

    let results = crate::batch::prove_batch(jobs, args.max_parallel);

    let mut failures = 0;
    for result in &results {
        match &result.proof_data {
            Ok(_) => {
                eprintln!(
                    "  {} ({} ms)",
                    result.output_path.display(),
                    result.proving_time_ms
                );
            }
            Err(e) => {
                eprintln!("  FAIL {}: {}", result.output_path.display(), e);
                failures += 1;
            }
        }
    }

    eprintln!("{}/{} proofs generated", count - failures, count);
    if failures > 0 {
        process::exit(1);
    }
}

pub fn cmd_verify(args: VerifyArgs) {
    let proof_file = match ProofFile::load(&args.proof) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };

    let proof_bytes = match ProofFile::decode_proof_bytes(&proof_file.data.proof) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };

    let proof_data = ProofData {
        claim: trident::field::proof::Claim {
            program_hash: proof_file.claim.program_hash,
            public_input: proof_file.claim.public_input,
            public_output: proof_file.claim.public_output,
        },
        proof_bytes,
        format: proof_file.proof.format,
    };

    let warrior = TrishaWarrior::new();
    match warrior.verify(&proof_data) {
        Ok(true) => {
            println!("Verification: PASS");
        }
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

pub fn cmd_deploy(args: DeployArgs) {
    let bundle = match compile_source(&args.input, &args.target, &args.profile) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };

    // Load proof if provided
    let proof_data = if let Some(ref proof_path) = args.proof {
        let pf = match ProofFile::load(proof_path) {
            Ok(p) => p,
            Err(e) => {
                eprintln!("error: cannot load proof: {}", e);
                process::exit(1);
            }
        };
        let proof_bytes = match ProofFile::decode_proof_bytes(&pf.data.proof) {
            Ok(b) => b,
            Err(e) => {
                eprintln!("error: {}", e);
                process::exit(1);
            }
        };
        Some(ProofData {
            claim: trident::field::proof::Claim {
                program_hash: pf.claim.program_hash,
                public_input: pf.claim.public_input,
                public_output: pf.claim.public_output,
            },
            proof_bytes,
            format: pf.proof.format,
        })
    } else {
        None
    };

    // Compute program digest for display
    let digest = trident::poseidon2::hash_bytes(bundle.assembly.as_bytes());
    let digest_hex = trident::hash::ContentHash(digest).to_hex();

    if args.dry_run {
        eprintln!("Dry run — would deploy:");
        eprintln!("  Program:  {}", bundle.name);
        eprintln!("  Target:   {}", args.target);
        eprintln!("  State:    {}", args.state);
        eprintln!("  Digest:   {}", digest_hex);
        eprintln!(
            "  Proof:    {}",
            if args.proof.is_some() {
                "attached"
            } else {
                "none"
            }
        );
        return;
    }

    let warrior = TrishaWarrior::new();
    match warrior.deploy(&bundle, proof_data.as_ref()) {
        Ok(result) => {
            println!("{}", result);
        }
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}
