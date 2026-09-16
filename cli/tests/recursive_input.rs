#![cfg(feature = "triton")]
use std::path::PathBuf;
use std::process::{Command, Output};

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        static NEXT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
        let dir = std::env::temp_dir().join(format!(
            "trisha-recursive-cli-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
        ));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(
            dir.join("inner.tri"),
            "program inner\nfn main() { pub_write(pub_read()+3) }\n",
        )
        .unwrap();
        std::fs::write(
            dir.join("inner.json"),
            r#"{"schema_version":1,"public":["2"],"secret":[],"digests":[]}"#,
        )
        .unwrap();
        Self(dir)
    }
    fn run(&self, args: &[&str]) -> Output {
        Command::new(env!("CARGO_BIN_EXE_trisha"))
            .current_dir(&self.0)
            .env("RAYON_NUM_THREADS", "4")
            .args(args)
            .output()
            .unwrap()
    }
    fn pass(&self, args: &[&str]) -> Output {
        let result = self.run(args);
        assert!(
            result.status.success(),
            "{args:?}: {}",
            String::from_utf8_lossy(&result.stderr)
        );
        result
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn large_recursive_witness_runs_from_file_and_expected_claim_is_mandatory() {
    let f = Fixture::new();
    f.pass(&[
        "prove",
        "inner.tri",
        "--input-file",
        "inner.json",
        "--output",
        "inner.proof.toml",
    ]);
    // This proof was generated inside the fixture from its controlled source/input.
    // Application callers instead supply an independently authorized expected claim.
    let proof: toml::Value =
        toml::from_str(&std::fs::read_to_string(f.0.join("inner.proof.toml")).unwrap()).unwrap();
    let expected = serde_json::json!({"schema_version":1,"program_hash":proof["claim"]["program_hash"],"public_input":["2"],"public_output":["5"]});
    std::fs::write(
        f.0.join("expected.json"),
        serde_json::to_vec(&expected).unwrap(),
    )
    .unwrap();
    f.pass(&[
        "witness",
        "inner.proof.toml",
        "--expected-claim",
        "expected.json",
        "--output",
        "witness.json",
    ]);
    assert!(
        std::fs::metadata(f.0.join("witness.json")).unwrap().len() > 262144,
        "fixture must exceed typical argv capacity"
    );
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        assert_eq!(
            std::fs::metadata(f.0.join("witness.json"))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
    }
    std::fs::write(f.0.join("outer.tri"),"program outer\nuse vm.triton.proof\nuse vm.io.io\nfn main() { proof.verify(io.read_digest()) pub_write(1) }\n").unwrap();
    let output = f.pass(&["run", "outer.tri", "--input-file", "witness.json"]);
    assert_eq!(String::from_utf8(output.stdout).unwrap().trim(), "1");
    let mut witness: serde_json::Value =
        serde_json::from_slice(&std::fs::read(f.0.join("witness.json")).unwrap()).unwrap();
    let old = witness["public"][0]
        .as_str()
        .unwrap()
        .parse::<u64>()
        .unwrap();
    witness["public"][0] = serde_json::json!(((old + 1) % 18_446_744_069_414_584_321).to_string());
    std::fs::write(
        f.0.join("changed.json"),
        serde_json::to_vec(&witness).unwrap(),
    )
    .unwrap();
    let rejected = f.run(&["run", "outer.tri", "--input-file", "changed.json"]);
    assert!(!rejected.status.success());
    assert!(String::from_utf8_lossy(&rejected.stderr).contains("program rejected private witness"));
    let mut wrong = expected;
    wrong["public_output"] = serde_json::json!(["6"]);
    std::fs::write(f.0.join("wrong.json"), serde_json::to_vec(&wrong).unwrap()).unwrap();
    assert!(!f
        .run(&[
            "witness",
            "inner.proof.toml",
            "--expected-claim",
            "wrong.json",
            "--output",
            "bad.json"
        ])
        .status
        .success());
    assert!(!f.0.join("bad.json").exists());
}

#[test]
fn file_inputs_work_for_batches_and_reject_conflicts_and_noncanonical_fields() {
    let f = Fixture::new();
    std::fs::write(
        f.0.join("inner.tasm"),
        "read_io 1 push 3 add write_io 1 halt",
    )
    .unwrap();
    assert_eq!(
        String::from_utf8(
            f.pass(&["run", "--tasm", "inner.tasm", "--input-file", "inner.json"])
                .stdout
        )
        .unwrap()
        .trim(),
        "5"
    );
    f.pass(&[
        "prove",
        "--tasm",
        "inner.tasm",
        "--input-file",
        "inner.json",
        "--output",
        "raw.proof.toml",
    ]);
    f.pass(&["run", "batch", "inner.tri", "--input-file", "inner.json"]);
    f.pass(&[
        "prove",
        "batch",
        "inner.tri",
        "--input-file",
        "inner.json",
        "--output",
        "proofs",
        "--max-parallel",
        "1",
    ]);
    for args in [
        vec![
            "run",
            "inner.tri",
            "--input-file",
            "inner.json",
            "--secret",
            "1",
        ],
        vec![
            "prove",
            "inner.tri",
            "--input-file",
            "inner.json",
            "--input-values",
            "2",
        ],
        vec![
            "run",
            "batch",
            "inner.tri",
            "--input-file",
            "inner.json",
            "--digests",
            "1,2,3,4,5",
        ],
        vec![
            "prove",
            "batch",
            "inner.tri",
            "--input-file",
            "inner.json",
            "--secret",
            "1",
        ],
    ] {
        assert!(!f.run(&args).status.success());
    }
    for invalid in [
        r#"{"schema_version":2,"public":[],"secret":[],"digests":[]}"#,
        r#"{"schema_version":1,"public":["18446744069414584321"],"secret":[],"digests":[]}"#,
        r#"{"schema_version":1,"public":[],"secret":[],"digests":[[1,2,3,4]]}"#,
        r#"{"schema_version":1,"public":[],"secret":[],"digests":[],"expected_failure":true}"#,
    ] {
        std::fs::write(f.0.join("invalid.json"), invalid).unwrap();
        assert!(!f
            .run(&["run", "inner.tri", "--input-file", "invalid.json"])
            .status
            .success());
    }
    let huge = std::fs::File::create(f.0.join("huge.json")).unwrap();
    huge.set_len(64 * 1024 * 1024 + 1).unwrap();
    let rejected = f.run(&["run", "inner.tri", "--input-file", "huge.json"]);
    assert!(!rejected.status.success());
    assert!(String::from_utf8_lossy(&rejected.stderr).contains("64MiB"));
}

#[test]
fn fixed_neptune_policy_witnesses_bind_real_proofs_to_caller_commitments() {
    use base64::Engine;
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap();
    let cases = [
        (
            "neptune-transaction",
            "neptune-transaction/valid.bench.toml",
            trisha_rs::recursive::neptune::SINGLE_PROOF_PROGRAM,
        ),
        (
            "neptune-native-currency",
            "neptune-native-currency/vector.bench.toml",
            trisha_rs::recursive::neptune::NATIVE_CURRENCY_PROGRAM,
        ),
    ];
    for (policy, fixture_name, program_hash) in cases {
        let f = Fixture::new();
        let fixture_path = root.join("baselines/triton/fixtures").join(fixture_name);
        let fixture: toml::Value =
            toml::from_str(&std::fs::read_to_string(&fixture_path).unwrap()).unwrap();
        let public: Vec<u64> = fixture["input"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap().parse().unwrap())
            .collect();
        let witness_path = fixture_path
            .parent()
            .unwrap()
            .join(fixture["witness_files"][0].as_str().unwrap());
        let witness: toml::Value =
            toml::from_str(&std::fs::read_to_string(witness_path).unwrap()).unwrap();
        let secret: Vec<u64> = witness["secret"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap().parse().unwrap())
            .collect();
        let offset = 2 + secret[1] as usize;
        let length = secret[offset] as usize;
        assert_eq!(secret[offset + 1] + 1, length as u64);
        // BFieldCodec adds a struct-size word before the Vec length; the fixed
        // native wire codec starts at that Vec length, not at the struct prefix.
        assert_eq!(secret[offset + 2] + 2, length as u64);
        let bytes: Vec<u8> = secret[offset + 2..offset + 1 + length]
            .iter()
            .flat_map(|v| v.to_le_bytes())
            .collect();
        let input: Vec<_> = public
            .chunks_exact(5)
            .flat_map(|chunk| chunk.iter().rev().map(u64::to_string))
            .collect();
        // Native TOML values keep integer metadata independent of serde_json's
        // arbitrary_precision feature, which is required by Neptune RPC i128.
        let mut proof: toml::Value = r#"
[proof]
format = "stark-triton-v7"
program_name = "independent-policy-reference"
cycle_count = 0
padded_height = 0
proving_time_ms = 0
[claim]
program_hash = []
public_input = []
public_output = []
[data]
proof = ""
"#
        .parse()
        .unwrap();
        proof["claim"]["program_hash"] = toml::Value::Array(
            program_hash
                .into_iter()
                .map(|v| toml::Value::String(v.to_string()))
                .collect(),
        );
        proof["claim"]["public_input"] =
            toml::Value::Array(input.into_iter().map(toml::Value::String).collect());
        proof["data"]["proof"] =
            toml::Value::String(base64::engine::general_purpose::STANDARD.encode(bytes));
        std::fs::write(f.0.join("policy.toml"), toml::to_string(&proof).unwrap()).unwrap();
        let mut commitments = serde_json::json!({"schema_version":1,"kernel":public[..5]});
        if public.len() == 15 {
            commitments["inputs"] = serde_json::json!(public[5..10]);
            commitments["outputs"] = serde_json::json!(public[10..15]);
        }
        std::fs::write(
            f.0.join("commitments.json"),
            serde_json::to_vec(&commitments).unwrap(),
        )
        .unwrap();
        f.pass(&[
            "witness",
            "policy.toml",
            "--policy",
            policy,
            "--commitments",
            "commitments.json",
            "--output",
            "policy-input.json",
        ]);
        let document: serde_json::Value =
            serde_json::from_slice(&std::fs::read(f.0.join("policy-input.json")).unwrap()).unwrap();
        let actual: Vec<u64> = document["public"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap().parse().unwrap())
            .collect();
        assert_eq!(
            actual, public,
            "protocol source receives caller commitments, not the generic full-claim hash"
        );
        let source = fixture_path
            .parent()
            .unwrap()
            .join(fixture["source"].as_str().unwrap());
        f.pass(&[
            "run",
            source.to_str().unwrap(),
            "--target",
            "neptune",
            "--input-file",
            "policy-input.json",
        ]);
        commitments["kernel"][0] =
            serde_json::json!((public[0] + 1) % 18_446_744_069_414_584_321u64);
        std::fs::write(
            f.0.join("changed.json"),
            serde_json::to_vec(&commitments).unwrap(),
        )
        .unwrap();
        let changed = f.run(&[
            "witness",
            "policy.toml",
            "--policy",
            policy,
            "--commitments",
            "changed.json",
            "--output",
            "invalid.json",
        ]);
        assert!(!changed.status.success());
        assert!(!f.0.join("invalid.json").exists());
        let conflict = f.run(&[
            "witness",
            "policy.toml",
            "--policy",
            policy,
            "--commitments",
            "commitments.json",
            "--expected-claim",
            "commitments.json",
            "--output",
            "conflict.json",
        ]);
        assert!(!conflict.status.success());
        assert!(!f.0.join("conflict.json").exists());
        commitments["kernel"] = serde_json::json!(["18446744069414584321", "0", "0", "0", "0"]);
        std::fs::write(
            f.0.join("noncanonical.json"),
            serde_json::to_vec(&commitments).unwrap(),
        )
        .unwrap();
        assert!(!f
            .run(&[
                "witness",
                "policy.toml",
                "--policy",
                policy,
                "--commitments",
                "noncanonical.json",
                "--output",
                "alias.json"
            ])
            .status
            .success());
        assert!(!f.0.join("alias.json").exists());
    }
}
