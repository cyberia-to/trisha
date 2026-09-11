use triton_vm::prelude::*;
use triton_vm::proof::Claim;

use trident::runtime::{
    Deployer, ExecutionResult, GuessResult, Guesser, ProgramBundle, ProgramInput, ProofData,
    Prover, Runner, Verifier,
};

use crate::convert;

pub struct ProveResult {
    pub proof_data: ProofData,
    pub cycle_count: u64,
    pub padded_height: u64,
}

pub struct Warrior {
    gpu: bool,
}

impl Warrior {
    pub fn new() -> Self {
        #[cfg(not(target_arch = "wasm32"))]
        {
            if let Some(backend) = crate::backend::WgpuBackend::try_new() {
                eprintln!("GPU: {}", backend.adapter_info());
                if let Some(accel) = crate::backend::create_tip5_accelerator() {
                    match triton_vm::gpu::set_gpu_accelerator(Box::new(accel)) {
                        Ok(()) => eprintln!("GPU: Tip5 accelerator registered"),
                        Err(_) => eprintln!("GPU: Tip5 accelerator already registered"),
                    }
                }
                return Warrior { gpu: true };
            }
            eprintln!("GPU: not available, using CPU");
        }
        Warrior { gpu: false }
    }

    pub fn gpu_available(&self) -> bool {
        self.gpu
    }

    pub fn prove_full(
        &self,
        bundle: &ProgramBundle,
        input: &ProgramInput,
    ) -> Result<ProveResult, String> {
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;

        let (pub_in, non_det) = convert::to_triton_inputs(input);

        let op_count = bundle.assembly.lines().count();
        eprintln!("Proving {} ({} ops)...", bundle.name, op_count);

        let (aet, output) = VM::trace_execution(program.clone(), pub_in.clone(), non_det)
            .map_err(|e| format!("execution error: {}", e))?;

        let cycle_count = aet.processor_trace.nrows() as u64;
        let padded_height = aet.padded_height() as u64;

        let claim = Claim::about_program(&program)
            .with_input(pub_in.individual_tokens)
            .with_output(output);

        let proof = Stark::default()
            .prove(&claim, &aet)
            .map_err(|e| format!("proving error: {}", e))?;

        eprintln!(
            "Proof generated ({} cycles, padded height {})",
            cycle_count, padded_height
        );

        Ok(ProveResult {
            proof_data: ProofData {
                claim: convert::to_trident_claim(&claim),
                proof_bytes: convert::proof_to_bytes(&proof),
                format: "stark-triton-v2".to_string(),
            },
            cycle_count,
            padded_height,
        })
    }
}

impl Runner for Warrior {
    fn run(&self, bundle: &ProgramBundle, input: &ProgramInput) -> Result<ExecutionResult, String> {
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;

        let (pub_in, non_det) = convert::to_triton_inputs(input);

        let op_count = bundle.assembly.lines().count();
        eprintln!("Executing {} ({} ops)...", bundle.name, op_count);

        let (aet, output) = VM::trace_execution(program, pub_in, non_det)
            .map_err(|e| format!("execution error: {}", e))?;
        let cycle_count = aet.processor_trace.nrows() as u64;
        Ok(convert::to_execution_result(&output, cycle_count))
    }
}

impl Prover for Warrior {
    fn prove(&self, bundle: &ProgramBundle, input: &ProgramInput) -> Result<ProofData, String> {
        self.prove_full(bundle, input).map(|r| r.proof_data)
    }
}

impl Verifier for Warrior {
    fn verify(&self, proof_data: &ProofData) -> Result<bool, String> {
        if proof_data.format != "stark-triton-v2" {
            return Err(format!("unsupported proof format: {}", proof_data.format));
        }
        let claim = convert::to_triton_claim_native(
            &proof_data.claim.program_hash,
            &proof_data.claim.public_input,
            &proof_data.claim.public_output,
        )?;
        let proof = convert::bytes_to_proof(&proof_data.proof_bytes)?;
        let stark = Stark::default();
        Ok(triton_vm::verify(stark, &claim, &proof))
    }
}

impl Deployer for Warrior {
    fn deploy(
        &self,
        _bundle: &ProgramBundle,
        _proof: Option<&ProofData>,
    ) -> Result<String, String> {
        Err(
            "on-chain Neptune deployment is not implemented; use --dry-run to inspect the artifact"
                .to_string(),
        )
    }
}

impl Guesser for Warrior {
    fn guess(
        &self,
        bundle: &ProgramBundle,
        _input: &ProgramInput,
        difficulty: u64,
        max_attempts: u64,
    ) -> Result<GuessResult, String> {
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;

        let digest = program.hash();
        let message: Vec<BFieldElement> = digest.0.to_vec();

        eprintln!(
            "Mining {} (difficulty {}, max {} attempts)...",
            bundle.name, difficulty, max_attempts
        );

        // Try GPU mining first
        #[cfg(not(target_arch = "wasm32"))]
        if let Some(accel) = crate::backend::create_tip5_accelerator() {
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

        // CPU fallback
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
