use std::process;

use std::path::PathBuf;

use clap::Args;
use serde_json::Value;
#[cfg(feature = "triton")]
use trident::runtime::{Guesser, ProgramInput};
use trisha_honeycrisp::neptune_mine::{self, GuesserBuffer, NeptunePow, PowMastPaths, HEIGHT};
use trisha_honeycrisp::Digest;
#[cfg(feature = "triton")]
use trisha_honeycrisp::Warrior as HoneycriAppleWarrior;
#[cfg(all(feature = "triton", feature = "trisha-rs"))]
use trisha_rs::Warrior as CpuWarrior;
#[cfg(feature = "trisha-wgpu")]
use trisha_wgpu::Warrior as GpuWarrior;

#[cfg(feature = "triton")]
use crate::compile::compile_source;
use crate::neptune::NeptuneClient;

#[derive(Args)]
pub struct MineArgs {
    /// Trident source file (Triton mode); omit when using --neptune
    pub input: Option<PathBuf>,
    #[arg(long, default_value = "triton")]
    pub target: String,
    #[arg(long, default_value = "release")]
    pub profile: String,
    /// Difficulty for Triton mining: nonce valid when hash[0] < difficulty
    #[arg(long, default_value = "1000000")]
    pub difficulty: u64,
    #[arg(long, default_value = "10000000000")]
    pub max_attempts: u64,
    #[arg(long, default_value = "auto", value_parser = ["gpu", "honeycrisp", "cpu", "auto"])]
    pub backend: String,
    /// Mine Neptune PoW using the running node (ignores input file)
    #[arg(long)]
    pub neptune: bool,
    /// Benchmark CPU HardforkBeta hashrate for N seconds (no node required)
    #[arg(long, default_value = "0")]
    pub bench_secs: f64,
    /// Benchmark GPU (aruminium Metal) hashrate for N seconds (no node required)
    #[arg(long, default_value = "0")]
    pub bench_gpu_secs: f64,
    /// Guesser reward address (for --neptune; uses neuron address if omitted)
    #[arg(long)]
    pub guesser_address: Option<String>,
    /// HTTP JSON-RPC port (for --neptune; neptune-core --listen-rpc default: 9797)
    #[arg(long, default_value = "9797")]
    pub http_rpc_port: u16,
    #[command(flatten)]
    pub network: crate::NetworkArgs,
}

pub fn cmd_mine(args: MineArgs) {
    if args.bench_secs > 0.0 {
        neptune_mine::benchmark_hardfork_beta(args.bench_secs);
        return;
    }
    #[cfg(feature = "gpu")]
    if args.bench_gpu_secs > 0.0 {
        neptune_mine::benchmark_gpu(args.bench_gpu_secs);
        return;
    }
    #[cfg(not(feature = "gpu"))]
    if args.bench_gpu_secs > 0.0 {
        eprintln!("GPU benchmark requires --features gpu");
        process::exit(1);
    }
    if args.neptune {
        cmd_mine_neptune(args);
    } else {
        #[cfg(feature = "triton")]
        cmd_mine_triton(args);
        #[cfg(not(feature = "triton"))]
        {
            eprintln!("error: Triton mining requires the 'triton' feature; use --neptune for Neptune PoW");
            process::exit(1);
        }
    }
}

// ── Triton mode ───────────────────────────────────────────────────────────────

