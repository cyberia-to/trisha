use std::path::{Path, PathBuf};
use std::process::Command;

use serde_json::Value;

use crate::error::TrishaError;

pub struct NeptuneClient {
    rpc_port: u16,
    http_rpc_port: u16,
    network: Option<String>,
}

impl NeptuneClient {
    pub fn new(rpc_port: u16) -> Self {
        NeptuneClient {
            rpc_port,
            http_rpc_port: 9797,
            network: None,
        }
    }

    pub fn mining_client(rpc_port: u16, http_rpc_port: u16, network: &str) -> Self {
        let mut client = Self::for_network(rpc_port, network);
        client.http_rpc_port = http_rpc_port;
        client
    }

    pub fn for_network(rpc_port: u16, network: &str) -> Self {
        let mut client = Self::new(rpc_port);
        client.network = Some(network.to_owned());
        client
    }

    fn command(&self) -> Command {
        let mut command = Command::new("neptune-cli");
        if let Some(dir) = std::env::var_os("NEPTUNE_DATA_DIR") {
            command.arg("--data-dir").arg(dir);
        }
        command
    }

    fn network(&self) -> Result<&str, TrishaError> {
        self.network.as_deref().ok_or_else(|| {
            TrishaError::Node("wallet operation requires an explicit network".into())
        })
    }

    fn require_node_network(&self) -> Result<(), TrishaError> {
        if self.run(&["network"])? != self.network()? {
            return Err(TrishaError::Node(
                "node network differs from selected wallet network".into(),
            ));
        }
        Ok(())
    }

    fn run(&self, args: &[&str]) -> Result<String, TrishaError> {
        let output = self
            .command()
            .arg("--port")
            .arg(self.rpc_port.to_string())
            .args(args)
            .output()
            .map_err(|e| {
                if e.kind() == std::io::ErrorKind::NotFound {
                    TrishaError::Node(
                        "neptune-cli not found — install neptune-core and ensure it is in PATH"
                            .to_string(),
                    )
                } else {
                    TrishaError::Node(format!("failed to launch neptune-cli: {}", e))
                }
            })?;

        if output.status.success() {
            let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
            // Upstream prints this diagnostic and exits successfully.
            // A successful child process therefore does not imply an RPC reply.
            if stdout.starts_with("This command requires a connection to `neptune-core`") {
                return Err(TrishaError::Node(stdout));
            }
            Ok(stdout)
        } else {
            let stderr = String::from_utf8_lossy(&output.stderr);
            let stdout = String::from_utf8_lossy(&output.stdout);
            let msg = if !stderr.is_empty() { stderr } else { stdout };
            Err(TrishaError::Node(format!(
                "neptune-cli error: {}",
                msg.trim()
            )))
        }
    }

    pub fn block_height(&self) -> Result<String, TrishaError> {
        self.unsigned_reply("block-height")
    }

    pub fn peer_info(&self) -> Result<String, TrishaError> {
        self.run(&["peer-info"])
    }

    pub fn mempool_tx_count(&self) -> Result<String, TrishaError> {
        self.unsigned_reply("mempool-tx-count")
    }

    fn unsigned_reply(&self, command: &str) -> Result<String, TrishaError> {
        let value = self.run(&[command])?;
        value.parse::<u64>().map_err(|_| {
            TrishaError::Node(format!(
                "neptune-cli {command} did not return an unsigned integer"
            ))
        })?;
        Ok(value)
    }

    pub fn confirmed_balance(&self) -> Result<String, TrishaError> {
        self.require_node_network()?;
        self.run(&["confirmed-available-balance"])
    }

    pub fn unconfirmed_balance(&self) -> Result<String, TrishaError> {
        self.run(&["unconfirmed-available-balance"])
    }

    pub fn next_address(&self, key_type: &str) -> Result<String, TrishaError> {
        validate_key_type(key_type)?;
        self.require_node_network()?;
        self.run(&["next-receiving-address"])
    }

