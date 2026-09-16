//! Export an already generated, freshly verified canonical oracle proof.
#[path = "../src/artifact.rs"]
mod artifact;
use std::io::Read;
use tasm_lib::triton_vm::prelude::*;
fn main() {
    let args: Vec<_> = std::env::args().skip(1).collect();
    assert_eq!(
        args.len(),
        4,
        "JSON OUTPUT_PREFIX MEASURED_CYCLES MEASURED_PROVING_MS"
    );
    let mut bytes = Vec::new();
    std::fs::File::open(&args[0])
        .unwrap()
        .take(64 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)
        .unwrap();
    assert!(bytes.len() <= 64 * 1024 * 1024);
    let value: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
    for fields in [
        &value["proof"],
        &value["claim"]["input"],
        &value["claim"]["output"],
    ] {
        assert!(fields
            .as_array()
            .unwrap()
            .iter()
            .all(|v| v.as_u64().is_some_and(|n| n < BFieldElement::P)));
    }
    let claim: Claim = serde_json::from_value(value["claim"].clone()).unwrap();
    let proof: Proof = serde_json::from_value(value["proof"].clone()).unwrap();
    assert_eq!(claim.version, 5);
    assert_eq!(
        serde_json::to_value(&claim).unwrap(),
        value["claim"],
        "noncanonical claim encoding"
    );

    artifact::write(
        std::path::Path::new(&args[1]),
        &claim,
        &proof,
        args[2].parse().unwrap(),
        args[3].parse().unwrap(),
    );
}