#[cfg(feature = "triton")]
fn cmd_mine_triton(args: MineArgs) {
    let input = match args.input {
        Some(p) => p,
        None => {
            eprintln!("error: input file required (or use --neptune for Neptune PoW)");
            process::exit(1);
        }
    };

    let bundle = match compile_source(&input, &args.target, &args.profile) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };
    let pi = ProgramInput::default();

    let use_honeycrisp = {
        #[cfg(feature = "trisha-wgpu")]
        {
            args.backend == "honeycrisp"
                || (args.backend == "auto" && !GpuWarrior::new().gpu_available())
        }
        #[cfg(not(feature = "trisha-wgpu"))]
        {
            args.backend != "cpu"
        }
    };

    let result = if args.backend == "cpu" {
        CpuWarrior::new().guess(&bundle, &pi, args.difficulty, args.max_attempts)
    } else if use_honeycrisp {
        if args.backend != "honeycrisp" {
            eprintln!("GPU not available — using honeycrisp (multi-threaded CPU)");
        }
        HoneycriAppleWarrior::new().guess(&bundle, &pi, args.difficulty, args.max_attempts)
    } else {
        #[cfg(feature = "trisha-wgpu")]
        {
            GpuWarrior::new().guess(&bundle, &pi, args.difficulty, args.max_attempts)
        }
        #[cfg(not(feature = "trisha-wgpu"))]
        {
            CpuWarrior::new().guess(&bundle, &pi, args.difficulty, args.max_attempts)
        }
    };

    match result {
        Ok(r) => {
            println!("nonce:    {}", r.nonce);
            println!(
                "digest:   {}",
                r.digest
                    .iter()
                    .map(|d| d.to_string())
                    .collect::<Vec<_>>()
                    .join(":")
            );
            println!("attempts: {}", r.attempts);
        }
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

// ── Neptune mode ──────────────────────────────────────────────────────────────

fn cmd_mine_neptune(args: MineArgs) {
    let (_state, port) = match args.network.resolve() {
        Ok(r) => r,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };

    let client = NeptuneClient::with_http_port(port, args.http_rpc_port);

    let guesser_address = match args.guesser_address {
        Some(addr) => addr,
        None => match client.next_address("generation") {
            Ok(addr) => addr,
            Err(e) => {
                eprintln!(
                    "error: no --guesser-address and cannot get neuron address: {}",
                    e
                );
                process::exit(1);
            }
        },
    };
    eprintln!("Guesser address: {}", guesser_address);

    eprintln!("Fetching block template from node...");
    let template_resp = match client.get_block_template(&guesser_address) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    };

    let template_val = match template_resp.get("template") {
        Some(t) if !t.is_null() => t.clone(),
        _ => {
            eprintln!("error: node returned null template (still syncing or no peers?)");
            process::exit(1);
        }
    };

    let metadata = match template_val.get("metadata") {
        Some(m) => m.clone(),
        None => {
            eprintln!("error: template missing metadata");
            process::exit(1);
        }
    };

    let block = match template_val.get("block") {
        Some(b) => b.clone(),
        None => {
            eprintln!("error: template missing block");
            process::exit(1);
        }
    };

    let prev_block = match parse_digest(metadata.get("prev_block")) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("error parsing prev_block: {}", e);
            process::exit(1);
        }
    };

    let threshold = match parse_digest(metadata.get("threshold")) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("error parsing threshold: {}", e);
            process::exit(1);
        }
    };

    let mast_paths = match parse_pow_mast_paths(metadata.get("pow_mast_paths")) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error parsing pow_mast_paths: {}", e);
            process::exit(1);
        }
    };

    eprintln!("threshold: {}", threshold.to_hex());

    // HardforkBeta (active on mainnet since block 38000): no memory-hard PoW.
    // Validation only checks fast_mast_hash(pow) ≤ target; paths are not
    // Merkle-verified. The composer pre-encodes lustration_status into
    // pathA[27..28] and version into pathA[26]; we take pathA from the
    // template block header directly.
    let hardfork_beta = metadata.get("lustration_status").map_or(false, |v| !v.is_null());

    let pow = if hardfork_beta {
        eprintln!("HardforkBeta detected — no GuesserBuffer required.");
        let path_a = match parse_pow_path_a(&block) {
            Ok(p) => p,
            Err(e) => {
                eprintln!("error parsing block header pathA: {}", e);
                process::exit(1);
            }
        };

        eprintln!("Mining (max {} attempts)...", args.max_attempts);

        // Try GPU first (Apple Silicon Metal), fall back to CPU.
        // GPU path (Apple Silicon Metal, requires --features gpu).
        // Falls back to CPU if Metal unavailable or when gpu returns None.
        #[cfg(feature = "gpu")]
        let pow_opt = neptune_mine::mine_hardfork_beta_gpu(
            path_a, &mast_paths, threshold, args.max_attempts,
        ).or_else(|| neptune_mine::mine_hardfork_beta(
            path_a, &mast_paths, threshold, args.max_attempts,
        ));
        #[cfg(not(feature = "gpu"))]
        let pow_opt = neptune_mine::mine_hardfork_beta(
            path_a, &mast_paths, threshold, args.max_attempts,
        );

        match pow_opt {
            Some(p) => p,
            None => {
                eprintln!("No solution found within {} attempts", args.max_attempts);
                process::exit(1);
            }
        }
    } else {
        eprintln!("Building GuesserBuffer (2^29 leaves, ~32 GB)...");
        let buffer = GuesserBuffer::build(prev_block);

        eprintln!("Mining (max {} attempts)...", args.max_attempts);
        match neptune_mine::mine(&buffer, &mast_paths, threshold, args.max_attempts) {
            Some(p) => p,
            None => {
                eprintln!("No solution found within {} attempts", args.max_attempts);
                process::exit(1);
            }
        }
    };

    eprintln!("Solution found! Submitting to node...");

    let pow_json = neptune_pow_to_json(&pow);

    match client.submit_block(&block, &pow_json) {
        Ok(true) => {
            println!("accepted");
            println!("nonce: {}", pow.nonce.to_hex());
            println!("root:  {}", pow.root.to_hex());
        }
        Ok(false) => {
            eprintln!("block rejected by node");
            process::exit(1);
        }
        Err(e) => {
            eprintln!("error submitting block: {}", e);
            process::exit(1);
        }
    }
}

