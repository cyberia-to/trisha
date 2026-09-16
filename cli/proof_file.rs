use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::error::TrishaError;

#[derive(Serialize, Deserialize)]
pub struct ProofFile {
    pub proof: ProofMeta,
    pub claim: ClaimSection,
    pub data: DataSection,
}

#[derive(Serialize, Deserialize)]
pub struct ProofMeta {
    pub format: String,
    pub program_name: String,
    pub cycle_count: u64,
    pub padded_height: u64,
    pub proving_time_ms: u64,
}

/// Field elements serialized as strings (Goldilocks values exceed i64 range).
#[derive(Serialize, Deserialize)]
pub struct ClaimSection {
    #[serde(with = "u64_strings")]
    pub program_hash: Vec<u64>,
    #[serde(with = "u64_strings")]
    pub public_input: Vec<u64>,
    #[serde(with = "u64_strings")]
    pub public_output: Vec<u64>,
}

mod u64_strings {
    use serde::{self, Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(values: &[u64], serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        use serde::ser::SerializeSeq;
        let mut seq = serializer.serialize_seq(Some(values.len()))?;
        for v in values {
            seq.serialize_element(&v.to_string())?;
        }
        seq.end()
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Vec<u64>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let strings: Vec<String> = Vec::deserialize(deserializer)?;
        strings
            .iter()
            .map(|s| s.parse::<u64>().map_err(serde::de::Error::custom))
            .collect()
    }
}

#[derive(Serialize, Deserialize)]
pub struct DataSection {
    pub proof: String,
}

impl ProofFile {
    pub fn save(&self, path: &Path) -> Result<(), TrishaError> {
        let content = toml::to_string(self)
            .map_err(|e| TrishaError::Io(format!("TOML serialization failed: {}", e)))?;
        std::fs::write(path, content)?;
        Ok(())
    }

    pub fn load(path: &Path) -> Result<Self, TrishaError> {
        let bytes = crate::input_file::read_regular_bounded(path)
            .map_err(|error| TrishaError::Verify(format!("proof {error}")))?;
        let content = std::str::from_utf8(&bytes)
            .map_err(|_| TrishaError::Verify("invalid proof file: expected UTF-8".into()))?;
        toml::from_str(content).map_err(|_| TrishaError::Verify("invalid proof file".into()))
    }

    pub fn encode_proof_bytes(bytes: &[u8]) -> String {
        use base64::Engine;
        base64::engine::general_purpose::STANDARD.encode(bytes)
    }

    pub fn decode_proof_bytes(encoded: &str) -> Result<Vec<u8>, TrishaError> {
        use base64::Engine;
        base64::engine::general_purpose::STANDARD
            .decode(encoded)
            .map_err(|e| TrishaError::Verify(format!("invalid base64 proof data: {}", e)))
    }
}
