use triton_vm::prelude::*;

use trident::runtime::{
    Deployer, ExecutionResult, ProgramBundle, ProgramInput, ProofData, Prover, Runner, Verifier,
};

use crate::convert;
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
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;

        let (pub_in, non_det) = convert::to_triton_inputs(input);

        let op_count = bundle.assembly.lines().count();
        eprintln!("Executing {} ({} ops)...", bundle.name, op_count);

        let output =
            VM::run(program, pub_in, non_det).map_err(|e| format!("execution error: {}", e))?;

        // VM::run doesn't return cycle count — use 0 as placeholder.
        // For cycle count, trace_execution is needed (but expensive).
        Ok(convert::to_execution_result(&output, 0))
    }
}

impl Prover for TrishaWarrior {
    fn prove(&self, _bundle: &ProgramBundle, _input: &ProgramInput) -> Result<ProofData, String> {
        Err("proving not yet implemented".to_string())
    }
}

impl Verifier for TrishaWarrior {
    fn verify(&self, _proof: &ProofData) -> Result<bool, String> {
        Err("verification not yet implemented".to_string())
    }
}

impl Deployer for TrishaWarrior {
    fn deploy(
        &self,
        _bundle: &ProgramBundle,
        _proof: Option<&ProofData>,
    ) -> Result<String, String> {
        Err("deployment not yet implemented".to_string())
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