// ── helpers ───────────────────────────────────────────────────────────────────

fn parse_digest(val: Option<&Value>) -> Result<Digest, String> {
    let hex = val
        .and_then(|v| v.as_str())
        .ok_or_else(|| "expected hex string".to_string())?;
    Digest::try_from_hex(hex).map_err(|e| format!("{}", e))
}

fn parse_digest_array<const N: usize>(arr: Option<&Value>) -> Result<[Digest; N], String> {
    let items = arr
        .and_then(|v| v.as_array())
        .ok_or_else(|| format!("expected array of {} digests", N))?;
    if items.len() != N {
        return Err(format!("expected {} digests, got {}", N, items.len()));
    }
    let mut out = [Digest::default(); N];
    for (i, item) in items.iter().enumerate() {
        out[i] = parse_digest(Some(item))?;
    }
    Ok(out)
}

fn parse_pow_path_a(block: &Value) -> Result<[Digest; HEIGHT], String> {
    let path_a = block
        .get("kernel")
        .and_then(|k| k.get("header"))
        .and_then(|h| h.get("pow"))
        .and_then(|p| p.get("pathA"))
        .ok_or_else(|| "block.kernel.header.pow.pathA missing".to_string())?;
    parse_digest_array::<HEIGHT>(Some(path_a))
}

fn parse_pow_mast_paths(val: Option<&Value>) -> Result<PowMastPaths, String> {
    let obj = val
        .ok_or_else(|| "pow_mast_paths missing".to_string())?;
    Ok(PowMastPaths {
        pow: parse_digest_array::<{ neptune_mine::POW_PATH_LEN }>(obj.get("pow"))?,
        header: parse_digest_array::<{ neptune_mine::HEADER_PATH_LEN }>(obj.get("header"))?,
        kernel: parse_digest_array::<{ neptune_mine::KERNEL_PATH_LEN }>(obj.get("kernel"))?,
    })
}

fn neptune_pow_to_json(pow: &NeptunePow) -> Value {
    serde_json::json!({
        "root":  pow.root.to_hex(),
        "pathA": pow.path_a.iter().map(|d| d.to_hex()).collect::<Vec<_>>(),
        "pathB": pow.path_b.iter().map(|d| d.to_hex()).collect::<Vec<_>>(),
        "nonce": pow.nonce.to_hex(),
    })
}
