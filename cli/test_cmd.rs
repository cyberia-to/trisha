use clap::Args;
use std::path::PathBuf;

#[derive(Args)]
pub struct TestArgs {
    /// Source file or project directory containing #[test] functions
    pub input: PathBuf,
    #[arg(long)]
    pub target: Option<String>,
    #[arg(long, default_value = "debug")]
    pub profile: String,
}

pub fn cmd_test(args: TestArgs) {
    let target = crate::compile::selected_target(Some(&args.input), args.target.as_deref());
    match trisha_rs::test::run_tests(&args.input, &target, &args.profile) {
        Ok(report) => eprint!("{report}"),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
}
