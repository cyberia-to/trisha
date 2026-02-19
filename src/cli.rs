use std::path::PathBuf;
use std::process;

use clap::{Args, Parser, Subcommand};

use trident::runtime::{
    Deployer, Guesser, ProgramBundle, ProgramInput, ProofData, Prover, Runner, Verifier,
};
use trisha::batch;
use trisha::compile::compile_source;
use trisha::error::TrishaError;
use trisha::proof_file::{ClaimSection, DataSection, ProofFile, ProofMeta};
use trisha::warrior::TrishaWarrior;

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
    /// Deploy a program (package artifact + optional on-chain)
    Deploy(DeployArgs),
    /// Search for a nonce satisfying a difficulty target
    Guess(GuessArgs),
}

// ---------------------------------------------------------------------------
// Shared arg groups
// ---------------------------------------------------------------------------

fn make_input(
    input_values: &Option<Vec<u64>>,
    secret: &Option<Vec<u64>>,
    digests: &Option<Vec<u64>>,
) -> ProgramInput {
    let digest_vals = digests.clone().unwrap_or_default();
    let parsed_digests: Vec<[u64; 5]> = digest_vals
        .chunks(5)
        .filter(|c| c.len() == 5)
        .map(|c| [c[0], c[1], c[2], c[3], c[4]])
        .collect();
    ProgramInput {
        public: input_values.clone().unwrap_or_default(),
        secret: secret.clone().unwrap_or_default(),
        digests: parsed_digests,
    }
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

#[derive(Args)]
#[command(args_conflicts_with_subcommands = true)]
pub struct RunArgs {
    #[command(subcommand)]
    pub mode: Option<RunMode>,

    /// Input .tri file
    pub input: Option<PathBuf>,
    /// Raw TASM file (skip compilation, execute directly)
    #[arg(long)]
    pub tasm: Option<PathBuf>,
    /// Target VM
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
    /// Nondeterministic digests for merkle_step (comma-separated, 5 per digest)
    #[arg(long, value_delimiter = ',')]
    pub digests: Option<Vec<u64>>,
}

#[derive(Subcommand)]
pub enum RunMode {
    /// Run multiple programs in parallel
    Batch(RunBatchArgs),
}

#[derive(Args)]
pub struct RunBatchArgs {
    /// Input .tri files
    pub inputs: Vec<PathBuf>,
    /// Target VM
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
    /// Nondeterministic digests for merkle_step (comma-separated, 5 per digest)
    #[arg(long, value_delimiter = ',')]
    pub digests: Option<Vec<u64>>,
    /// Maximum parallel jobs
    #[arg(long, default_value = "4")]
    pub max_parallel: usize,
}

pub fn cmd_run(args: RunArgs) {
    match args.mode {
        Some(RunMode::Batch(batch_args)) => cmd_run_batch(batch_args),
        None => {
            // --tasm flag: execute raw TASM directly (skip compilation)
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
    let warrior = TrishaWarrior::new();
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
    let warrior = TrishaWarrior::new();
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

/// Build a ProgramBundle from a raw .tasm file (no compilation step).
fn bundle_from_tasm(tasm_path: &std::path::Path) -> Result<ProgramBundle, TrishaError> {
    let assembly = std::fs::read_to_string(tasm_path)
        .map_err(|e| TrishaError::Io(format!("cannot read '{}': {}", tasm_path.display(), e)))?;
    let name = tasm_path
        .file_stem()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string();
    Ok(ProgramBundle {
        name,
        version: String::new(),
        target_vm: "triton".to_string(),
        target_os: None,
        assembly,
        entry_point: String::new(),
        functions: Vec::new(),
        cost: trident::runtime::artifact::BundleCost {
            table_values: Vec::new(),
            table_names: Vec::new(),
            padded_height: 0,
            estimated_proving_ns: 0,
        },
        source_hash: String::new(),
    })
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
        let warrior = TrishaWarrior::new();
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

// ---------------------------------------------------------------------------
// Prove
// ---------------------------------------------------------------------------

#[derive(Args)]
#[command(args_conflicts_with_subcommands = true)]
pub struct ProveArgs {
    #[command(subcommand)]
    pub mode: Option<ProveMode>,

    /// Input .tri file
    pub input: Option<PathBuf>,
    /// Raw TASM file (skip compilation, prove directly)
    #[arg(long)]
    pub tasm: Option<PathBuf>,
    /// Target VM
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
    /// Nondeterministic digests for merkle_step (comma-separated, 5 per digest)
    #[arg(long, value_delimiter = ',')]
    pub digests: Option<Vec<u64>>,
    /// Output path for proof file
    #[arg(long)]
    pub output: Option<PathBuf>,
}

#[derive(Subcommand)]
pub enum ProveMode {
    /// Prove multiple programs in parallel
    Batch(ProveBatchArgs),
}

#[derive(Args)]
pub struct ProveBatchArgs {
    /// Input .tri files
    pub inputs: Vec<PathBuf>,
    /// Target VM
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
    /// Nondeterministic digests for merkle_step (comma-separated, 5 per digest)
    #[arg(long, value_delimiter = ',')]
    pub digests: Option<Vec<u64>>,
    /// Output directory for proof files
    #[arg(long, default_value = ".")]
    pub output: PathBuf,
    /// Maximum parallel jobs
    #[arg(long, default_value = "4")]
    pub max_parallel: usize,
}

pub fn cmd_prove(args: ProveArgs) {
    match args.mode {
        Some(ProveMode::Batch(batch_args)) => cmd_prove_batch(batch_args),
        None => {
            // --tasm flag: prove raw TASM directly (skip compilation)
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
    let warrior = TrishaWarrior::new();
    let proof_data = match warrior.prove(&bundle, &pi) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let proving_time_ms = start.elapsed().as_millis() as u64;

    let output_path = output.unwrap_or_else(|| {
        let stem = input.file_stem().unwrap_or_default().to_string_lossy();
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
    let warrior = TrishaWarrior::new();
    let proof_data = match warrior.prove(&bundle, &pi) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let proving_time_ms = start.elapsed().as_millis() as u64;

    let output_path = output.unwrap_or_else(|| {
        let stem = tasm_path.file_stem().unwrap_or_default().to_string_lossy();
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
        let warrior = TrishaWarrior::new();
        let start = std::time::Instant::now();
        let proof_data = warrior.prove(&bundle, &pi).map_err(TrishaError::Prove)?;
        let proving_time_ms = start.elapsed().as_millis() as u64;

        let stem = path.file_stem().unwrap_or_default().to_string_lossy();
        let out_path = output_dir.join(format!("{}.proof.toml", stem));

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

// ---------------------------------------------------------------------------
// Verify
// ---------------------------------------------------------------------------

#[derive(Args)]
#[command(args_conflicts_with_subcommands = true)]
pub struct VerifyArgs {
    #[command(subcommand)]
    pub mode: Option<VerifyMode>,

    /// Path to the proof file (.proof.toml)
    pub proof: Option<PathBuf>,
    /// Target VM
    #[arg(long, default_value = "triton")]
    pub target: String,
}

#[derive(Subcommand)]
pub enum VerifyMode {
    /// Verify multiple proofs in parallel
    Batch(VerifyBatchArgs),
}

#[derive(Args)]
pub struct VerifyBatchArgs {
    /// Proof files (.proof.toml)
    pub proofs: Vec<PathBuf>,
    /// Target VM
    #[arg(long, default_value = "triton")]
    pub target: String,
    /// Maximum parallel jobs
    #[arg(long, default_value = "4")]
    pub max_parallel: usize,
}

pub fn cmd_verify(args: VerifyArgs) {
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

fn load_proof_data(path: &std::path::Path) -> Result<ProofData, TrishaError> {
    let proof_file = ProofFile::load(path)?;
    let proof_bytes = ProofFile::decode_proof_bytes(&proof_file.data.proof)?;
    Ok(ProofData {
        claim: trident::field::proof::Claim {
            program_hash: proof_file.claim.program_hash,
            public_input: proof_file.claim.public_input,
            public_output: proof_file.claim.public_output,
        },
        proof_bytes,
        format: proof_file.proof.format,
    })
}

fn cmd_verify_single(proof_path: PathBuf) {
    let proof_data = match load_proof_data(&proof_path) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };

    let warrior = TrishaWarrior::new();
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
        let warrior = TrishaWarrior::new();
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

// ---------------------------------------------------------------------------
// Deploy
// ---------------------------------------------------------------------------

#[derive(Args)]
#[command(args_conflicts_with_subcommands = true)]
pub struct DeployArgs {
    #[command(subcommand)]
    pub mode: Option<DeployMode>,

    /// Input .tri file
    pub input: Option<PathBuf>,
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

#[derive(Subcommand)]
pub enum DeployMode {
    /// Deploy multiple programs in parallel
    Batch(DeployBatchArgs),
}

#[derive(Args)]
pub struct DeployBatchArgs {
    /// Input .tri files
    pub inputs: Vec<PathBuf>,
    /// Target (default: neptune)
    #[arg(long, default_value = "neptune")]
    pub target: String,
    /// Chain state (mainnet, testnet)
    #[arg(long, default_value = "testnet")]
    pub state: String,
    /// Compilation profile
    #[arg(long, default_value = "release")]
    pub profile: String,
    /// Show what would happen without deploying
    #[arg(long)]
    pub dry_run: bool,
    /// Maximum parallel jobs
    #[arg(long, default_value = "4")]
    pub max_parallel: usize,
}

pub fn cmd_deploy(args: DeployArgs) {
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
                &args.target,
                &args.state,
                &args.profile,
                args.proof,
                args.dry_run,
            );
        }
    }
}

fn cmd_deploy_single(
    input: PathBuf,
    target: &str,
    state: &str,
    profile: &str,
    proof_path: Option<PathBuf>,
    dry_run: bool,
) {
    let bundle = match compile_source(&input, target, profile) {
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

    let digest = trident::poseidon2::hash_bytes(bundle.assembly.as_bytes());
    let digest_hex = trident::hash::ContentHash(digest).to_hex();

    if dry_run {
        eprintln!("Dry run — would deploy:");
        eprintln!("  Program:  {}", bundle.name);
        eprintln!("  Target:   {}", target);
        eprintln!("  State:    {}", state);
        eprintln!("  Digest:   {}", digest_hex);
        eprintln!(
            "  Proof:    {}",
            if proof_path.is_some() {
                "attached"
            } else {
                "none"
            }
        );
        return;
    }

    let warrior = TrishaWarrior::new();
    match warrior.deploy(&bundle, proof_data.as_ref()) {
        Ok(result) => println!("{}", result),
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

// ---------------------------------------------------------------------------
// Guess
// ---------------------------------------------------------------------------

#[derive(Args)]
pub struct GuessArgs {
    /// Input .tri file
    pub input: PathBuf,
    /// Target VM
    #[arg(long, default_value = "triton")]
    pub target: String,
    /// Compilation profile
    #[arg(long, default_value = "release")]
    pub profile: String,
    /// Difficulty target (digest[0] must be less than this value)
    #[arg(long, default_value = "1000000")]
    pub difficulty: u64,
    /// Maximum nonces to try before giving up
    #[arg(long, default_value = "100000000")]
    pub max_attempts: u64,
}

pub fn cmd_guess(args: GuessArgs) {
    let bundle = match compile_source(&args.input, &args.target, &args.profile) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };

    let pi = ProgramInput::default();
    let warrior = TrishaWarrior::new();
    match warrior.guess(&bundle, &pi, args.difficulty, args.max_attempts) {
        Ok(result) => {
            println!("nonce:    {}", result.nonce);
            println!(
                "digest:   {}",
                result
                    .digest
                    .iter()
                    .map(|d| d.to_string())
                    .collect::<Vec<_>>()
                    .join(":")
            );
            println!("attempts: {}", result.attempts);
        }
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

    let target = args.target.clone();
    let profile = args.profile.clone();
    let dry_run = args.dry_run;
    let count = args.inputs.len();
    eprintln!(
        "Deploying {} programs (max {} parallel)...",
        count, args.max_parallel
    );

    let results = batch::run_batch(args.inputs, args.max_parallel, |path| {
        let bundle = compile_source(&path, &target, &profile)?;

        let digest = trident::poseidon2::hash_bytes(bundle.assembly.as_bytes());
        let digest_hex = trident::hash::ContentHash(digest).to_hex();

        if dry_run {
            return Ok::<String, TrishaError>(format!("dry-run: {} ({})", bundle.name, digest_hex));
        }

        let warrior = TrishaWarrior::new();
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
