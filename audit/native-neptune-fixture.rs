//! Test-only Neptune process fixture. Never opens a network socket or a real wallet.
use std::{env, fs, io::{self, Read, Write}, path::PathBuf};

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut log = fs::OpenOptions::new().create(true).append(true)
        .open(env::var_os("WLOG").expect("isolated fixture log")).unwrap();
    writeln!(log, "{}|", args.join("|")).unwrap();
    let mut offset = 0;
    let mut data = PathBuf::from(env::var_os("FIXTURE_DATA").unwrap());
    while matches!(args.get(offset).map(String::as_str), Some("--data-dir" | "--port")) {
        if args[offset] == "--data-dir" { data = PathBuf::from(&args[offset + 1]); }
        offset += 2;
    }
    let command = args[offset].as_str();
    let tail = &args[offset + 1..];
    let network = tail.windows(2).find(|v| v[0] == "--network")
        .map(|v| v[1].as_str()).unwrap_or("testnet-0");
    let wallet = env::var_os("WALLET_PATH").map(PathBuf::from)
        .unwrap_or_else(|| data.join(network).join("wallet/wallet.dat"));
    if env::var("NODE_REPLY").as_deref() == Ok("offline") {
        println!("This command requires a connection to `neptune-core`, but that connection could not be established. Is `neptune-core` running?");
        return;
    }
    match command {
        "network" => println!("{}", env::var("NODE_NETWORK").unwrap_or("testnet-0".into())),
        "block-height" | "mempool-tx-count" => {
            if env::var("NODE_REPLY").as_deref() == Ok("malformed") { println!("not-an-integer"); }
            else { println!("{}", if command == "block-height" {123} else {7}); }
        }
        "peer-info" => println!("peer fixture"),
        "get-derivation-index" => println!("{}", env::var("LAST_INDEX").unwrap_or("2".into())),
        "nth-receiving-address" => println!("mock-address-{}", tail[0]),
        "next-receiving-address" => println!("mock-next-address"),
        "which-wallet" => { if wallet.is_file() { println!("{}", wallet.display()); } }
        "generate-wallet" | "import-seed-phrase" => {
            if command == "import-seed-phrase" {
                let mut private = String::new();
                io::stdin().read_to_string(&mut private).unwrap();
            }
            if env::var("FAIL_ZERO").as_deref() == Ok("1") {
                println!("Failed to import seed phrase."); return;
            }
            fs::create_dir_all(wallet.parent().unwrap()).unwrap();
            fs::write(wallet, "test fixture without funds").unwrap();
            println!("New wallet generated.");
        }
        _ => std::process::exit(9),
    }
}
