use std::path::PathBuf;
use std::process::Command;

use serde_json::Value;

use crate::error::TrishaError;

pub struct NeptuneClient {
    rpc_port: u16,
    http_rpc_port: u16,
}

impl NeptuneClient {
    pub fn new(rpc_port: u16) -> Self {
        NeptuneClient {
            rpc_port,
            http_rpc_port: 9797,
        }
    }

    pub fn with_http_port(rpc_port: u16, http_rpc_port: u16) -> Self {
        NeptuneClient {
            rpc_port,
            http_rpc_port,
        }
    }

    fn run(&self, args: &[&str]) -> Result<String, TrishaError> {
        let output = Command::new("neptune-cli")
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
            Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
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
        self.run(&["block-height"])
    }

    pub fn peer_info(&self) -> Result<String, TrishaError> {
        self.run(&["peer-info"])
    }

    pub fn mempool_tx_count(&self) -> Result<String, TrishaError> {
        self.run(&["mempool-tx-count"])
    }

    pub fn confirmed_balance(&self) -> Result<String, TrishaError> {
        self.run(&["confirmed-available-balance"])
    }

    pub fn unconfirmed_balance(&self) -> Result<String, TrishaError> {
        self.run(&["unconfirmed-available-balance"])
    }

    pub fn next_address(&self, key_type: &str) -> Result<String, TrishaError> {
        validate_key_type(key_type)?;
        self.run(&["next-receiving-address"])
    }

    pub fn address_at_index(&self, index: u64, key_type: &str) -> Result<String, TrishaError> {
        validate_key_type(key_type)?;
        self.run(&["nth-receiving-address", &index.to_string()])
    }

    pub fn list_utxos(&self) -> Result<String, TrishaError> {
        self.run(&["list-coins"])
    }

    pub fn known_keys(&self) -> Result<String, TrishaError> {
        let index = self.run(&["get-derivation-index", "generation"])?;
        let last = index.trim().parse::<u64>().map_err(|_| {
            TrishaError::Node(format!("invalid generation derivation index: {}", index))
        })?;
        let mut addresses = Vec::new();
        for index in 0..=last {
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
            .send_json(body)
            .map_err(|e| TrishaError::Node(format!("RPC '{}': {}", method, e)))?
            .into_json()
            .map_err(|e| TrishaError::Node(format!("RPC '{}' parse: {}", method, e)))?;
        if let Some(err) = response.get("error") {
            return Err(TrishaError::Node(format!("RPC error: {}", err)));
        }
        response
            .get("result")
            .cloned()
            .ok_or_else(|| TrishaError::Node(format!("RPC '{}': missing result", method)))
    }

    pub fn get_block_template(&self, guesser_address: &str) -> Result<Value, TrishaError> {
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

    pub fn create_neuron() -> Result<String, TrishaError> {
        let output = Command::new("neptune-cli")
            .arg("generate-wallet")
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
            Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
        } else {
            let stderr = String::from_utf8_lossy(&output.stderr);
            Err(TrishaError::Node(format!(
                "neptune-cli generate-wallet: {}",
                stderr.trim()
            )))
        }
    }
}

pub fn data_dir() -> PathBuf {
    if let Ok(d) = std::env::var("NEPTUNE_DATA_DIR") {
        return PathBuf::from(d);
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    if cfg!(target_os = "macos") {
        PathBuf::from(home).join("Library/Application Support/neptune-core")
    } else if cfg!(target_os = "linux") {
        if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
            PathBuf::from(xdg).join("neptune-core")
        } else {
            PathBuf::from(home).join(".local/share/neptune-core")
        }
    } else {
        PathBuf::from(home).join("neptune-core")
    }
}

pub fn neuron_dir() -> PathBuf {
    data_dir().join("wallet")
}

pub fn trisha_config_dir() -> PathBuf {
    if let Ok(d) = std::env::var("TRISHA_CONFIG_DIR") {
        return PathBuf::from(d);
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    if cfg!(target_os = "macos") {
        PathBuf::from(home).join("Library/Application Support/trisha")
    } else {
        PathBuf::from(home).join(".config/trisha")
    }
}

pub fn load_hidden_addresses() -> Vec<String> {
    let path = trisha_config_dir().join("hidden_addresses");
    std::fs::read_to_string(path)
        .unwrap_or_default()
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| l.trim().to_string())
        .collect()
}

pub fn save_hidden_addresses(addrs: &[String]) -> Result<(), TrishaError> {
    let dir = trisha_config_dir();
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
