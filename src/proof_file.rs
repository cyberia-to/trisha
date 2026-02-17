//! Proof file format: TOML envelope + bincode proof bytes (base64-encoded).

use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::error::TrishaError;

/// Top-level proof file structure.
#[derive(Serialize, Deserialize)]
pub struct ProofFile {
    pub proof: ProofMeta,
    pub claim: ClaimSection,
    pub data: DataSection,
}

/// Proof metadata.
#[derive(Serialize, Deserialize)]
pub struct ProofMeta {
    /// Proof system identifier.
    pub format: String,
    /// Program name.
    pub program_name: String,
    /// Number of VM cycles.
    pub cycle_count: u64,
    /// Padded trace height (next power of two).
    pub padded_height: u64,
    /// Proving time in milliseconds.
    pub proving_time_ms: u64,
}

/// Claim section: what the proof asserts.
#[derive(Serialize, Deserialize)]
pub struct ClaimSection {
    /// Program hash (5 Goldilocks field elements).
    pub program_hash: Vec<u64>,
    /// Public input field elements.
    pub public_input: Vec<u64>,
    /// Public output field elements.
    pub public_output: Vec<u64>,
}

/// Data section: opaque proof bytes.
#[derive(Serialize, Deserialize)]
pub struct DataSection {
    /// base64(bincode(triton_vm::Proof))
    pub proof: String,
}

impl ProofFile {
    /// Write proof file to disk as TOML.
    pub fn save(&self, path: &Path) -> Result<(), TrishaError> {
        let content = toml::to_string(self)
            .map_err(|e| TrishaError::Io(format!("TOML serialization failed: {}", e)))?;
        std::fs::write(path, content)?;
        Ok(())
    }

    /// Read proof file from disk.
    pub fn load(path: &Path) -> Result<Self, TrishaError> {
        let content = std::fs::read_to_string(path)?;
        toml::from_str(&content)
            .map_err(|e| TrishaError::Verify(format!("invalid proof file: {}", e)))
    }

    /// Encode proof bytes as base64 string.
    pub fn encode_proof_bytes(bytes: &[u8]) -> String {
        use base64::Engine;
        base64::engine::general_purpose::STANDARD.encode(bytes)
    }

    /// Decode proof bytes from base64 string.
    pub fn decode_proof_bytes(encoded: &str) -> Result<Vec<u8>, TrishaError> {
        use base64::Engine;
        base64::engine::general_purpose::STANDARD
            .decode(encoded)
            .map_err(|e| TrishaError::Verify(format!("invalid base64 proof data: {}", e)))
    }
}
