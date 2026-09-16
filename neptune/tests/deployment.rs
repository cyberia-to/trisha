//! Full local release gate; generate the pinned oracle fixture before invocation.
use trisha_neptune::{prepare, read_intent};
#[test]
#[ignore = "requires fresh pinned SingleProof with compiled custom-lock UTXO"]
fn genuine_custom_lock_transaction_and_binding_mutations() {
    let intent_path = std::env::var("TRISHA_DEPLOY_INTENT").expect("TRISHA_DEPLOY_INTENT required");
    let assembly_path =
        std::env::var("TRISHA_DEPLOY_ASSEMBLY").expect("TRISHA_DEPLOY_ASSEMBLY required");
    let assembly = std::fs::read_to_string(assembly_path).unwrap();
    let load = || read_intent(std::path::Path::new(&intent_path)).unwrap();
    let intent = load();
    let prepared = prepare(&assembly, &intent, "local-testnet1").unwrap();
    assert_eq!(prepared.kernel_digest(), intent.expected_kernel);
    assert!(prepare(&assembly, &intent, "mainnet").is_err());
    assert!(prepare("push 123 pop 1 halt", &intent, "local-testnet1")
        .unwrap_err()
        .contains("UTXO lock"));
    let mut bad = load();
    bad.expected_kernel[0] ^= 1;
    assert!(prepare(&assembly, &bad, "local-testnet1")
        .unwrap_err()
        .contains("kernel differs"));
    let mut bad = load();
    bad.outputs[0].sender_randomness[0] ^= 1;
    assert!(prepare(&assembly, &bad, "local-testnet1")
        .unwrap_err()
        .contains("preimage"));
    let mut bad = load();
    bad.outputs[0].receiver_digest[0] ^= 1;
    assert!(prepare(&assembly, &bad, "local-testnet1")
        .unwrap_err()
        .contains("preimage"));
    let mut bad = load();
    bad.outputs[0].compiled_lock = false;
    assert!(prepare(&assembly, &bad, "local-testnet1").is_err());
    let mut bad = load();
    bad.outputs[0].sender_randomness[0] = u64::MAX;
    assert!(prepare(&assembly, &bad, "local-testnet1").is_err());
    let mut bad = load();
    bad.transaction["kernel"]["fee"] = serde_json::json!("1");
    let rpc: neptune_rpc_api::model::wallet::transaction::RpcTransaction =
        serde_json::from_value(bad.transaction.clone()).unwrap();
    let changed: neptune_consensus::transaction::Transaction = rpc.into();
    use neptune_primitives::mast_hash::MastHash;
    bad.expected_kernel = changed.kernel.mast_hash().values().map(|v| v.value());
    assert!(prepare(&assembly, &bad, "local-testnet1")
        .unwrap_err()
        .contains("proof does not verify"));
    let mut bad = load();
    bad.transaction["extra"] = serde_json::json!(1);
    assert!(prepare(&assembly, &bad, "local-testnet1")
        .unwrap_err()
        .contains("canonically"));
    let mut bad = load();
    let mut proof = bad.transaction["proof"].as_str().unwrap().to_owned();
    proof.push_str("0000000000000000");
    bad.transaction["proof"] = serde_json::json!(proof);
    assert!(prepare(&assembly, &bad, "local-testnet1").is_err());
}
