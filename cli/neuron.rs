use std::process;

use clap::{Args, Subcommand};

use crate::neptune::{load_hidden_addresses, save_hidden_addresses, NeptuneClient};
use crate::NetworkArgs;

#[derive(Args)]
pub struct NeuronArgs {
    #[command(subcommand)]
    pub cmd: NeuronCmd,
    #[command(flatten)]
    pub network: NetworkArgs,
}

#[derive(Subcommand)]
pub enum NeuronCmd {
    /// Show confirmed and unconfirmed balance
    Balance,
    /// Manage receiving addresses
    Address(NeuronAddressArgs),
    /// List all boxes (UTXOs)
    Boxes,
    /// Create a new neuron
    Create,
    /// Import a wallet through the upstream interactive seed dialog
    Import(NeuronImportArgs),
    /// Remove local neuron files
    Remove(NeuronRemoveArgs),
}

#[derive(Args)]
pub struct NeuronAddressArgs {
    #[command(subcommand)]
    pub cmd: NeuronAddressCmd,
}

#[derive(Subcommand)]
pub enum NeuronAddressCmd {
    /// Derive a new receiving address
    Add(NeuronAddressAddArgs),
    /// Hide an address from default listing
    Hide(NeuronAddressTargetArgs),
    /// Reveal a previously hidden address
    Show(NeuronAddressTargetArgs),
    /// List visible addresses (hidden filtered out unless --all)
    List(NeuronAddressListArgs),
}

#[derive(Args)]
pub struct NeuronAddressAddArgs {
    #[arg(long, default_value = "generation")]
    pub key_type: String,
    #[arg(long)]
    pub index: Option<u64>,
}

#[derive(Args)]
pub struct NeuronAddressTargetArgs {
    pub address: String,
}

#[derive(Args)]
pub struct NeuronAddressListArgs {
    #[arg(long)]
    pub all: bool,
    #[arg(long, default_value_t = 0)]
    pub start: u64,
    #[arg(long, default_value_t = 100, value_parser = clap::value_parser!(u16).range(1..=1000))]
    pub limit: u16,
}

#[derive(Args)]
pub struct NeuronImportArgs {
    #[arg(hide = true)]
    pub words: Vec<String>,
}

#[derive(Args)]
pub struct NeuronRemoveArgs {
    #[arg(long)]
    pub confirm: bool,
}

pub fn cmd_neuron(args: NeuronArgs) {
    let (state, rpc_port) = args.network.resolve().unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });
    match args.cmd {
        NeuronCmd::Balance => {
            cmd_neuron_balance(rpc_port, state.network_flag, state.currency_symbol)
        }
        NeuronCmd::Address(a) => cmd_neuron_address(rpc_port, state.network_flag, a),
        NeuronCmd::Boxes => cmd_neuron_boxes(rpc_port, state.network_flag),
        NeuronCmd::Create => cmd_neuron_create(rpc_port, state.network_flag, false),
        NeuronCmd::Import(a) => {
            if !a.words.is_empty() {
                eprintln!(
                    "error: seed words must be entered only in the interactive upstream dialog; run neuron import without positional arguments"
                );
                process::exit(1);
            }
            cmd_neuron_create(rpc_port, state.network_flag, true)
        }
        NeuronCmd::Remove(a) => cmd_neuron_remove(rpc_port, state.network_flag, a.confirm),
    }
}

fn cmd_neuron_balance(rpc_port: u16, network: &str, currency: &str) {
    let client = NeptuneClient::for_network(rpc_port, network);

    let confirmed = client.confirmed_balance().unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });

    let unconfirmed = client
        .unconfirmed_balance()
        .unwrap_or_else(|_| "(unavailable)".to_string());

    println!("Confirmed   : {} {}", confirmed, currency);
    println!("Unconfirmed : {} {}", unconfirmed, currency);
}

fn cmd_neuron_address(rpc_port: u16, network: &str, args: NeuronAddressArgs) {
    match args.cmd {
        NeuronAddressCmd::Add(a) => cmd_address_add(rpc_port, network, a),
        NeuronAddressCmd::Hide(a) => cmd_address_hide(network, a.address),
        NeuronAddressCmd::Show(a) => cmd_address_show(network, a.address),
        NeuronAddressCmd::List(a) => cmd_address_list(rpc_port, network, a),
    }
}

