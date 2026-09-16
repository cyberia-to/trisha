use rayon::prelude::*;
use triton_vm::prelude::*;

use trident::runtime::{
    Deployer, ExecutionResult, GuessResult, Guesser, ProgramBundle, ProgramInput, ProofData,
    Prover, Runner, Verifier,
};

pub struct Warrior;

impl Warrior {
    pub fn new() -> Self {
        let threads = rayon::current_num_threads();
        eprintln!("Backend: honeycrisp ({} threads)", threads);
        Warrior
    }
}

impl Runner for Warrior {
    fn run(&self, _bundle: &ProgramBundle, _input: &ProgramInput) -> Result<ExecutionResult, String> {
        Err("honeycrisp: run not implemented".to_string())
    }
}

impl Prover for Warrior {
    fn prove(&self, _bundle: &ProgramBundle, _input: &ProgramInput) -> Result<ProofData, String> {
        Err("honeycrisp: prove not implemented".to_string())
    }
}

impl Verifier for Warrior {
    fn verify(&self, _proof_data: &ProofData) -> Result<bool, String> {
        Err("honeycrisp: verify not implemented".to_string())
    }
}

impl Deployer for Warrior {
    fn deploy(&self, _bundle: &ProgramBundle, _proof: Option<&ProofData>) -> Result<String, String> {
        Err("honeycrisp: deploy not implemented".to_string())
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
        let program = Program::from_code(&bundle.assembly)
            .map_err(|e| format!("TASM parse error: {}", e))?;

        let base: [BFieldElement; 5] = program.hash().0;

        let threads = rayon::current_num_threads();
        eprintln!(
            "Mining {} (difficulty {}, max {} attempts, {} threads)...",
            bundle.name, difficulty, max_attempts, threads
        );

        let start = std::time::Instant::now();

        let found = (0u64..max_attempts).into_par_iter().find_any(|&nonce| {
            let input = [base[0], base[1], base[2], base[3], base[4], BFieldElement::new(nonce)];
            Tip5::hash_varlen(&input).0[0].value() < difficulty
        });

        match found {
            Some(nonce) => {
                let input = [base[0], base[1], base[2], base[3], base[4], BFieldElement::new(nonce)];
                let hash = Tip5::hash_varlen(&input);
                let elapsed = start.elapsed();
                let rate = nonce as f64 / elapsed.as_secs_f64();
                eprintln!(
                    "Found nonce {} ({:.0} H/s, {:.1}s)",
                    nonce,
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
