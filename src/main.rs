mod cli;
mod compile;
mod convert;
mod error;
mod warrior;

use clap::Parser;
use cli::{Cli, Command};

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Command::Run(args) => cli::cmd_run(args),
        Command::Prove(args) => cli::cmd_prove(args),
        Command::Verify(args) => cli::cmd_verify(args),
    }
}