    pub fn address_at_index(&self, index: u64, key_type: &str) -> Result<String, TrishaError> {
        validate_key_type(key_type)?;
        usize::try_from(index)
            .map_err(|_| TrishaError::Node("address index exceeds platform bounds".into()))?;
        let output = self
            .command()
            .args([
                "nth-receiving-address",
                &index.to_string(),
                "generation",
                "--network",
                self.network()?,
            ])
            .output()?;
        if !output.status.success() {
            return Err(TrishaError::Node(
                "offline address derivation failed".into(),
            ));
        }
        let address = String::from_utf8(output.stdout)
            .map_err(|_| TrishaError::Node("invalid address response".into()))?;
        let address = address.trim();
        if address.is_empty() || address.chars().any(char::is_whitespace) {
            return Err(TrishaError::Node(
                "offline command did not return an address".into(),
            ));
        }
        Ok(address.into())
    }

    pub fn list_utxos(&self) -> Result<String, TrishaError> {
        self.require_node_network()?;
        self.run(&["list-coins"])
    }

    pub fn known_keys(&self, start: u64, limit: u16) -> Result<String, TrishaError> {
        if limit == 0 || limit > 1000 {
            return Err(TrishaError::Node(
                "address list limit must be 1..1000".into(),
            ));
        }
        self.require_node_network()?;
        let index = self.run(&["get-derivation-index", "generation"])?;
        let last = index.trim().parse::<u64>().map_err(|_| {
            TrishaError::Node(format!("invalid generation derivation index: {}", index))
        })?;
        let mut addresses = Vec::new();
        for offset in 0..u64::from(limit) {
            let Some(index) = start.checked_add(offset) else {
                break;
            };
            if index > last {
                break;
            }
            addresses.push(self.address_at_index(index, "generation")?);
        }
        Ok(addresses.join("\n"))
    }

    fn rpc_url(&self) -> String {
        format!("http://127.0.0.1:{}/", self.http_rpc_port)
    }

