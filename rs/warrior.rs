use rayon::prelude::*;
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

pub struct Warrior;

impl Warrior {
    pub fn new() -> Self {
        eprintln!("Backend: cpu");
        Warrior
    }

    /// Execute an untrusted candidate without collecting an unbounded trace.
    pub fn run_bounded(
        &self,
        bundle: &ProgramBundle,
        input: &ProgramInput,
        max_cycles: u32,
    ) -> Result<ExecutionResult, String> {
        crate::bundle::validate(bundle)?;
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {e}"))?;
        let (public, secret) = convert::to_triton_inputs(input)?;
        let mut state = VMState::new(program, public, secret);
        while !state.halting {
            if state.cycle_count >= max_cycles {
                return Err(format!("execution budget exceeded: {max_cycles} cycles"));
            }
            state
                .step()
                .map_err(|e| convert::execution_error(e, input))?;
        }
        Ok(convert::to_execution_result(
            &state.public_output,
            u64::from(state.cycle_count),
        ))
    }

    pub fn prove_full(
        &self,
        bundle: &ProgramBundle,
        input: &ProgramInput,
    ) -> Result<ProveResult, String> {
        crate::bundle::validate(bundle)?;
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;

        let (pub_in, non_det) = convert::to_triton_inputs(input)?;

        let op_count = bundle.assembly.lines().count();
        eprintln!("Proving {} ({} ops)...", bundle.name, op_count);

        let (aet, output) = VM::trace_execution(program.clone(), pub_in.clone(), non_det)
            .map_err(|e| convert::execution_error(e, input))?;

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
                format: "stark-triton-v7".to_string(),
            },
            cycle_count,
            padded_height,
        })
    }
}

impl Runner for Warrior {
    fn run(&self, bundle: &ProgramBundle, input: &ProgramInput) -> Result<ExecutionResult, String> {
        crate::bundle::validate(bundle)?;
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;

        let (pub_in, non_det) = convert::to_triton_inputs(input)?;

        let op_count = bundle.assembly.lines().count();
        eprintln!("Executing {} ({} ops)...", bundle.name, op_count);

        let (aet, output) = VM::trace_execution(program, pub_in, non_det)
            .map_err(|e| convert::execution_error(e, input))?;
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
        if proof_data.format != "stark-triton-v7" {
            return Err(format!("unsupported proof format: {}", proof_data.format));
        }
        let claim = convert::to_triton_claim_native(
            &proof_data.claim.program_hash,
            &proof_data.claim.public_input,
            &proof_data.claim.public_output,
        )?;
        let proof = convert::bytes_to_proof(&proof_data.proof_bytes)?;
        Ok(crate::convert::verify_native_proof(&claim, &proof).is_ok())
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
        crate::bundle::validate(bundle)?;
        let program =
            Program::from_code(&bundle.assembly).map_err(|e| format!("TASM parse error: {}", e))?;

        let base: [BFieldElement; 5] = program.hash().0;

        let threads = rayon::current_num_threads();
        eprintln!(
            "Mining {} (difficulty {}, max {} attempts, {} threads)...",
            bundle.name, difficulty, max_attempts, threads
        );

        let start = std::time::Instant::now();

        let found = (0u64..max_attempts).into_par_iter().find_any(|&nonce| {
            let input = [
                base[0],
                base[1],
                base[2],
                base[3],
                base[4],
                BFieldElement::new(nonce),
            ];
            Tip5::hash_varlen(&input).0[0].value() < difficulty
        });

        match found {
            Some(nonce) => {
                let input = [
                    base[0],
                    base[1],
                    base[2],
                    base[3],
                    base[4],
                    BFieldElement::new(nonce),
                ];
                let hash = Tip5::hash_varlen(&input);
                let elapsed = start.elapsed();
                let rate = nonce as f64 / elapsed.as_secs_f64();
                eprintln!(
                    "Found nonce {} in {} attempts ({:.0} H/s, {:.1}s)",
                    nonce,
                    nonce + 1,
                    rate,
                    elapsed.as_secs_f64()
                );
                Ok(GuessResult {
                    nonce,
                    digest: hash.0.iter().map(|b| b.value()).collect(),
                    attempts: nonce + 1,
                })
            }
            None => Err(format!(
                "no solution found within {} attempts",
                max_attempts
            )),
        }
    }
}
