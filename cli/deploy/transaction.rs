use crate::{compile::compile_source, NetworkArgs};
use clap::Args;
use std::{io::Write, path::PathBuf};

#[derive(Args)]
pub struct PrepareArgs {
    pub input: PathBuf,
    #[arg(long)]
    pub intent: PathBuf,
    #[arg(long)]
    pub output: PathBuf,
    #[arg(long, default_value = "release")]
    pub profile: String,
    #[command(flatten)]
    pub network: NetworkArgs,
}
#[derive(Args)]
pub struct SubmitArgs {
    pub input: PathBuf,
    #[arg(long)]
    pub intent: PathBuf,
    #[arg(long)]
    pub endpoint: String,
    #[arg(long)]
    pub auth_file: PathBuf,
    #[arg(long, default_value = "release")]
    pub profile: String,
    #[command(flatten)]
    pub network: NetworkArgs,
}
fn validated(
    input: &std::path::Path,
    intent: &std::path::Path,
    profile: &str,
    network: &NetworkArgs,
) -> Result<trisha_neptune::PreparedTransaction, String> {
    let (state, _) = network.resolve().map_err(|e| e.to_string())?;
    if state.union != "neptune" {
        return Err("transaction submission requires Neptune".into());
    }
    let bundle = compile_source(input, "neptune", profile).map_err(|e| e.to_string())?;
    let intent = trisha_neptune::read_intent(intent)?;
    trisha_neptune::prepare(&bundle.assembly, &intent, state.name)
}
pub fn prepare(args: PrepareArgs) -> Result<(), String> {
    let prepared = validated(&args.input, &args.intent, &args.profile, &args.network)?;
    let bytes =
        serde_json::to_vec_pretty(&prepared).map_err(|_| "cannot encode prepared transaction")?;
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options
        .open(&args.output)
        .map_err(|_| "cannot create new preparation artifact")?;
    file.write_all(&bytes)
        .map_err(|_| "cannot write preparation artifact")?;
    println!(
        "{}",
        serde_json::json!({"operation":"prepare-complete-transaction","single_proof_verified":true,"submitted":false,"current_chain_admission_checked":false})
    );
    Ok(())
}
pub fn submit(args: SubmitArgs) -> Result<(), String> {
    let prepared = validated(&args.input, &args.intent, &args.profile, &args.network)?;
    let auth = trisha_neptune::transport::GatewayAuth::from_file(&args.auth_file)?;
    trisha_neptune::transport::submit(&prepared, &args.endpoint, &auth)?;
    println!(
        "{}",
        serde_json::json!({"operation":"submit-complete-transaction","gateway_accepted":true,"confirmed_on_chain":false,"kernel_digest":prepared.kernel_digest()})
    );
    Ok(())
}

#[derive(Args)]
pub struct OutputArgs {
    pub input: PathBuf,
    #[arg(long)]
    pub spec: PathBuf,
    #[arg(long)]
    pub output: PathBuf,
    #[arg(long, default_value = "release")]
    pub profile: String,
}
pub fn output(args: OutputArgs) -> Result<(), String> {
    let bundle =
        compile_source(&args.input, "neptune", &args.profile).map_err(|e| e.to_string())?;
    let spec = trisha_neptune::read_json(&args.spec)?;
    let output = trisha_neptune::construct_output(&bundle.assembly, spec)?;
    let bytes = serde_json::to_vec_pretty(&output).map_err(|_| "cannot encode output")?;
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    options
        .open(&args.output)
        .map_err(|_| "cannot create new output artifact")?
        .write_all(&bytes)
        .map_err(|_| "cannot write output artifact")?;
    println!(
        "{}",
        serde_json::json!({"operation":"construct-output","transaction_proved":false,"submitted":false})
    );
    Ok(())
}
