use trident::runtime::{
    Deployer, ExecutionResult, ProgramBundle, ProgramInput, ProofData, Prover, Runner, Verifier,
};

use crate::error::TrishaError;

/// Trisha warrior: implements all four runtime traits for Triton VM.
pub struct TrishaWarrior;

impl TrishaWarrior {
    pub fn new() -> Self {
        TrishaWarrior
    }
}

impl Runner for TrishaWarrior {
    fn run(&self, bundle: &ProgramBundle, input: &ProgramInput) -> Result<ExecutionResult, String> {
        // Phase 1: stub — will be implemented when triton-vm is added
        let _ = input;
        let op_count = bundle.assembly.lines().count();
        eprintln!("Executing {} ({} ops)...", bundle.name, op_count);
        eprintln!("triton-vm execution not yet implemented");
        Err("triton-vm dependency not yet added — coming in Phase 2".to_string())
    }
}

impl Prover for TrishaWarrior {
    fn prove(&self, _bundle: &ProgramBundle, _input: &ProgramInput) -> Result<ProofData, String> {
        Err("proving not yet implemented — coming in Phase 2".to_string())
    }
}

impl Verifier for TrishaWarrior {
    fn verify(&self, _proof: &ProofData) -> Result<bool, String> {
        Err("verification not yet implemented — coming in Phase 3".to_string())
    }
}

impl Deployer for TrishaWarrior {
    fn deploy(
        &self,
        _bundle: &ProgramBundle,
        _proof: Option<&ProofData>,
    ) -> Result<String, String> {
        Err("deployment not yet implemented — coming in Phase 4".to_string())
    }
}

/// Parse comma-separated u64 values from a CLI argument.
pub fn parse_values(s: &str) -> Result<Vec<u64>, TrishaError> {
    s.split(',')
        .map(|v| {
            v.trim()
                .parse::<u64>()
                .map_err(|e| TrishaError::Parse(format!("invalid field element '{}': {}", v, e)))
        })
        .collect()
}
