use triton_vm::prelude::*;

use trident::runtime::{
    Deployer, ExecutionResult, GuessResult, Guesser, ProgramBundle, ProgramInput, ProofData,
    Prover, Runner, Verifier,
};

use crate::convert;
use crate::error::TrishaError;
use crate::gpu::{self, GpuBackend};

/// Trisha warrior: implements all four runtime traits for Triton VM.
///
/// Uses the GPU backend for trace generation, proving, and verification
/// when available; falls back to CPU otherwise.
pub struct TrishaWarrior {
    backend: Box<dyn GpuBackend>,
}

impl TrishaWarrior {
    pub fn new() -> Self {
        let backend = gpu::select_backend();
        eprintln!("Backend: {}", backend.name());
        TrishaWarrior { backend }
    }
}

impl Runner for TrishaWarrior {
    fn run(&self, bundle: &ProgramBundle, input: &ProgramInput) -> Result<ExecutionResult, String> {
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;

        let (pub_in, non_det) = convert::to_triton_inputs(input);

        let op_count = bundle.assembly.lines().count();
        eprintln!("Executing {} ({} ops)...", bundle.name, op_count);

        let (output, cycle_count) = self.backend.trace(&program, pub_in, non_det)?;
        Ok(convert::to_execution_result(&output, cycle_count))
    }
}

impl Prover for TrishaWarrior {
    fn prove(&self, bundle: &ProgramBundle, input: &ProgramInput) -> Result<ProofData, String> {
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;

        let (pub_in, non_det) = convert::to_triton_inputs(input);

        let op_count = bundle.assembly.lines().count();
        eprintln!("Proving {} ({} ops)...", bundle.name, op_count);

        let (claim, proof) = self.backend.prove(&program, pub_in, non_det)?;

        eprintln!("Proof generated ({} output elements)", claim.output.len());

        Ok(ProofData {
            claim: convert::to_trident_claim(&claim),
            proof_bytes: convert::proof_to_bytes(&proof),
            format: "stark-triton-v2".to_string(),
        })
    }
}

impl Verifier for TrishaWarrior {
    fn verify(&self, proof_data: &ProofData) -> Result<bool, String> {
        let claim = convert::to_triton_claim_native(
            &proof_data.claim.program_hash,
            &proof_data.claim.public_input,
            &proof_data.claim.public_output,
        );
        let proof = convert::bytes_to_proof(&proof_data.proof_bytes).map_err(|e| e.to_string())?;
        self.backend.verify(&claim, &proof)
    }
}

impl Deployer for TrishaWarrior {
    fn deploy(&self, bundle: &ProgramBundle, proof: Option<&ProofData>) -> Result<String, String> {
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;
        let digest = program.hash();
        let digest_u64s = convert::digest_to_u64s(&digest);
        let digest_str = digest_u64s
            .iter()
            .map(|v| v.to_string())
            .collect::<Vec<_>>()
            .join(":");

        eprintln!("Program:   {}", bundle.name);
        eprintln!("Digest:    {}", digest_str);
        eprintln!(
            "Proof:     {}",
            if proof.is_some() { "attached" } else { "none" }
        );
        eprintln!();
        eprintln!("On-chain deployment requires a running Neptune node.");
        eprintln!("Neptune RPC is not yet available in this release.");
        eprintln!("The program is ready for deployment — use the digest");
        eprintln!("to construct a LockScript when Neptune SDK is available.");

        Ok(digest_str)
    }
}

impl Guesser for TrishaWarrior {
    fn guess(
        &self,
        bundle: &ProgramBundle,
        _input: &ProgramInput,
        difficulty: u64,
        max_attempts: u64,
    ) -> Result<GuessResult, String> {
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;

        // Use program hash as the mining message
        let digest = program.hash();
        let message: Vec<BFieldElement> = digest.0.to_vec();

        eprintln!(
            "Mining {} (difficulty {}, max {} attempts)...",
            bundle.name, difficulty, max_attempts
        );

        // Try GPU mining first
        #[cfg(feature = "gpu")]
        {
            if let Some(accel) = crate::gpu::wgpu_backend::create_tip5_accelerator() {
                let start = std::time::Instant::now();
                if let Some((nonce, digest_bfes, attempts)) =
                    accel.mine(&message, difficulty, max_attempts)
                {
                    let elapsed = start.elapsed();
                    let rate = attempts as f64 / elapsed.as_secs_f64();
                    eprintln!(
                        "Found nonce {} in {} attempts ({:.0} H/s, {:.1}s)",
                        nonce,
                        attempts,
                        rate,
                        elapsed.as_secs_f64()
                    );
                    return Ok(GuessResult {
                        nonce,
                        digest: digest_bfes.iter().map(|b| b.value()).collect(),
                        attempts,
                    });
                }
                return Err(format!(
                    "no solution found within {} attempts",
                    max_attempts
                ));
            }
        }

        // CPU fallback: sequential search
        let start = std::time::Instant::now();
        for nonce in 0..max_attempts {
            let mut input_elements = message.clone();
            input_elements.push(BFieldElement::new(nonce));
            let hash = Tip5::hash_varlen(&input_elements);
            if hash.0[0].value() < difficulty {
                let elapsed = start.elapsed();
                let rate = (nonce + 1) as f64 / elapsed.as_secs_f64();
                eprintln!(
                    "Found nonce {} in {} attempts ({:.0} H/s, {:.1}s)",
                    nonce,
                    nonce + 1,
                    rate,
                    elapsed.as_secs_f64()
                );
                return Ok(GuessResult {
                    nonce,
                    digest: hash.0.iter().map(|b| b.value()).collect(),
                    attempts: nonce + 1,
                });
            }
        }
        Err(format!(
            "no solution found within {} attempts",
            max_attempts
        ))
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
