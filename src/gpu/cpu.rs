//! CPU fallback backend — delegates all operations to triton-vm.

use triton_vm::prelude::*;
use triton_vm::proof::Proof;

use super::GpuBackend;

/// CPU-only backend using triton-vm's built-in implementations.
pub struct CpuBackend;

impl GpuBackend for CpuBackend {
    fn name(&self) -> &str {
        "cpu"
    }

    fn trace(
        &self,
        program: &Program,
        public_input: PublicInput,
        non_determinism: NonDeterminism,
    ) -> Result<(Vec<BFieldElement>, u64), String> {
        let output = VM::run(program.clone(), public_input, non_determinism)
            .map_err(|e| format!("execution error: {}", e))?;
        // VM::run doesn't return cycle count; use 0 as placeholder
        Ok((output, 0))
    }

    fn prove(
        &self,
        program: &Program,
        public_input: PublicInput,
        non_determinism: NonDeterminism,
    ) -> Result<(triton_vm::proof::Claim, Proof), String> {
        let (_stark, claim, proof) =
            triton_vm::prove_program(program.clone(), public_input, non_determinism)
                .map_err(|e| format!("proving error: {}", e))?;
        Ok((claim, proof))
    }

    fn verify(&self, claim: &triton_vm::proof::Claim, proof: &Proof) -> Result<bool, String> {
        let stark = Stark::default();
        Ok(triton_vm::verify(stark, claim, proof))
    }

    fn verify_batch(&self, jobs: &[(triton_vm::proof::Claim, Proof)]) -> Vec<Result<bool, String>> {
        jobs.iter()
            .map(|(claim, proof)| self.verify(claim, proof))
            .collect()
    }
}