    fn json_call(&self, method: &str, params: Value) -> Result<Value, TrishaError> {
        let body = serde_json::json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        });
        let response: Value = ureq::post(&self.rpc_url())
            .timeout(std::time::Duration::from_secs(15))
            .send_json(body)
            .map_err(|e| TrishaError::Node(format!("RPC '{}': {}", method, e)))?
            .into_json()
            .map_err(|e| TrishaError::Node(format!("RPC '{}' parse: {}", method, e)))?;
        if response.get("jsonrpc").and_then(Value::as_str) != Some("2.0")
            || response.get("id").and_then(Value::as_u64) != Some(1)
        {
            return Err(TrishaError::Node("invalid mining JSON-RPC envelope".into()));
        }
        if let Some(err) = response.get("error").filter(|v| !v.is_null()) {
            return Err(TrishaError::Node(format!("RPC error: {}", err)));
        }
        response
            .get("result")
            .cloned()
            .ok_or_else(|| TrishaError::Node(format!("RPC '{}': missing result", method)))
    }

    pub fn get_block_template(&self, guesser_address: &str) -> Result<Value, TrishaError> {
        let actual = self.json_call("node_network", serde_json::json!([]))?;
        if actual.get("network").and_then(Value::as_str) != Some(self.network()?) {
            return Err(TrishaError::Node(
                "HTTP mining node network differs from selected network".into(),
            ));
        }
        self.json_call(
            "mining_getBlockTemplate",
            serde_json::json!([guesser_address]),
        )
    }

    pub fn submit_block(&self, block: &Value, pow: &Value) -> Result<bool, TrishaError> {
        let result = self.json_call("mining_submitBlock", serde_json::json!([block, pow]))?;
        result
            .get("success")
            .and_then(|v| v.as_bool())
            .ok_or_else(|| TrishaError::Node("submit_block: unexpected response".to_string()))
    }

    pub fn wallet_file(&self) -> Result<Option<PathBuf>, TrishaError> {
        let network = self.network()?;
        let output = self
            .command()
            .args(["which-wallet", "--network", network])
            .output()?;
        if !output.status.success() {
            return Err(TrishaError::Node("which-wallet failed".into()));
        }
        let text = String::from_utf8(output.stdout)
            .map_err(|_| TrishaError::Node("invalid wallet path response".into()))?;
        let text = text.trim();
        if text.is_empty() {
            return Ok(None);
        }
        let file = PathBuf::from(text);
        if !file.is_absolute()
            || file.components().any(|c| {
                matches!(
                    c,
                    std::path::Component::ParentDir | std::path::Component::CurDir
                )
            })
            || file.file_name().is_none_or(|n| n != "wallet.dat")
            || file
                .parent()
                .and_then(Path::file_name)
                .is_none_or(|n| n != "wallet")
            || file
                .parent()
                .and_then(Path::parent)
                .and_then(Path::file_name)
                .is_none_or(|n| n != network)
        {
            return Err(TrishaError::Node(
                "which-wallet returned an unsafe or wrong-network path".into(),
            ));
        }
        // Reject symlinks in every component, not just the final secret file.
        let mut prefix = PathBuf::new();
        for part in file.components() {
            prefix.push(part.as_os_str());
            // A drive prefix alone (C:) denotes a drive-relative current
            // directory; inspect it only after the absolute root is joined.
            if matches!(part, std::path::Component::Prefix(_)) {
                continue;
            }
            let metadata = std::fs::symlink_metadata(&prefix)?;
            let symbolic = metadata.file_type().is_symlink();
            #[cfg(windows)]
            let symbolic = {
                use std::os::windows::fs::MetadataExt;
                symbolic || metadata.file_attributes() & 0x400 != 0
            };
            if symbolic {
                return Err(TrishaError::Node(
                    "wallet path contains a symbolic link".into(),
                ));
            }
        }
        if !file.is_file() {
            return Err(TrishaError::Node(
                "wallet path is not a regular file".into(),
            ));
        }
        let file = std::fs::canonicalize(file)?;
        if let Some(base) = std::env::var_os("NEPTUNE_DATA_DIR") {
            // Absolute overrides name the base exactly. Relative upstream project
            // paths are OS-specific; trust which-wallet rather than guessing them.
            let base = PathBuf::from(base);
            if base.is_absolute() {
                let base = std::fs::canonicalize(base)?;
                if file != base.join(network).join("wallet/wallet.dat") {
                    return Err(TrishaError::Node(
                        "wallet path differs from selected data directory".into(),
                    ));
                }
            }
        }
        Ok(Some(file))
    }

    pub fn create_neuron(&self, import: bool) -> Result<PathBuf, TrishaError> {
        if self.wallet_file()?.is_some() {
            return Err(TrishaError::Node("selected wallet already exists".into()));
        }
        let mut command = self.command();
        command.args([
            if import {
                "import-seed-phrase"
            } else {
                "generate-wallet"
            },
            "--network",
            self.network()?,
        ]);
        let success = if import {
            // Upstream owns the interactive secret dialog. No seed argv or logs.
            command.status()?.success()
        } else {
            // Generation emits ordinary status, not a seed phrase.
            command.output()?.status.success()
        };
        if !success {
            return Err(TrishaError::Node("wallet operation failed".into()));
        }
        self.wallet_file()?
            .ok_or_else(|| TrishaError::Node("wallet operation did not create a wallet".into()))
    }
}

pub fn trisha_config_dir() -> PathBuf {
    crate::platform_paths::config_dir()
}

pub fn load_hidden_addresses(network: &str) -> Vec<String> {
    let path = trisha_config_dir().join(network).join("hidden_addresses");
    std::fs::read_to_string(path)
        .unwrap_or_default()
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| l.trim().to_string())
        .collect()
}

