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
#[cfg(feature = "triton")]
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
    if [args.bench_secs, args.bench_gpu_secs]
        .iter()
        .any(|s| !s.is_finite() || !(0.0..=86400.0).contains(s))
    {
        eprintln!("benchmark duration must be finite and between 0 and 86400 seconds");
        process::exit(1);
    }
    if args.bench_secs > 0.0 {
        neptune_mine::benchmark_hardfork_beta(args.bench_secs);
        return;
    }
    #[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
    if args.bench_gpu_secs > 0.0 {
        neptune_mine::benchmark_gpu(args.bench_gpu_secs);
        return;
    }
    #[cfg(not(all(feature = "gpu", target_os = "macos", target_arch = "aarch64")))]
    if args.bench_gpu_secs > 0.0 {
        eprintln!("GPU benchmark requires Apple Silicon macOS and --features gpu");
        process::exit(1);
    }
    if args.neptune {
        cmd_mine_neptune(args);
    } else {
        #[cfg(feature = "triton")]
        cmd_mine_triton(args);
        #[cfg(not(feature = "triton"))]
        {
            eprintln!(
                "error: Triton mining requires the 'triton' feature; use --neptune for Neptune PoW"
            );
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

#[path = "mining_session.rs"]
mod mining_session;

fn cmd_mine_neptune(args: MineArgs) {
    if let Err(error) = run_neptune(args) {
        eprintln!("error: {error}");
        process::exit(1);
    }
}
fn run_neptune(args: MineArgs) -> Result<(), String> {
    let (state, port) = args.network.resolve().map_err(|e| e.to_string())?;
    let client = NeptuneClient::mining_client(port, args.http_rpc_port, state.network_flag);
    let address = match args.guesser_address {
        Some(a) => a,
        None => client
            .next_address("generation")
            .map_err(|e| e.to_string())?,
    };
    #[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
    let mut gpu = if args.backend == "auto" || args.backend == "gpu" {
        trisha_honeycrisp::aruminium_mine::AruMine::try_new()
    } else {
        None
    };
    #[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
    let gpu_available = gpu.is_some();
    #[cfg(not(all(feature = "gpu", target_os = "macos", target_arch = "aarch64")))]
    let gpu_available = false;
    let backend = mining_session::backend(&args.backend, gpu_available)?;
    let mut legacy: Option<(Digest, bool, GuesserBuffer)> = None;
    let pow = mining_session::run(
        state.network_flag,
        args.max_attempts,
        || {
            client
                .get_block_template(&address)
                .map_err(|e| e.to_string())
        },
        |template, start, count| {
            if template.rule.fast() {
                #[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
                if let Some(ref mut miner) = gpu {
                    return Ok(neptune_mine::mine_gpu_range(
                        miner,
                        template.path,
                        &template.mast,
                        template.target,
                        start,
                        count,
                        backend == mining_session::Backend::Combined,
                    ));
                }
                Ok(neptune_mine::mine_cpu_range(
                    template.path,
                    &template.mast,
                    template.target,
                    start,
                    count,
                ))
            } else {
                if backend == mining_session::Backend::Gpu {
                    return Err(
                        "legacy memory-hard mining is a CPU backend; choose cpu/honeycrisp/auto"
                            .into(),
                    );
                }
                let reversed = template.rule != mining_session::Rule::Reboot;
                let prefix = if reversed {
                    template.parent
                } else {
                    template.mast.commit()
                };
                if !legacy
                    .as_ref()
                    .is_some_and(|(p, r, _)| *p == prefix && *r == reversed)
                {
                    eprintln!(
                        "Legacy {:?}: building explicit consensus buffer (~43 GB peak)",
                        template.rule
                    );
                    drop(legacy.take()); // free the previous buffer before allocating another
                    legacy = Some((
                        prefix,
                        reversed,
                        GuesserBuffer::build_legacy(prefix, reversed),
                    ));
                }
                Ok(neptune_mine::mine_legacy_range(
                    &legacy.as_ref().unwrap().2,
                    &template.mast,
                    template.target,
                    start,
                    count,
                ))
            }
        },
        |block, pow| client.submit_block(block, pow).map_err(|e| e.to_string()),
    )?;
    println!(
        "accepted\nnonce: {}\nroot: {}",
        pow.nonce.to_hex(),
        pow.root.to_hex()
    );
    Ok(())
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
    let obj = val.ok_or_else(|| "pow_mast_paths missing".to_string())?;
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
