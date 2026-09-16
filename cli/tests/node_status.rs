#![cfg(unix)]
use std::{os::unix::fs::PermissionsExt, process::Command};

#[test]
fn successful_cli_exit_without_a_node_reply_is_a_failed_status() {
    let directory = std::env::temp_dir().join(format!("trisha-node-status-{}", std::process::id()));
    std::fs::create_dir_all(&directory).unwrap();
    struct Cleanup(std::path::PathBuf);
    impl Drop for Cleanup {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
    let _cleanup = Cleanup(directory.clone());
    let executable = directory.join("neptune-cli");
    std::fs::write(&executable, "#!/bin/sh\nprintf '%s\\n' 'This command requires a connection to `neptune-core`, but that connection could not be established. Is `neptune-core` running?'\nexit 0\n").unwrap();
    std::fs::set_permissions(&executable, std::fs::Permissions::from_mode(0o755)).unwrap();
    let run = || {
        Command::new(env!("CARGO_BIN_EXE_trisha"))
            .env("PATH", &directory)
            .args(["node", "status"])
            .output()
            .unwrap()
    };
    let offline = run();
    assert!(!offline.status.success());
    assert!(offline.stdout.is_empty());
    assert!(String::from_utf8_lossy(&offline.stderr).contains("could not be established"));
    std::fs::write(&executable, "#!/bin/sh\ncase \"$3\" in\nblock-height) printf '123\\n';;\nmempool-tx-count) printf '7\\n';;\npeer-info) printf 'peer fixture\\n';;\nesac\n").unwrap();
    let connected = run();
    assert!(
        connected.status.success(),
        "{}",
        String::from_utf8_lossy(&connected.stderr)
    );
    let output = String::from_utf8_lossy(&connected.stdout);
    assert!(output.contains("Block height : 123"));
    assert!(output.contains("Mempool txs  : 7"));
    std::fs::write(&executable, "#!/bin/sh\nprintf 'not-a-height\\n'\n").unwrap();
    assert!(!run().status.success());
}
