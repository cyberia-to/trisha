//! Offline program inspection for the Neptune transaction preparation boundary.
use trident::runtime::{ProgramBundle, ProofData, Verifier};
use triton_vm::prelude::Program;

#[derive(Debug)]
pub struct ProgramInspection {
    pub lock_script_hash: [u64; 5],
    pub execution_proof_verified: bool,
}

pub fn inspect(
    bundle: &ProgramBundle,
    proof: Option<&ProofData>,
) -> Result<ProgramInspection, String> {
    crate::bundle::validate(bundle)?;
    let program = Program::from_code(&bundle.assembly)
        .map_err(|e| format!("invalid lock-script program: {e}"))?;
    let lock_script_hash = program.hash().0.map(|v| v.value());
    if let Some(proof) = proof {
        if proof.claim.program_hash != lock_script_hash {
            return Err("attached execution proof belongs to another program".into());
        }
        if !crate::Warrior.verify(proof)? {
            return Err("attached execution proof failed verification".into());
        }
    }
    Ok(ProgramInspection {
        lock_script_hash,
        execution_proof_verified: proof.is_some(),
    })
}