pub fn save_hidden_addresses(network: &str, addrs: &[String]) -> Result<(), TrishaError> {
    let dir = trisha_config_dir().join(network);
    std::fs::create_dir_all(&dir)
        .map_err(|e| TrishaError::Io(format!("cannot create config dir: {}", e)))?;
    let content = addrs.join("\n") + if addrs.is_empty() { "" } else { "\n" };
    std::fs::write(dir.join("hidden_addresses"), content)
        .map_err(|e| TrishaError::Io(format!("cannot write hidden_addresses: {}", e)))
}

fn validate_key_type(key_type: &str) -> Result<(), TrishaError> {
    if key_type != "generation" {
        return Err(TrishaError::Node(format!(
            "neptune-cli receiving addresses support generation keys, not '{}'",
            key_type
        )));
    }
    Ok(())
}

#[cfg(test)]
mod mining_rpc_tests {
    use super::*;
    use std::io::{BufRead, Read, Write};
    fn server(responses: Vec<Value>) -> (u16, std::thread::JoinHandle<Vec<Value>>) {
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let handle = std::thread::spawn(move || {
            let mut requests = Vec::new();
            for response in responses {
                let (mut stream, _) = listener.accept().unwrap();
                stream
                    .set_read_timeout(Some(std::time::Duration::from_secs(5)))
                    .unwrap();
                let mut reader = std::io::BufReader::new(stream.try_clone().unwrap());
                let mut size = 0;
                loop {
                    let mut line = String::new();
                    reader.read_line(&mut line).unwrap();
                    if line == "\r\n" {
                        break;
                    }
                    if let Some(v) = line.to_lowercase().strip_prefix("content-length:") {
                        size = v.trim().parse().unwrap();
                    }
                }
                let mut bytes = vec![0; size];
                reader.read_exact(&mut bytes).unwrap();
                requests.push(serde_json::from_slice(&bytes).unwrap());
                let body = response.to_string();
                write!(stream,"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",body.len(),body).unwrap();
            }
            requests
        });
        (port, handle)
    }
    fn ok(result: Value) -> Value {
        serde_json::json!({"jsonrpc":"2.0","id":1,"error":null,"result":result})
    }
    #[test]
    fn mining_http_uses_selected_network_and_native_tuple_requests() {
        let (port, server) = server(vec![
            ok(serde_json::json!({"network":"main"})),
            ok(serde_json::json!({"template":null})),
            ok(serde_json::json!({"success":false})),
        ]);
        let client = NeptuneClient::mining_client(1, port, "main");
        assert!(client.get_block_template("reward-address").unwrap()["template"].is_null());
        assert!(!client
            .submit_block(
                &serde_json::json!({"kernel":{}}),
                &serde_json::json!({"nonce":"n"})
            )
            .unwrap());
        let requests = server.join().unwrap();
        assert_eq!(requests[0]["method"], "node_network");
        assert_eq!(requests[0]["params"], serde_json::json!([]));
        assert_eq!(requests[1]["method"], "mining_getBlockTemplate");
        assert_eq!(requests[1]["params"], serde_json::json!(["reward-address"]));
        assert_eq!(requests[2]["method"], "mining_submitBlock");
        assert_eq!(
            requests[2]["params"],
            serde_json::json!([{"kernel":{}},{"nonce":"n"}])
        );
    }
    #[test]
    fn wrong_network_and_rpc_envelope_reject_before_template_work() {
        for response in [
            ok(serde_json::json!({"network":"testnet-0"})),
            serde_json::json!({"jsonrpc":"2.0","id":2,"result":{"network":"main"}}),
            serde_json::json!({"jsonrpc":"2.0","id":1,"error":{"code":-1,"message":"unavailable"}}),
        ] {
            let (port, server) = server(vec![response]);
            assert!(NeptuneClient::mining_client(1, port, "main")
                .get_block_template("address")
                .is_err());
            assert_eq!(server.join().unwrap().len(), 1);
        }
    }
}
