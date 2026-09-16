#![cfg(all(feature = "triton", unix))]
use std::path::PathBuf;
use std::process::{Command, Output, Stdio};
use std::time::{Duration, Instant};

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!("trisha-input-kind-{}", std::process::id()));
        std::fs::create_dir(&path).unwrap();
        std::fs::write(
            path.join("entry.tri"),
            "program entry\nfn main(){pub_write(pub_read()+3)}\n",
        )
        .unwrap();
        std::fs::write(
            path.join("valid.json"),
            r#"{"schema_version":1,"public":[2],"secret":[],"digests":[]}"#,
        )
        .unwrap();
        Self(path)
    }
    fn invoke(&self, args: &[&str]) -> Output {
        let mut child = Command::new(env!("CARGO_BIN_EXE_trisha"))
            .current_dir(&self.0)
            .args(args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let deadline = Instant::now() + Duration::from_secs(3);
        loop {
            if child.try_wait().unwrap().is_some() {
                return child.wait_with_output().unwrap();
            }
            if Instant::now() >= deadline {
                child.kill().unwrap();
                let output = child.wait_with_output().unwrap();
                panic!(
                    "CLI blocked on input path: {args:?}; {}",
                    String::from_utf8_lossy(&output.stderr)
                );
            }
            std::thread::sleep(Duration::from_millis(10));
        }
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn cli_file_readers_reject_special_paths_without_blocking_and_keep_regular_inputs() {
    let f = Fixture::new();
    assert!(Command::new("mkfifo")
        .arg(f.0.join("fifo"))
        .status()
        .unwrap()
        .success());
    std::fs::create_dir(f.0.join("directory")).unwrap();
    std::os::unix::fs::symlink("valid.json", f.0.join("link.json")).unwrap();
    std::os::unix::fs::symlink("fifo", f.0.join("link-fifo")).unwrap();
    for path in ["fifo", "directory", "link.json", "link-fifo"] {
        for args in [
            vec!["run", "entry.tri", "--input-file", path],
            vec!["verify", path],
        ] {
            let result = f.invoke(&args);
            assert!(!result.status.success());
            assert!(
                String::from_utf8_lossy(&result.stderr).contains("regular file"),
                "{}",
                String::from_utf8_lossy(&result.stderr)
            );
        }
    }
    let valid = f.invoke(&["run", "entry.tri", "--input-file", "valid.json"]);
    assert!(
        valid.status.success(),
        "{}",
        String::from_utf8_lossy(&valid.stderr)
    );
    assert_eq!(String::from_utf8(valid.stdout).unwrap().trim(), "5");
    const SECRET: &str = "private_witness_must_not_appear_in_diagnostics";
    std::fs::write(
        f.0.join("invalid.json"),
        format!("{{\"secret\":\"{SECRET}\""),
    )
    .unwrap();
    std::fs::write(
        f.0.join("invalid.toml"),
        format!("secret = '{SECRET}'\n[broken"),
    )
    .unwrap();
    std::fs::write(f.0.join("invalid-utf8.toml"), [255, 254]).unwrap();
    for args in [
        vec!["run", "entry.tri", "--input-file", "invalid.json"],
        vec!["verify", "invalid.toml"],
        vec!["verify", "invalid-utf8.toml"],
    ] {
        let rejected = f.invoke(&args);
        assert!(!rejected.status.success());
        assert!(!String::from_utf8_lossy(&rejected.stderr).contains(SECRET));
    }
    std::fs::File::create(f.0.join("oversized"))
        .unwrap()
        .set_len(64 * 1024 * 1024 + 1)
        .unwrap();
    for args in [
        vec!["run", "entry.tri", "--input-file", "oversized"],
        vec!["verify", "oversized"],
    ] {
        let rejected = f.invoke(&args);
        assert!(!rejected.status.success());
        assert!(String::from_utf8_lossy(&rejected.stderr).contains("64MiB"));
    }
}
