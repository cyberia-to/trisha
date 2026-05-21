use std::process;

use clap::{Args, Subcommand};

use crate::neptune::{
    load_hidden_addresses, neuron_dir, save_hidden_addresses, NeptuneClient,
};
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
    /// Instructions for importing a neuron from seed phrase
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
}

#[derive(Args)]
pub struct NeuronImportArgs {
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
        NeuronCmd::Balance => cmd_neuron_balance(rpc_port, state.currency_symbol),
        NeuronCmd::Address(a) => cmd_neuron_address(rpc_port, a),
        NeuronCmd::Boxes => cmd_neuron_boxes(rpc_port),
        NeuronCmd::Create => cmd_neuron_create(),
        NeuronCmd::Import(a) => cmd_neuron_import(&a.words),
        NeuronCmd::Remove(a) => cmd_neuron_remove(a.confirm),
    }
}

fn cmd_neuron_balance(rpc_port: u16, currency: &str) {
    let client = NeptuneClient::new(rpc_port);

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

fn cmd_neuron_address(rpc_port: u16, args: NeuronAddressArgs) {
    match args.cmd {
        NeuronAddressCmd::Add(a) => cmd_address_add(rpc_port, a),
        NeuronAddressCmd::Hide(a) => cmd_address_hide(a.address),
        NeuronAddressCmd::Show(a) => cmd_address_show(a.address),
        NeuronAddressCmd::List(a) => cmd_address_list(rpc_port, a.all),
    }
}

fn cmd_address_add(rpc_port: u16, args: NeuronAddressAddArgs) {
    let client = NeptuneClient::new(rpc_port);

    let address = if let Some(idx) = args.index {
        client
            .address_at_index(idx, &args.key_type)
            .unwrap_or_else(|_| {
                client.next_address(&args.key_type).unwrap_or_else(|e| {
                    eprintln!("error: {}", e);
                    process::exit(1);
                })
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

fn cmd_address_hide(address: String) {
    let mut hidden = load_hidden_addresses();
    if hidden.contains(&address) {
        eprintln!("already hidden: {}", address);
        return;
    }
    hidden.push(address.clone());
    match save_hidden_addresses(&hidden) {
        Ok(()) => eprintln!("hidden: {}", address),
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_address_show(address: String) {
    let mut hidden = load_hidden_addresses();
    let before = hidden.len();
    hidden.retain(|a| a != &address);
    if hidden.len() == before {
        eprintln!("not in hidden list: {}", address);
        return;
    }
    match save_hidden_addresses(&hidden) {
        Ok(()) => eprintln!("visible: {}", address),
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_address_list(rpc_port: u16, show_all: bool) {
    let client = NeptuneClient::new(rpc_port);
    let output = client.known_keys().unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });

    if output.is_empty() {
        println!("No addresses found.");
        return;
    }

    let hidden = load_hidden_addresses();
    let mut displayed = 0u32;
    for line in output.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        if !show_all && hidden.iter().any(|h| trimmed.contains(h.as_str())) {
            continue;
        }
        println!("{}", trimmed);
        displayed += 1;
    }

    if displayed == 0 && !hidden.is_empty() {
        eprintln!("All addresses are hidden. Use --all to show them.");
    }
}

fn cmd_neuron_boxes(rpc_port: u16) {
    let client = NeptuneClient::new(rpc_port);
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

fn cmd_neuron_create() {
    match NeptuneClient::create_neuron() {
        Ok(output) => {
            if output.is_empty() {
                eprintln!("Neuron created successfully.");
            } else {
                eprintln!("=== WRITE DOWN YOUR SEED PHRASE ===");
                println!("{}", output);
                eprintln!("===================================");
                eprintln!("Store the seed phrase in a safe place. It cannot be recovered.");
            }
        }
        Err(e) => {
            eprintln!("error: {}", e);
            process::exit(1);
        }
    }
}

fn cmd_neuron_import(words: &[String]) {
    if words.is_empty() {
        eprintln!("Usage: trisha neuron import <word1> <word2> ... <word24>");
        process::exit(1);
    }
    let phrase = words.join(" ");
    eprintln!("Importing a neuron from seed phrase requires neptune-core:");
    eprintln!();
    eprintln!("  1. Stop neptune-core if it is running.");
    eprintln!("  2. Remove the existing neuron:");
    eprintln!("       trisha neuron remove --confirm");
    eprintln!("  3. Start neptune-core and enter your seed phrase when prompted:");
    eprintln!("       neptune-core --network alpha-mainnet");
    eprintln!();
    eprintln!("Seed phrase ({} words): {}", words.len(), phrase);
}

fn cmd_neuron_remove(confirmed: bool) {
    let neuron_path = neuron_dir();

    if !neuron_path.exists() {
        eprintln!(
            "Neuron directory not found at: {}",
            neuron_path.display()
        );
        eprintln!("Nothing to remove.");
        return;
    }

    eprintln!("Neuron directory: {}", neuron_path.display());

    if let Ok(entries) = std::fs::read_dir(&neuron_path) {
        for entry in entries.flatten() {
            eprintln!("  {}", entry.file_name().to_string_lossy());
        }
    }

    if !confirmed {
        eprintln!();
        eprintln!("This will permanently remove your neuron. All funds will be");
        eprintln!("lost unless you have the seed phrase.");
        eprintln!();
        eprintln!("Re-run with --confirm to proceed:");
        eprintln!("  trisha neuron remove --confirm");
        return;
    }

    match std::fs::remove_dir_all(&neuron_path) {
        Ok(()) => eprintln!("Neuron removed: {}", neuron_path.display()),
        Err(e) => {
            eprintln!("error: failed to remove neuron: {}", e);
            process::exit(1);
        }
    }
}
