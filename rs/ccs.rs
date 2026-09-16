//! A deterministic, verifier-regenerated CCS checker proved by Triton's ZK STARK.
//! The caller must derive the relation and binding from a trusted statement.
use std::fmt::Write;
use trident::runtime::ProofData;
use triton_vm::prelude::*;
use triton_vm::proof::Claim;
use zheng::types::CCSInstance;

pub const FORMAT: &str = "zheng-ccs-triton7-zk-v2";
const MAX_COLUMNS: usize = 1 << 16;
const MAX_ROWS: usize = 1 << 16;
const MAX_MATRICES: usize = 64;
const MAX_WORK: usize = 1 << 20;

/// Contains public verifier data only. Private columns exist only during proving.
pub struct Checker {
    assembly: String,
    program: Program,
    claim: Claim,
    columns: usize,
}

impl Checker {
    /// Coordinate zero is always the constant one. Other coordinates must be
    /// sorted, unique and in range. Binding bytes identify statement and ABI.
    pub fn new(
        instance: &CCSInstance,
        public: &[(usize, u64)],
        statement_binding: &[u8],
    ) -> Result<Self, String> {
        validate(instance, public, statement_binding)?;
        let n = instance.num_cols;
        let mut code = String::from("push 1\npop 1\n"); // generator version
        writeln!(code, "push {}\npop 1", statement_binding.len()).unwrap();
        for bytes in statement_binding.chunks(4) {
            let mut limb = [0u8; 4];
            limb[..bytes.len()].copy_from_slice(bytes);
            writeln!(code, "push {}\npop 1", u32::from_le_bytes(limb)).unwrap();
        }
        // Materialize every column once. All subsequent reads use this RAM.
        for column in 0..n {
            writeln!(code, "divine 1\npush {column}\nwrite_mem 1\npop 1").unwrap();
        }
        read(&mut code, 0);
        code.push_str("push 1\neq\nassert\n");
        for &(column, _) in public {
            read(&mut code, column);
            code.push_str("read_io 1\neq\nassert\n");
        }
        for row in 0..instance.num_rows {
            for (matrix_index, matrix) in instance.matrices.iter().enumerate() {
                code.push_str("push 0\n");
                for &(column, coefficient) in &matrix.entries[row] {
                    read(&mut code, column);
                    writeln!(code, "push {}\nmul\nadd", coefficient.as_u64()).unwrap();
                }
                writeln!(code, "push {}\nwrite_mem 1\npop 1", n + matrix_index).unwrap();
            }
            code.push_str("push 0\n");
            for (multiset, coefficient) in instance.multisets.iter().zip(&instance.coeffs) {
                writeln!(code, "push {}", coefficient.as_u64()).unwrap();
                for &matrix_index in multiset {
                    read(&mut code, n + matrix_index);
                    code.push_str("mul\n");
                }
                code.push_str("add\n");
            }
            code.push_str("push 0\neq\nassert\n");
        }
        code.push_str("halt\n");
        let program = Program::from_code(&code).map_err(|_| "CCS checker generation failed")?;
        let input = public
            .iter()
            .map(|&(_, v)| BFieldElement::new(v))
            .collect::<Vec<_>>();
        let claim = Claim::about_program(&program)
            .with_input(input)
            .with_output(vec![]);
        Ok(Self {
            assembly: code,
            program,
            claim,
            columns: n,
        })
    }

    pub fn assembly(&self) -> &str {
        &self.assembly
    }

    /// Uses upstream default security and fresh upstream prover randomness.
    /// Execution errors deliberately omit VM state, which contains secrets.
    pub fn prove(&self, witness: &[u64]) -> Result<ProofData, String> {
        if witness.len() != self.columns || witness.iter().any(|&v| v >= BFieldElement::P) {
            return Err("invalid private CCS witness encoding or length".into());
        }
        let private = NonDeterminism::new(crate::convert::u64s_to_bfes(witness));
        let (aet, output) = VM::trace_execution(
            self.program.clone(),
            PublicInput::new(self.claim.input.clone()),
            private,
        )
        .map_err(|_| "private CCS witness does not satisfy the checker")?;
        if !output.is_empty() {
            return Err("CCS checker emitted unexpected output".into());
        }
        let proof = Stark::default()
            .prove(&self.claim, &aet)
            .map_err(|_| "CCS STARK proving failed")?;
        Ok(ProofData {
            claim: crate::convert::to_trident_claim(&self.claim),
            proof_bytes: crate::convert::proof_to_bytes(&proof),
            format: FORMAT.into(),
        })
    }

