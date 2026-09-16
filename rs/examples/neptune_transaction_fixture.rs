//! Turn an independently generated genuine SingleProof into owner benchmark fixtures.
use std::{io::Read, path::Path};
use trident::runtime::ProgramInput;
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
fn secret_file(path: &Path, input: &ProgramInput) {
    std::fs::write(
        path,
        format!(
            "secret = {}\ndigests = {}\n",
            fields(&input.secret),
            fields(&input.digests.iter().flatten().copied().collect::<Vec<_>>())
        ),
    )
    .unwrap();
}
fn main() {
    let path = std::env::args()
        .nth(1)
        .expect("path to pinned consensus single-proof.json required");
    let mut bytes = Vec::new();
    std::fs::File::open(path)
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
    assert_eq!(claim.input.len(), 5);
    let kernel = Digest::new(
        claim
            .input
            .iter()
            .rev()
            .copied()
            .collect::<Vec<_>>()
            .try_into()
            .unwrap(),
    );
    let expected = recursive::neptune::transaction_claim(kernel);
    assert_eq!(
        claim, expected,
        "proof claim must match owner-pinned complete protocol"
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
    let mut witness = recursive::encode(&expected, &proof)
        .expect("canonical native proof must verify independently");
    witness.public = kernel.values().map(|v| v.value()).to_vec();
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
    let fixtures = root.join("baselines/triton/fixtures");
    let shared = fixtures.join("neptune-transaction-witnesses");
    std::fs::create_dir_all(&shared).unwrap();
    secret_file(&shared.join("valid.toml"), &witness);
    for (name, mutation) in [
        ("wrong-program", 0),
        ("wrong-output", 1),
        ("wrong-version", 2),
    ] {
        let mut changed = claim.clone();
        match mutation {
            0 => changed.program_digest = Digest::default(),
            1 => changed.output.push(bfe!(1)),
            _ => changed.version -= 1,
        }
        let encoded = changed.encode();
        let mut invalid = witness.clone();
        let old_len = invalid.secret[1] as usize;
        invalid.secret[1] = encoded.len() as u64;
        invalid
            .secret
            .splice(2..2 + old_len, encoded.into_iter().map(|v| v.value()));
        secret_file(&shared.join(format!("{name}.toml")), &invalid);
    }
    for name in [
        "valid",
        "wrong-kernel",
        "wrong-program",
        "wrong-output",
        "wrong-version",
    ] {
        let directory = fixtures.join("neptune-transaction");
        std::fs::create_dir_all(&directory).unwrap();
        let mut public = witness.public.clone();
        if name == "wrong-kernel" {
            public[0] = (public[0] + 1) % BFieldElement::P;
        }
        let secret = if name == "wrong-kernel" {
            "valid"
        } else {
            name
        };
        std::fs::write(directory.join(format!("{name}.bench.toml")),format!(r#"source = "../../../../examples/neptune/transaction_validation.tri"
hand = "../../os/neptune/programs/transaction_validation.tasm"
target = "neptune"
input = {}
output = ["1"]
witness_files = ["../neptune-transaction-witnesses/{secret}.toml"]
hand_prefix = "call __main halt"
expect_failure = {}
max_cycles = 3000000
reference = "Pinned Neptune0.15.1 revision9869b5e35b659dc520fad51ba5a9c812fed46db0 HardforkGamma SingleProof generated independently by tools/neptune-policy-oracle/examples/single_proof.rs. Complete empty transaction includes four integrity/collector proofs and mandatory native currency proof; fixed program, nativeversion5, reversed kernel and empty output authenticated in VM. Mutated cases bypass host validation deliberately."
"#,fields(&public), name!="valid")).unwrap();
    }
    let assembly=format!("// Complete pinned Neptune0.15.1 HardforkGamma SingleProof verifier.\n__main: read_io 5 call {} push 1 write_io 1 return\n{}\n{}",recursive::neptune::TRANSACTION_ENTRYPOINT,recursive::neptune::protocol_assembly(recursive::neptune::TRANSACTION_ENTRYPOINT).unwrap(),recursive::assembly());
    std::fs::write(
        root.join("baselines/triton/os/neptune/programs/transaction_validation.tasm"),
        assembly,
    )
    .unwrap();
    println!("Generated real whole-transaction positive fixture and four adversarial claims; run bench to validate compiled SDK and manual entry.");
}
