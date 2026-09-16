//! Convert an independent pinned-consensus proof to the owned recursive witness.
use std::io::Read;
use trisha_rs::recursive;
use triton_vm::prelude::*;
fn fields(values: &[u64]) -> String {
    format!(
        "[{}]",
        values
            .iter()
            .map(|v| format!("\"{v}\""))
            .collect::<Vec<_>>()
            .join(",")
    )
}
fn main() {
    let args: Vec<_> = std::env::args().skip(1).collect();
    assert_eq!(
        args.len(),
        3,
        "usage: neptune_witness native|transaction ORACLE_JSON OUTPUT_TOML"
    );
    let mut bytes = Vec::new();
    std::fs::File::open(&args[1])
        .unwrap()
        .take(64 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)
        .unwrap();
    assert!(bytes.len() <= 64 * 1024 * 1024);
    let value: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
    for key in ["input", "output"] {
        assert!(value["claim"][key]
            .as_array()
            .unwrap()
            .iter()
            .all(|v| v.as_u64().is_some_and(|v| v < BFieldElement::P)));
    }
    let claim: Claim = serde_json::from_value(value["claim"].clone()).unwrap();
    let count = match args[0].as_str() {
        "native" => 3,
        "transaction" => 1,
        _ => panic!("unknown policy"),
    };
    assert_eq!(claim.input.len(), count * 5);
    let digests: Vec<_> = claim
        .input
        .chunks_exact(5)
        .map(|chunk| {
            Digest::new(
                chunk
                    .iter()
                    .rev()
                    .copied()
                    .collect::<Vec<_>>()
                    .try_into()
                    .unwrap(),
            )
        })
        .collect();
    let expected = if count == 1 {
        recursive::neptune::transaction_claim(digests[0])
    } else {
        recursive::neptune::native_currency_claim(digests[0], digests[1], digests[2])
    };
    assert_eq!(
        claim, expected,
        "oracle must prove exactly the fixed owner protocol claim"
    );
    let words = value["proof"].as_array().unwrap();
    assert!(words.len() < recursive::MAX_PROOF_WORDS);
    let proof = Proof(
        words
            .iter()
            .map(|v| {
                let n = v.as_u64().unwrap();
                assert!(n < BFieldElement::P);
                BFieldElement::new(n)
            })
            .collect(),
    );
    let witness = recursive::encode(&expected, &proof)
        .expect("fresh canonical default-security proof verification");
    std::fs::write(
        &args[2],
        format!(
            "secret = {}\ndigests = {}\n",
            fields(&witness.secret),
            fields(
                &witness
                    .digests
                    .iter()
                    .flatten()
                    .copied()
                    .collect::<Vec<_>>()
            )
        ),
    )
    .unwrap();
    let public: Vec<_> = digests
        .iter()
        .flat_map(|d| d.values().map(|v| v.value()))
        .collect();
    println!("input = {}", fields(&public));
}
