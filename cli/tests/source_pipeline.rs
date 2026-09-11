#![cfg(feature = "triton")]
use std::path::PathBuf;
use std::process::{Command, Output};

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        static NEXT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
        let id = NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let dir = std::env::temp_dir().join(format!("trisha-cli-{}-{}", std::process::id(), id));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(
            dir.join("main.tri"),
            "program main\nfn main() { let x = pub_read()\n pub_write(x + 7) }\n",
        )
        .unwrap();
        Self(dir)
    }
    fn run(&self, args: &[&str]) -> Output {
        Command::new(env!("CARGO_BIN_EXE_trisha"))
            .current_dir(&self.0)
            .args(args)
            .output()
            .unwrap()
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn source_cli_executes_proves_and_rejects_tampered_claim() {
    let f = Fixture::new();
    let run = f.run(&["run", "main.tri", "--input-values", "5"]);
    assert!(
        run.status.success(),
        "{}",
        String::from_utf8_lossy(&run.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&run.stdout).trim(), "12");
    let prove = f.run(&[
        "prove",
        "main.tri",
        "--input-values",
        "5",
        "--output",
        "proof.toml",
    ]);
    assert!(
        prove.status.success(),
        "{}",
        String::from_utf8_lossy(&prove.stderr)
    );
    assert!(f.run(&["verify", "proof.toml"]).status.success());
    let path = f.0.join("proof.toml");
    let text = std::fs::read_to_string(&path).unwrap();
    let altered = text.replace("public_output = [\"12\"]", "public_output = [\"13\"]");
    assert_ne!(altered, text);
    std::fs::write(path, altered).unwrap();
    assert!(!f.run(&["verify", "proof.toml"]).status.success());
}

#[test]
fn unsupported_targets_digests_and_deployment_fail() {
    let f = Fixture::new();
    for target in ["nox", "tritno", "../../triton"] {
        assert!(!f
            .run(&["build", "main.tri", "--target", target])
            .status
            .success());
        assert!(!f.0.join("main.tasm").exists());
    }
    assert!(!f
        .run(&["run", "main.tri", "--digests", "1,2,3"])
        .status
        .success());
    assert!(!f.run(&["deploy", "main.tri"]).status.success());
    assert!(f.run(&["deploy", "main.tri", "--dry-run"]).status.success());
}

#[test]
fn duplicate_batch_destinations_fail_before_writing_proofs() {
    let f = Fixture::new();
    std::fs::create_dir(f.0.join("other")).unwrap();
    std::fs::copy(f.0.join("main.tri"), f.0.join("other/main.tri")).unwrap();
    let result = f.run(&[
        "prove",
        "batch",
        "main.tri",
        "other/main.tri",
        "--output",
        "proofs",
    ]);
    assert!(!result.status.success());
    assert!(String::from_utf8_lossy(&result.stderr).contains("collision"));
    assert!(!f.0.join("proofs/main.proof.toml").exists());
}

#[test]
fn embedded_libraries_and_project_profiles_work_outside_checkout() {
    let f = Fixture::new();
    std::fs::write(f.0.join("trident.toml"), "[project]\nname = \"isolated\"\nentry = \"main.tri\"\n[targets.release]\nflags = [\"selected\"]\n").unwrap();
    std::fs::write(f.0.join("main.tri"), "program isolated\nuse vm.core.convert\nuse os.neptune.xfield\n#[cfg(selected)]\nfn chosen() -> Field { 38 }\n#[cfg(not(selected))]\nfn chosen() -> Field { 99 }\nfn main() { pub_write(convert.as_field(convert.as_u32(chosen()))) }\n").unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_trisha"))
        .current_dir(&f.0)
        .env_remove("TRIDENT_STDLIB")
        .env_remove("TRIDENT_OSLIB")
        .env_remove("TRIDENT_EXTLIB")
        .args(["run", ".", "--target", "neptune", "--profile", "release"])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "38");
}
