#![cfg(feature = "triton")]
use std::process::Command;

#[test]
fn dry_run_reports_an_offline_native_program_plan_and_resolved_rpc_selection() {
    let dir = std::env::temp_dir().join(format!("trisha-deploy-inspect-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    struct Cleanup(std::path::PathBuf);
    impl Drop for Cleanup {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
    let _cleanup = Cleanup(dir.clone());
    std::fs::write(
        dir.join("main.tri"),
        "program main\nfn main() { pub_write(7) }\n",
    )
    .unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_trisha"))
        .current_dir(&dir)
        .args([
            "deploy",
            "main.tri",
            "--dry-run",
            "--state",
            "testnet",
            "--rpc-port",
            "19001",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let plan: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(plan["format"], "trisha-neptune-program-plan-v1");
    assert_eq!(plan["state"], "testnet");
    assert_eq!(plan["rpc_port"], 19001);
    assert_eq!(plan["lock_script_hash"].as_array().unwrap().len(), 5);
    for word in plan["lock_script_hash"].as_array().unwrap() {
        assert!(word.as_str().unwrap().parse::<u64>().is_ok());
    }
    assert_eq!(plan["execution_proof_verified"], false);
    assert_eq!(plan["submission_supported"], false);
    assert!(plan["transaction"].is_null());
    let batch = Command::new(env!("CARGO_BIN_EXE_trisha"))
        .current_dir(&dir)
        .args(["deploy", "batch", "main.tri", "--dry-run"])
        .output()
        .unwrap();
    assert!(
        batch.status.success(),
        "{}",
        String::from_utf8_lossy(&batch.stderr)
    );
    serde_json::from_slice::<serde_json::Value>(&batch.stdout).unwrap();
    let diagnostics = String::from_utf8_lossy(&batch.stderr);
    assert!(diagnostics.contains("1/1 inspected"));
    assert!(!diagnostics.contains("deployed"));
}
