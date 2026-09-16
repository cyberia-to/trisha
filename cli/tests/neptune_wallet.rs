#![cfg(unix)]
use std::{
    fs,
    io::Write,
    os::unix::fs::{symlink, PermissionsExt},
    path::PathBuf,
    process::{Command, Output, Stdio},
    sync::atomic::{AtomicU64, Ordering},
};
static NEXT: AtomicU64 = AtomicU64::new(0);
struct Fixture {
    root: PathBuf,
}
impl Fixture {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "trisha-wallet-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&root).unwrap();
        let root = root.canonicalize().unwrap();
        fs::create_dir_all(root.join("data")).unwrap();
        let executable = root.join("neptune-cli");
        fs::write(
            &executable,
            r#"#!/bin/sh
printf '%s|' "$@" >> "$WLOG"
printf '\n' >> "$WLOG"
data=''
while [ "$1" = '--data-dir' ] || [ "$1" = '--port' ]; do
 if [ "$1" = '--data-dir' ]; then data="$2"; fi
 shift 2
done
cmd="$1"; shift
case "$cmd" in
network) printf '%s\n' "${NODE_NETWORK:-testnet-0}";;
get-derivation-index) printf '%s\n' "${LAST_INDEX:-2}";;
nth-receiving-address) printf 'mock-address-%s\n' "$1";;
next-receiving-address) printf 'mock-next-address\n';;
which-wallet)
 wallet="${WALLET_PATH:-$data/$2/wallet/wallet.dat}"
 if [ -f "$wallet" ]; then printf '%s\n' "$wallet"; fi;;
generate-wallet|import-seed-phrase)
 if [ "$cmd" = 'import-seed-phrase' ]; then IFS= read -r private_input; fi
 if [ "${FAIL_ZERO:-0}" = 1 ]; then printf 'Failed to import seed phrase.\n'; exit 0; fi
 /bin/mkdir -p "$data/$2/wallet"
 printf 'mock wallet, no real funds\n' > "$data/$2/wallet/wallet.dat"
 printf 'New wallet generated.\n';;
