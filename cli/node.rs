use std::process;

use clap::{Args, Subcommand};

use crate::neptune::NeptuneClient;
use crate::NetworkArgs;

#[derive(Args)]
pub struct NodeArgs {
    #[command(subcommand)]
    pub cmd: NodeCmd,
    #[command(flatten)]
    pub network: NetworkArgs,
}

#[derive(Subcommand)]
pub enum NodeCmd {
    /// Show block height, peers, and mempool
    Status,
}

pub fn cmd_node(args: NodeArgs) {
    let (state, rpc_port) = args.network.resolve().unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });
    match args.cmd {
        NodeCmd::Status => cmd_node_status(rpc_port, state.display_name),
    }
}

fn cmd_node_status(rpc_port: u16, display_name: &str) {
    eprintln!("Network: {}", display_name);
    let client = NeptuneClient::new(rpc_port);

    let height = client.block_height().unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });

    let peers = client.peer_info().unwrap_or_else(|e| {
        eprintln!("warning: peer-info failed: {}", e);
        "(unavailable)".to_string()
    });

    let mempool = client
        .mempool_tx_count()
        .unwrap_or_else(|_| "?".to_string());

    println!("Block height : {}", height);
    println!("Mempool txs  : {}", mempool);
    println!("Peers        :");
    if peers.is_empty() || peers == "(unavailable)" {
        println!("  {}", peers);
    } else {
        for line in peers.lines() {
            println!("  {}", line);
        }
    }
}
