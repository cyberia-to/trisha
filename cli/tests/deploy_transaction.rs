#![cfg(feature = "triton")]
use std::{
    fs,
    path::{Path, PathBuf},
    process::{Command, Output},
    sync::atomic::{AtomicUsize, Ordering},
};
fn directory() -> PathBuf {
    static COUNT: AtomicUsize = AtomicUsize::new(0);
    let p = std::env::temp_dir().join(format!(
        "trisha-deploy-{}-{}",
        std::process::id(),
        COUNT.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&p).unwrap();
    p
}
fn cli(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_trisha"))
        .args(args)
        .output()
        .unwrap()
}
fn text(p: &Path) -> &str {
    p.to_str().unwrap()
}
#[test]
fn output_construction_is_offline_private_and_cannot_overwrite() {
    let dir = directory();
    let source = dir.join("lock.tri");
    let spec = dir.join("spec.json");
    let output = dir.join("output.json");
    fs::write(
        &source,
        "program lock\nfn main() { assert(pub_read() == 7) }\n",
    )
    .unwrap();
    fs::write(
        &spec,
        r#"{"coins":[],"sender_randomness":[1,2,3,4,5],"receiver_digest":[6,7,8,9,10]}"#,
    )
    .unwrap();
    let args = [
        "deploy",
        "output",
        text(&source),
        "--spec",
        text(&spec),
        "--output",
        text(&output),
    ];
    let result = cli(&args);
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let receipt: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(receipt["submitted"], false);
    assert_eq!(receipt["transaction_proved"], false);
    let bytes = fs::read(&output).unwrap();
    let value: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(value["intent"]["compiled_lock"], true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        assert_eq!(
            fs::metadata(&output).unwrap().permissions().mode() & 0o777,
            0o600
        );
    }
    assert!(!cli(&args).status.success());
    assert_eq!(fs::read(&output).unwrap(), bytes);
    fs::write(&spec,r#"{"coins":[],"sender_randomness":[18446744073709551615,2,3,4,5],"receiver_digest":[6,7,8,9,10]}"#).unwrap();
    fs::remove_file(&output).unwrap();
    assert!(!cli(&args).status.success());
    assert!(!output.exists());
    fs::remove_dir_all(dir).unwrap();
}

#[test]
#[ignore = "requires generated canonical custom-lock SingleProof deployment intent"]
fn genuine_transaction_prepare_and_mock_gateway_process() {
    use std::{
        io::{Read, Write},
        net::TcpListener,
        thread,
        time::Duration,
    };
    let intent = std::env::var("TRISHA_DEPLOY_INTENT").expect("TRISHA_DEPLOY_INTENT required");
    let source =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../neptune/tests/fixtures/custom_lock.tri");
    let dir = directory();
    let artifact = dir.join("prepared.json");
    let result = cli(&[
        "deploy",
        "prepare",
        text(&source),
        "--intent",
        &intent,
        "--output",
        text(&artifact),
        "--state",
        "local-testnet1",
    ]);
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let prepared: serde_json::Value =
        serde_json::from_slice(&fs::read(&artifact).unwrap()).unwrap();
    assert_eq!(prepared["single_proof_verified"], true);
    assert_eq!(prepared["current_chain_admission_checked"], false);
    let mut wrong: serde_json::Value = serde_json::from_slice(&fs::read(&intent).unwrap()).unwrap();
    wrong["expected_kernel"][0] =
        serde_json::json!(wrong["expected_kernel"][0].as_u64().unwrap() ^ 1);
    let wrong_path = dir.join("wrong-intent.json");
    fs::write(&wrong_path, serde_json::to_vec(&wrong).unwrap()).unwrap();
    let wrong_artifact = dir.join("rejected.json");
    assert!(!cli(&[
        "deploy",
        "prepare",
        text(&source),
        "--intent",
        text(&wrong_path),
        "--output",
        text(&wrong_artifact),
        "--state",
        "local-testnet1"
    ])
    .status
    .success());
    assert!(!wrong_artifact.exists());
    for accepted in [true, false] {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint = format!("http://{}", listener.local_addr().unwrap());
        let expected = prepared["rpc_request"].clone();
        let server = thread::spawn(move || {
            let (mut socket, _) = listener.accept().unwrap();
            socket
                .set_read_timeout(Some(Duration::from_secs(30)))
                .unwrap();
            let mut bytes = Vec::new();
            let mut buf = [0; 65536];
            loop {
                let n = socket.read(&mut buf).unwrap();
                assert_ne!(n, 0);
                bytes.extend_from_slice(&buf[..n]);
                if let Some(end) = bytes.windows(4).position(|v| v == b"\r\n\r\n") {
                    let headers = std::str::from_utf8(&bytes[..end]).unwrap();
                    let size: usize = headers
                        .lines()
                        .find_map(|line| {
                            line.to_ascii_lowercase()
                                .strip_prefix("content-length: ")
                                .map(|v| v.parse().unwrap())
                        })
                        .unwrap();
                    if bytes.len() >= end + 4 + size {
                        assert!(headers.contains("Authorization: Bearer process-mock-only"));
                        assert_eq!(
                            serde_json::from_slice::<serde_json::Value>(&bytes[end + 4..]).unwrap(),
                            expected
                        );
                        break;
                    }
                }
                assert!(bytes.len() < 64 * 1024 * 1024);
            }
            let body = serde_json::json!({"jsonrpc":"2.0","id":1,"result":{"success":accepted}})
                .to_string();
            write!(
                socket,
                "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(),
                body
            )
            .unwrap();
        });
        let auth = dir.join("gateway.json");
        fs::write(&auth,serde_json::to_vec(&serde_json::json!({"schema_version":1,"network":"local-testnet1","endpoint":endpoint,"bearer_token":"process-mock-only"})).unwrap()).unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(&auth, fs::Permissions::from_mode(0o600)).unwrap();
        }
        let result = cli(&[
            "deploy",
            "submit",
            text(&source),
            "--intent",
            &intent,
            "--endpoint",
            &endpoint,
            "--auth-file",
            text(&auth),
            "--state",
            "local-testnet1",
        ]);
        assert_eq!(
            result.status.success(),
            accepted,
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        assert!(!String::from_utf8_lossy(&result.stderr).contains("process-mock-only"));
        assert!(!String::from_utf8_lossy(&result.stdout).contains("process-mock-only"));
        server.join().unwrap();
    }
    fs::remove_dir_all(dir).unwrap();
}
