#[cfg(feature = "triton")]
mod batch;
#[cfg(feature = "triton")]
mod bench;
#[cfg(feature = "triton")]
mod build_cmd;
#[cfg(feature = "triton")]
mod compile;
#[cfg(feature = "triton")]
mod deploy;
mod error;
#[cfg(feature = "triton")]
mod input_file;
mod mine;
mod neptune;
mod neuron;
mod node;
mod platform_paths;
#[cfg(feature = "triton")]
mod policy_witness;
#[cfg(feature = "triton")]
mod proof_file;
#[cfg(feature = "triton")]
mod prove;
#[cfg(feature = "triton")]
mod run;
mod state;
mod state_cmd;
#[cfg(feature = "triton")]
mod test_cmd;
#[cfg(feature = "triton")]
mod verify;

use clap::{Args, Parser, Subcommand};

use crate::error::TrishaError;

#[cfg(feature = "triton")]
use crate::proof_file::ProofFile;
#[cfg(feature = "triton")]
use trident::runtime::{ProgramInput, ProofData};

#[derive(Parser)]
#[command(
    name = "trisha",
    version,
    about = "Triton VM warrior — execute, prove, verify, deploy"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    #[cfg(feature = "triton")]
    /// Export the embedded, versioned compiler package and runtime capabilities
    Describe {
        #[arg(long, default_value = "triton")]
        target: String,
    },
    #[cfg(feature = "triton")]
    /// Lower a Trident program to linked TASM (trident stops at TIR)
    Build(build_cmd::BuildArgs),
    #[cfg(feature = "triton")]
    /// Compare unchanged programs against independent reference vectors
    Bench(bench::BenchArgs),
    #[cfg(feature = "triton")]
    /// Execute a Trident program on Triton VM
    Run(run::RunArgs),
    #[cfg(feature = "triton")]
    /// Execute active Trident tests with isolated, bounded Triton machines
    Test(test_cmd::TestArgs),
    #[cfg(feature = "triton")]
    /// Generate a STARK proof of correct execution
    Prove(prove::ProveArgs),
    #[cfg(feature = "triton")]
    /// Verify a STARK proof
    Verify(verify::VerifyArgs),
    #[cfg(feature = "triton")]
    /// Prepare a private recursive witness for an explicit expected full claim
    Witness(input_file::WitnessArgs),
    #[cfg(feature = "triton")]
    /// Deploy a program (package artifact + optional on-chain)
    Deploy(deploy::DeployArgs),
    /// Search for a nonce satisfying a difficulty target
    Mine(mine::MineArgs),
    /// Neptune node status
    Node(node::NodeArgs),
    /// Neuron operations (balance, address, boxes, create, import, remove)
    Neuron(neuron::NeuronArgs),
    /// List and inspect known states
    State(state_cmd::StateArgs),
}

#[derive(Args, Clone)]
pub(crate) struct NetworkArgs {
    #[arg(long, default_value = "neptune")]
    pub union: String,
    #[arg(long)]
    pub state: Option<String>,
    #[arg(long)]
    pub rpc_port: Option<u16>,
}

impl NetworkArgs {
    pub fn resolve(&self) -> Result<(&'static state::State, u16), TrishaError> {
        let s = match self.state.as_deref() {
            Some(name) => state::resolve(&self.union, name)?,
            None => state::default_for_union(&self.union)?,
        };
        let port = self.rpc_port.unwrap_or(s.rpc_port);
        Ok((s, port))
    }
}

#[cfg(feature = "triton")]
pub(crate) fn require_target(target: &str) {
    if let Err(error) = trisha_rs::target::package(target) {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(feature = "triton")]
pub(crate) fn make_input(
    input_values: &Option<Vec<u64>>,
    secret: &Option<Vec<u64>>,
    digests: &Option<Vec<u64>>,
) -> ProgramInput {
    let digest_vals = digests.clone().unwrap_or_default();
    if digest_vals.len() % 5 != 0 {
        eprintln!("error: --digests requires a multiple of five field elements");
        std::process::exit(1);
    }
    if input_values
        .iter()
        .flatten()
        .chain(secret.iter().flatten())
        .chain(digest_vals.iter())
        .any(|&v| v >= 18_446_744_069_414_584_321)
    {
        eprintln!("error: inputs must be canonical Goldilocks field elements");
        std::process::exit(1);
    }

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

#[cfg(feature = "triton")]
pub(crate) fn make_input_from_file(
    input_values: &Option<Vec<u64>>,
    secret: &Option<Vec<u64>>,
    digests: &Option<Vec<u64>>,
    input_file: &Option<std::path::PathBuf>,
) -> ProgramInput {
    if let Some(path) = input_file {
        if input_values.is_some() || secret.is_some() || digests.is_some() {
            eprintln!("error: --input-file conflicts with explicit input flags");
            std::process::exit(1);
        }
        return input_file::load(path).unwrap_or_else(|error| {
            eprintln!("error: {error}");
            std::process::exit(1);
        });
    }
    make_input(input_values, secret, digests)
}

#[cfg(feature = "triton")]
pub(crate) fn bundle_from_tasm(
    tasm_path: &std::path::Path,
) -> Result<trident::runtime::ProgramBundle, TrishaError> {
    let assembly = std::fs::read_to_string(tasm_path)
        .map_err(|e| TrishaError::Io(format!("cannot read '{}': {}", tasm_path.display(), e)))?;
    let name = tasm_path
        .file_stem()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string();
    Ok(trident::runtime::ProgramBundle {
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
        // .tasm carries no state declaration; the bundle path that does is `trident build`
        reads_state: false,
    })
}

#[cfg(feature = "triton")]
pub(crate) fn load_proof_data(path: &std::path::Path) -> Result<ProofData, TrishaError> {
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

fn main() {
    let cli = Cli::parse();

    match cli.command {
        #[cfg(feature = "triton")]
        Command::Describe { target } => match trisha_rs::target::package(&target)
            .and_then(|package| serde_json::to_string(&package).map_err(|error| error.to_string()))
        {
            Ok(json) => println!("{json}"),
            Err(error) => {
                eprintln!("error: {error}");
                std::process::exit(1);
            }
        },
        #[cfg(feature = "triton")]
        Command::Bench(args) => {
            if let Err(e) = bench::cmd_bench(args) {
                eprintln!("error: {}", e);
                std::process::exit(1);
            }
        }
        #[cfg(feature = "triton")]
        Command::Build(args) => {
            if let Err(e) = build_cmd::cmd_build(args) {
                eprintln!("error: {}", e);
                std::process::exit(1);
            }
        }
        #[cfg(feature = "triton")]
        Command::Test(args) => test_cmd::cmd_test(args),
        #[cfg(feature = "triton")]
        Command::Run(args) => run::cmd_run(args),
        #[cfg(feature = "triton")]
        Command::Prove(args) => prove::cmd_prove(args),
        #[cfg(feature = "triton")]
        Command::Verify(args) => verify::cmd_verify(args),
        #[cfg(feature = "triton")]
        Command::Witness(args) => {
            if let Err(error) = input_file::cmd_witness(args) {
                eprintln!("error: {error}");
                std::process::exit(1);
            }
        }
        #[cfg(feature = "triton")]
        Command::Deploy(args) => deploy::cmd_deploy(args),
        Command::Mine(args) => mine::cmd_mine(args),
        Command::Node(args) => node::cmd_node(args),
        Command::Neuron(args) => neuron::cmd_neuron(args),
        Command::State(args) => state_cmd::cmd_state(args),
    }
}