    /// Verifies against this independently regenerated expected program/claim.
    /// A proof-supplied program digest can never select the accepted relation.
    pub fn verify(&self, proof: &ProofData) -> Result<bool, String> {
        if proof.format != FORMAT {
            return Err("unsupported CCS proof format".into());
        }
        let expected = crate::convert::to_trident_claim(&self.claim);
        if proof.claim.program_hash != expected.program_hash
            || proof.claim.public_input != expected.public_input
            || proof.claim.public_output != expected.public_output
        {
            return Ok(false);
        }
        let decoded = crate::convert::bytes_to_proof(&proof.proof_bytes)?;
        Ok(crate::convert::verify_native_proof(&self.claim, &decoded).is_ok())
    }
}

fn read(code: &mut String, address: usize) {
    writeln!(code, "push {address}\nread_mem 1\npop 1").unwrap();
}

fn validate(c: &CCSInstance, public: &[(usize, u64)], binding: &[u8]) -> Result<(), String> {
    let invalid = || "invalid or excessive CCS checker relation".to_string();
    if c.num_cols == 0
        || c.num_cols > MAX_COLUMNS
        || c.num_rows == 0
        || c.num_rows > MAX_ROWS
        || c.matrices.is_empty()
        || c.matrices.len() > MAX_MATRICES
        || c.multisets.is_empty()
        || c.multisets.len() != c.coeffs.len()
        || c.multisets.len() > MAX_WORK
        || binding.is_empty()
        || binding.len() > 4096
    {
        return Err(invalid());
    }
    let mut work = c.num_cols;
    for matrix in &c.matrices {
        if matrix.rows != c.num_rows
            || matrix.cols != c.num_cols
            || matrix.entries.len() != c.num_rows
        {
            return Err(invalid());
        }
        for row in &matrix.entries {
            work = work.checked_add(row.len()).ok_or_else(invalid)?;
            if work > MAX_WORK || row.iter().any(|&(column, _)| column >= c.num_cols) {
                return Err(invalid());
            }
        }
    }
    let mut terms = c.matrices.len();
    for multiset in &c.multisets {
        if multiset.len() > 16 || multiset.iter().any(|&i| i >= c.matrices.len()) {
            return Err(invalid());
        }
        terms = terms.checked_add(multiset.len() + 1).ok_or_else(invalid)?;
    }
    work = work
        .checked_add(c.num_rows.checked_mul(terms).ok_or_else(invalid)?)
        .ok_or_else(invalid)?;
    if work > MAX_WORK {
        return Err(invalid());
    }
    let mut previous = 0;
    for &(column, value) in public {
        if column <= previous || column >= c.num_cols || value >= BFieldElement::P {
            return Err("invalid CCS public coordinates or noncanonical value".into());
        }
        previous = column;
    }
    Ok(())
}

/// Serialize only public claim metadata and the opaque randomized STARK proof.
pub fn encode_proof(proof: &ProofData) -> Result<Vec<u8>, String> {
    use bincode::Options;
    if proof.format != FORMAT {
        return Err("unsupported CCS proof format".into());
    }
    bincode::DefaultOptions::new()
        .with_fixint_encoding()
        .with_limit(64 << 20)
        .serialize(&(
            FORMAT,
            &proof.claim.program_hash,
            &proof.claim.public_input,
            &proof.claim.public_output,
            &proof.proof_bytes,
        ))
        .map_err(|_| "CCS proof serialization failed".into())
}

/// Bounded canonical envelope decoder; acceptance still requires `Checker::verify`.
pub fn decode_proof(bytes: &[u8]) -> Result<ProofData, String> {
    use bincode::Options;
    type Wire = (String, Vec<u64>, Vec<u64>, Vec<u64>, Vec<u8>);
    if bytes.len() > 64 << 20 {
        return Err("CCS proof exceeds size limit".into());
    }
    let (format, hash, input, output, proof_bytes): Wire = bincode::DefaultOptions::new()
        .with_fixint_encoding()
        .with_limit(64 << 20)
        .reject_trailing_bytes()
        .deserialize(bytes)
        .map_err(|_| "invalid CCS proof envelope")?;
    if format != FORMAT {
        return Err("unsupported CCS proof format".into());
    }
    let claim = crate::convert::to_triton_claim_native(&hash, &input, &output)?;
    Ok(ProofData {
        format,
        claim: crate::convert::to_trident_claim(&claim),
        proof_bytes,
    })
}