fn cmd_address_add(rpc_port: u16, network: &str, args: NeuronAddressAddArgs) {
    let client = NeptuneClient::for_network(rpc_port, network);

    let address = if let Some(idx) = args.index {
        client
            .address_at_index(idx, &args.key_type)
            .unwrap_or_else(|e| {
                eprintln!("error: {}", e);
                process::exit(1);
            })
    } else {
        client.next_address(&args.key_type).unwrap_or_else(|e| {
            eprintln!("error: {}", e);
            process::exit(1);
        })
    };

    println!("{}", address);
    if let Some(idx) = args.index {
        eprintln!("key-type: {}  index: {}", args.key_type, idx);
    } else {
        eprintln!("key-type: {}", args.key_type);
    }
}

fn cmd_address_hide(network: &str, address: String) {
    let mut hidden = load_hidden_addresses(network);
    if hidden.contains(&address) {
        eprintln!("already hidden: {}", address);
        return;
    }
    hidden.push(address.clone());
    match save_hidden_addresses(network, &hidden) {
        Ok(()) => eprintln!("hidden: {}", address),
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_address_show(network: &str, address: String) {
    let mut hidden = load_hidden_addresses(network);
    let before = hidden.len();
    hidden.retain(|a| a != &address);
    if hidden.len() == before {
        eprintln!("not in hidden list: {}", address);
        return;
    }
    match save_hidden_addresses(network, &hidden) {
        Ok(()) => eprintln!("visible: {}", address),
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_address_list(rpc_port: u16, network: &str, args: NeuronAddressListArgs) {
    let client = NeptuneClient::for_network(rpc_port, network);
    let output = client
        .known_keys(args.start, args.limit)
        .unwrap_or_else(|e| {
            eprintln!("error: {}", e);
            process::exit(1);
        });

    if output.is_empty() {
        println!("No addresses found.");
        return;
    }

    let hidden = load_hidden_addresses(network);
    let mut displayed = 0u32;
    for line in output.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        if !args.all && hidden.iter().any(|h| trimmed.contains(h.as_str())) {
            continue;
        }
        println!("{}", trimmed);
        displayed += 1;
    }

    if displayed == 0 && !hidden.is_empty() {
        eprintln!("All addresses are hidden. Use --all to show them.");
    }
}

fn cmd_neuron_boxes(rpc_port: u16, network: &str) {
    let client = NeptuneClient::for_network(rpc_port, network);
    let boxes = client.list_utxos().unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });
    if boxes.is_empty() {
        println!("No boxes found.");
    } else {
        println!("{}", boxes);
    }
}

fn cmd_neuron_create(rpc_port: u16, network: &str, import: bool) {
    match NeptuneClient::for_network(rpc_port, network).create_neuron(import) {
        Ok(path) => eprintln!(
            "Wallet {}: {}",
            if import { "imported" } else { "created" },
            path.display()
        ),
        Err(e) => {
            eprintln!("error: {e}");
            process::exit(1);
        }
    }
}

fn cmd_neuron_remove(rpc_port: u16, network: &str, confirmed: bool) {
    let client = NeptuneClient::for_network(rpc_port, network);
    let wallet = client.wallet_file().unwrap_or_else(|e| {
        eprintln!("error: {e}");
        process::exit(1);
    });
    let Some(wallet) = wallet else {
        eprintln!("No wallet found for {network}.");
        return;
    };
    let directory = wallet.parent().expect("validated wallet path");
    if !confirmed {
        eprintln!("Wallet directory: {}", directory.display());
        eprintln!(
            "Removal requires --confirm. Stop the node and ensure your wallet backup exists before removing it."
        );
        return;
    }
    // Revalidate immediately before deletion, including all symlink components.
    let current = client.wallet_file().unwrap_or_else(|e| {
        eprintln!("error: {e}");
        process::exit(1);
    });
    if current.as_ref() != Some(&wallet) {
        eprintln!("error: selected wallet changed before removal");
        process::exit(1);
    }
    match std::fs::remove_dir_all(directory) {
        Ok(()) => eprintln!("Wallet directory removed: {}", directory.display()),
        Err(e) => {
            eprintln!("error: wallet removal failed: {e}");
            process::exit(1);
        }
    }
}