*) exit 9;;
esac
"#,
        )
        .unwrap();
        fs::set_permissions(executable, fs::Permissions::from_mode(0o755)).unwrap();
        Self { root }
    }
    fn command(&self, args: &[&str]) -> Command {
        let mut c = Command::new(env!("CARGO_BIN_EXE_trisha"));
        c.args(["neuron", "--state", "testnet"])
            .args(args)
            .env("PATH", &self.root)
            .env("HOME", &self.root)
            .env("NEPTUNE_DATA_DIR", self.root.join("data"))
            .env("TRISHA_CONFIG_DIR", self.root.join("config"))
            .env("WLOG", self.root.join("calls"));
        c
    }
    fn run(&self, args: &[&str]) -> Output {
        self.command(args).output().unwrap()
    }
    fn log(&self) -> String {
        fs::read_to_string(self.root.join("calls")).unwrap_or_default()
    }
    fn wallet(&self, network: &str) -> PathBuf {
        self.root
            .join("data")
            .join(network)
            .join("wallet/wallet.dat")
    }
    fn existing(&self, network: &str) {
        let p = self.wallet(network);
        fs::create_dir_all(p.parent().unwrap()).unwrap();
        fs::write(p, "fixture").unwrap();
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}
fn success(out: Output) -> Output {
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    out
}
#[test]
fn indexed_addresses_are_offline_and_pass_key_network_and_data_directory() {
    let f = Fixture::new();
    success(f.run(&["address", "add", "--index", "42"]));
    assert!(f
        .log()
        .contains("nth-receiving-address|42|generation|--network|testnet-0|"));
    assert!(!f.log().contains("--port"));
    assert!(f.log().starts_with("--data-dir|"));
    let before = f.log();
    assert!(!f
        .run(&["address", "add", "--key-type", "symmetric"])
        .status
        .success());
    assert_eq!(before, f.log());
}
#[test]
fn listing_is_bounded_even_for_maximum_remote_counter_and_checks_network() {
    let f = Fixture::new();
    let out = success(
        f.command(&["address", "list", "--start", "8", "--limit", "3"])
            .env("LAST_INDEX", u64::MAX.to_string())
            .output()
            .unwrap(),
    );
    assert_eq!(String::from_utf8_lossy(&out.stdout).lines().count(), 3);
    assert_eq!(f.log().matches("nth-receiving-address").count(), 3);
    let before = f.log();
    assert!(!f
        .run(&["address", "list", "--limit", "1001"])
        .status
        .success());
    assert_eq!(before, f.log());
    assert!(!f
        .command(&["address", "add"])
        .env("NODE_NETWORK", "main")
        .output()
        .unwrap()
        .status
        .success());
    assert!(!f.log().contains("next-receiving-address"));
    if cfg!(target_pointer_width = "64") {
        let edge = Fixture::new();
        success(
            edge.command(&[
                "address",
                "list",
                "--start",
                "18446744073709551615",
                "--limit",
                "3",
            ])
            .env("LAST_INDEX", u64::MAX.to_string())
            .output()
            .unwrap(),
        );
        assert_eq!(edge.log().matches("nth-receiving-address").count(), 1);
    }
}
#[test]
fn create_checks_wallet_appearance_and_never_labels_status_as_a_seed() {
    let f = Fixture::new();
    let out = success(f.run(&["create"]));
    assert!(f.wallet("testnet-0").is_file());
    assert!(!f.wallet("main").exists());
    let text = format!(
        "{}{}",
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr)
    );
    assert!(!text.contains("SEED PHRASE"));
    assert!(!text.contains("New wallet generated"));
    assert!(f.log().contains("generate-wallet|--network|testnet-0|"));
    assert!(!f.run(&["create"]).status.success());
    assert_eq!(f.log().matches("generate-wallet").count(), 1);
    let fail = Fixture::new();
    assert!(!fail
        .command(&["create"])
        .env("FAIL_ZERO", "1")
        .output()
        .unwrap()
        .status
        .success());
    assert!(!fail.wallet("testnet-0").exists());
}
#[test]
fn import_uses_inherited_stdin_without_seed_arguments_or_echo() {
    let f = Fixture::new();
    let mut c = f.command(&["import"]);
    let mut child = c
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(b"private-test-words\n")
        .unwrap();
    let out = success(child.wait_with_output().unwrap());
    assert!(f.wallet("testnet-0").exists());
    assert!(f.log().contains("import-seed-phrase|--network|testnet-0|"));
    for text in [
        f.log(),
        String::from_utf8_lossy(&out.stdout).into_owned(),
        String::from_utf8_lossy(&out.stderr).into_owned(),
    ] {
        assert!(!text.contains("private-test-words"));
    }
    let reject = Fixture::new();
    let out = reject.run(&["import", "do-not-echo-this"]);
    assert!(!out.status.success());
    assert!(!String::from_utf8_lossy(&out.stderr).contains("do-not-echo-this"));
    assert!(reject.log().is_empty());
    let fail = Fixture::new();
    assert!(!fail
        .command(&["import"])
        .env("FAIL_ZERO", "1")
        .stdin(Stdio::null())
        .output()
        .unwrap()
        .status
        .success());
}
#[test]
fn removal_requires_confirmation_and_only_removes_the_selected_wallet() {
    let f = Fixture::new();
    f.existing("testnet-0");
    f.existing("main");
    success(f.run(&["remove"]));
    assert!(f.wallet("testnet-0").exists());
    success(f.run(&["remove", "--confirm"]));
    assert!(!f.wallet("testnet-0").exists());
    assert!(f.wallet("main").exists());
}
#[test]
fn removal_rejects_wrong_network_and_symlink_paths() {
    let f = Fixture::new();
    f.existing("main");
    assert!(!f
        .command(&["remove", "--confirm"])
        .env("WALLET_PATH", f.wallet("main"))
        .output()
        .unwrap()
        .status
        .success());
    assert!(f.wallet("main").exists());
    let dir = f.wallet("testnet-0").parent().unwrap().to_owned();
    fs::create_dir_all(dir.parent().unwrap()).unwrap();
    symlink(f.wallet("main").parent().unwrap(), &dir).unwrap();
    assert!(!f.run(&["remove", "--confirm"]).status.success());
    assert!(f.wallet("main").exists());
}
#[test]
fn hidden_addresses_are_separate_by_network() {
    let f = Fixture::new();
    success(f.run(&["address", "hide", "mock-address-0"]));
    assert!(f.root.join("config/testnet-0/hidden_addresses").exists());
    assert!(!f.root.join("config/main/hidden_addresses").exists());
}

#[test]
fn removal_uses_upstream_wallet_path_without_guessing_platform_directory() {
    let f = Fixture::new();
    f.existing("testnet-0");
    let out = f
        .command(&["remove", "--confirm"])
        .env_remove("NEPTUNE_DATA_DIR")
        .env("WALLET_PATH", f.wallet("testnet-0"))
        .output()
        .unwrap();
    success(out);
    assert!(!f.wallet("testnet-0").exists());
    assert!(!f.log().contains("--data-dir"));
}
