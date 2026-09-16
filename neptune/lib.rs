//! Validated submission of complete caller-supplied Neptune transactions.
//! This adapter does not select wallet coins or claim current-chain admission.
use neptune_consensus::transaction::{
    transaction_proof::TransactionProof, utxo::Utxo, Transaction,
};
use neptune_primitives::mast_hash::MastHash;
use neptune_rpc_api::model::{
    message::SubmitTransactionRequest,
    wallet::transaction::{RpcCoin, RpcTransaction, RpcUtxo},
};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use serde_json::Value;
use tasm_lib::triton_vm::prelude::*;

mod json;
pub mod transport;
pub const MAX_INPUT_BYTES: u64 = 64 * 1024 * 1024;
pub const UPSTREAM_REVISION: &str = "9869b5e35b659dc520fad51ba5a9c812fed46db0";

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OutputIntent {
    /// Exact canonical RPC UTXO object, including all coins and their state.
    pub utxo: Value,
    pub sender_randomness: [u64; 5],
    pub receiver_digest: [u64; 5],
    pub compiled_lock: bool,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OutputSpec {
    pub coins: Vec<Value>,
    pub sender_randomness: [u64; 5],
    pub receiver_digest: [u64; 5],
}
#[derive(Serialize)]
pub struct ConstructedOutput {
    pub format: &'static str,
    pub intent: OutputIntent,
    pub addition_record: [u64; 5],
}
/// Construct the exact canonical custom-lock UTXO and mutator-set addition.
/// Coin states are preserved; this operation alone proves no transaction.
pub fn construct_output(assembly: &str, spec: OutputSpec) -> Result<ConstructedOutput, String> {
    if spec.coins.len() > 1024 {
        return Err("output coin count exceeds limit".into());
    }
    let program = Program::from_code(assembly).map_err(|_| "invalid compiled lock script")?;
    let coins = spec
        .coins
        .iter()
        .map(canonical::<RpcCoin>)
        .collect::<Result<Vec<_>, _>>()?;
    let utxo = Utxo::new(program.hash(), coins.into_iter().map(Into::into).collect());
    let addition = neptune_mutator_set::commit(
        Tip5::hash(&utxo),
        digest(spec.sender_randomness)?,
        digest(spec.receiver_digest)?,
    );
    Ok(ConstructedOutput {
        format: "trisha-neptune-output-v1",
        intent: OutputIntent {
            utxo: serde_json::to_value(RpcUtxo::from(utxo)).map_err(|_| "cannot encode UTXO")?,
            sender_randomness: spec.sender_randomness,
            receiver_digest: spec.receiver_digest,
            compiled_lock: true,
        },
        addition_record: addition.canonical_commitment.values().map(|w| w.value()),
    })
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransactionIntent {
    pub schema_version: u32,
    pub network: String,
    /// Independently selected full kernel commitment; never inferred from proof.
    pub expected_kernel: [u64; 5],
    pub transaction: Value,
    /// Every output, in the same order as the complete kernel.
    pub outputs: Vec<OutputIntent>,
}

#[derive(Debug, Serialize)]
pub struct PreparedTransaction {
    format: &'static str,
    upstream_revision: &'static str,
    operation: &'static str,
    network: String,
    program_digest: [u64; 5],
    kernel_digest: [u64; 5],
    output_commitments: Vec<[u64; 5]>,
    compiled_lock_outputs: Vec<usize>,
    single_proof_verified: bool,
    current_chain_admission_checked: bool,
    rpc_request: Value,
}

impl PreparedTransaction {
    pub fn kernel_digest(&self) -> [u64; 5] {
        self.kernel_digest
    }
}

fn digest(words: [u64; 5]) -> Result<Digest, String> {
    if words.iter().any(|word| *word >= BFieldElement::P) {
        return Err("noncanonical field word in intent".into());
    }
    Ok(Digest::new(words.map(BFieldElement::new)))
}

/// Round-trip equality rejects reducing field aliases, unknown object fields,
/// and alternate number/hex encodings accepted by upstream deserializers.
fn canonical<T: DeserializeOwned + Serialize>(value: &Value) -> Result<T, String> {
    let decoded: T =
        serde_json::from_value(value.clone()).map_err(|_| "invalid canonical RPC object")?;
    if serde_json::to_value(&decoded).map_err(|_| "cannot encode RPC object")? != *value {
        return Err("RPC object is not canonically encoded".into());
    }
    Ok(decoded)
}

pub fn prepare(
    assembly: &str,
    intent: &TransactionIntent,
    selected_network: &str,
) -> Result<PreparedTransaction, String> {
    if intent.schema_version != 1
        || !matches!(selected_network, "mainnet" | "testnet" | "local-testnet1")
        || intent.network != selected_network
    {
        return Err("unsupported or mismatched intent network/schema".into());
    }
    let program = Program::from_code(assembly).map_err(|_| "invalid compiled lock script")?;
    let program_digest = program.hash();
    let expected_kernel = digest(intent.expected_kernel)?;
    let rpc: RpcTransaction = canonical(&intent.transaction)?;
    let transaction: Transaction = rpc.clone().into();
    let kernel = &transaction.kernel;
    if kernel.mast_hash() != expected_kernel {
        return Err("transaction kernel differs from caller intent".into());
    }
    if kernel.coinbase.is_some() || kernel.fee.to_nau() < 0 {
        return Err("wallet submission cannot contain coinbase or negative fee".into());
    }
    if intent.outputs.is_empty()
        || intent.outputs.len() != kernel.outputs.len()
        || intent.outputs.len() > 1024
    {
        return Err("intent must describe every output (1..1024)".into());
    }
    let mut compiled_lock_outputs = Vec::new();
    let mut output_commitments = Vec::new();
    for (index, (output, record)) in intent.outputs.iter().zip(&kernel.outputs).enumerate() {
        let rpc_utxo: RpcUtxo = canonical(&output.utxo)?;
        let utxo: Utxo = rpc_utxo.into();
        if output.compiled_lock {
            if utxo.lock_script_hash() != program_digest {
                return Err("UTXO lock does not match compiled program".into());
            }
            compiled_lock_outputs.push(index);
        }
        let addition = neptune_mutator_set::commit(
            Tip5::hash(&utxo),
            digest(output.sender_randomness)?,
            digest(output.receiver_digest)?,
        );
        if addition != *record {
            return Err("output preimage does not match authenticated kernel commitment".into());
        }
        output_commitments.push(addition.canonical_commitment.values().map(|w| w.value()));
    }
    if compiled_lock_outputs.is_empty() {
        return Err("intent has no output locked by the compiled program".into());
    }
    let TransactionProof::SingleProof(proof) = &transaction.proof else {
        return Err("validated submission requires a complete SingleProof".into());
    };
    let claim = trisha_rs::recursive::neptune::transaction_claim(expected_kernel);
    trisha_rs::convert::verify_native_proof(&claim, &Proof(proof.0.clone()))?;
    let params = serde_json::to_value(SubmitTransactionRequest { transaction: rpc })
        .map_err(|_| "cannot encode RPC request")?;
    Ok(PreparedTransaction {
        format: "trisha-neptune-validated-submission-v1",
        upstream_revision: UPSTREAM_REVISION,
        operation: "submit-complete-transaction",
        network: intent.network.clone(),
        program_digest: program_digest.values().map(|w| w.value()),
        kernel_digest: intent.expected_kernel,
        output_commitments,
        compiled_lock_outputs,
        single_proof_verified: true,
        current_chain_admission_checked: false,
        rpc_request: serde_json::json!({"jsonrpc":"2.0","id":1,"method":"wallet_submitTransaction","params":params}),
    })
}

pub fn read_intent(path: &std::path::Path) -> Result<TransactionIntent, String> {
    read_json(path)
}

pub fn read_json<T: DeserializeOwned>(path: &std::path::Path) -> Result<T, String> {
    use std::io::Read;
    let metadata =
        std::fs::symlink_metadata(path).map_err(|_| "cannot inspect transaction input")?;
    if !metadata.is_file() {
        return Err("transaction input must be a regular file".into());
    }
    if metadata.len() > MAX_INPUT_BYTES {
        return Err("transaction intent exceeds 64 MiB".into());
    }
    let mut bytes = Vec::new();
    std::fs::File::open(path)
        .map_err(|_| "cannot open transaction intent")?
        .take(MAX_INPUT_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "cannot read transaction intent")?;
    if bytes.len() as u64 > MAX_INPUT_BYTES {
        return Err("transaction intent exceeds 64 MiB".into());
    }
    json::guard(&bytes)?;
    serde_json::from_slice(&bytes).map_err(|_| "invalid transaction intent JSON".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[cfg(unix)]
    #[test]
    fn rejects_fifo_directory_and_symlink_inputs_before_reading() {
        let directory =
            std::env::temp_dir().join(format!("trisha-input-kind-{}", std::process::id()));
        std::fs::create_dir(&directory).unwrap();
        let fifo = directory.join("intent.fifo");
        assert!(std::process::Command::new("mkfifo")
            .arg(&fifo)
            .status()
            .unwrap()
            .success());
        assert!(read_json::<Value>(&fifo)
            .unwrap_err()
            .contains("regular file"));
        assert!(read_json::<Value>(&directory)
            .unwrap_err()
            .contains("regular file"));
        let link = directory.join("intent.link");
        std::os::unix::fs::symlink(&fifo, &link).unwrap();
        assert!(read_json::<Value>(&link)
            .unwrap_err()
            .contains("regular file"));
        std::fs::remove_dir_all(directory).unwrap();
    }
    #[test]
    fn constructs_actual_custom_utxo_and_rejects_reducing_rpc_aliases() {
        let program = Program::from_code("push 7 pop 1 halt").unwrap();
        let coin = neptune_consensus::transaction::utxo::Coin {
            type_script_hash: Digest::default(),
            state: vec![bfe!(1)],
        };
        let coin_json = serde_json::to_value(RpcCoin::from(coin.clone())).unwrap();
        let spec = OutputSpec {
            coins: vec![coin_json.clone()],
            sender_randomness: [2; 5],
            receiver_digest: [3; 5],
        };
        let output = construct_output(&program.to_string(), spec).unwrap();
        let expected = Utxo::new(program.hash(), vec![coin]);
        assert_eq!(
            output.intent.utxo,
            serde_json::to_value(RpcUtxo::from(expected.clone())).unwrap()
        );
        assert_eq!(
            output.addition_record,
            neptune_mutator_set::commit(
                Tip5::hash(&expected),
                digest([2; 5]).unwrap(),
                digest([3; 5]).unwrap()
            )
            .canonical_commitment
            .values()
            .map(|w| w.value())
        );
        let mut alias = coin_json;
        alias["state"] = serde_json::json!("0xffffffffffffffff");
        assert!(construct_output(
            &program.to_string(),
            OutputSpec {
                coins: vec![alias],
                sender_randomness: [2; 5],
                receiver_digest: [3; 5]
            }
        )
        .is_err());
    }
}
