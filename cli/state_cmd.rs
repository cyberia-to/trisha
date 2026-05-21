use std::process;

use clap::{Args, Subcommand};

use crate::state::{self, STATES};

#[derive(Args)]
pub struct StateArgs {
    #[command(subcommand)]
    pub cmd: StateCmd,
}

#[derive(Subcommand)]
pub enum StateCmd {
    /// List all known states
    List,
    /// Show details for a specific state
    Show(StateShowArgs),
}

#[derive(Args)]
pub struct StateShowArgs {
    pub union: String,
    pub name: String,
}

pub fn cmd_state(args: StateArgs) {
    match args.cmd {
        StateCmd::List => cmd_state_list(),
        StateCmd::Show(a) => cmd_state_show(&a.union, &a.name),
    }
}

fn cmd_state_list() {
    for s in STATES {
        let marker = if s.is_default { " *" } else { "" };
        println!(
            "{}/{}{} — {} (port {}, {})",
            s.union, s.name, marker, s.display_name, s.rpc_port, s.currency_symbol
        );
    }
    println!();
    println!("* = default");
}

fn cmd_state_show(union: &str, name: &str) {
    let s = state::resolve(union, name).unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });
    println!("Display name     : {}", s.display_name);
    println!("Union            : {}", s.union);
    println!("State            : {}", s.name);
    println!("Chain ID         : {}", s.chain_id);
    println!("RPC port         : {}", s.rpc_port);
    println!("Network flag     : {}", s.network_flag);
    println!("Currency         : {}", s.currency_symbol);
    println!("Default          : {}", s.is_default);
}
