//! Explicit authenticated gateway transport. Neptune's native JSON-RPC does not
//! implement this bearer authentication; configure a gateway or local proxy.
use super::PreparedTransaction;
use serde::Deserialize;
use std::{io::Read, path::Path, time::Duration};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GatewayAuth {
    schema_version: u32,
    network: String,
    endpoint: String,
    bearer_token: String,
}

impl GatewayAuth {
    pub fn from_file(path: &Path) -> Result<Self, String> {
        let metadata =
            std::fs::symlink_metadata(path).map_err(|_| "cannot inspect gateway auth file")?;
        if !metadata.is_file() {
            return Err("gateway auth must be a regular file".into());
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            if metadata.permissions().mode() & 0o077 != 0 {
                return Err("gateway auth permissions must exclude group and other users".into());
            }
        }
        let mut bytes = Vec::new();
        std::fs::File::open(path)
            .map_err(|_| "cannot open gateway auth file")?
            .take(4097)
            .read_to_end(&mut bytes)
            .map_err(|_| "cannot read gateway auth file")?;
        if bytes.len() > 4096 {
            return Err("gateway auth exceeds 4 KiB".into());
        }
        super::json::guard(&bytes)?;
        serde_json::from_slice(&bytes).map_err(|_| "invalid gateway auth configuration".into())
    }
}

pub fn submit(
    prepared: &PreparedTransaction,
    endpoint: &str,
    auth: &GatewayAuth,
) -> Result<(), String> {
    if auth.schema_version != 1 || auth.network != prepared.network || auth.endpoint != endpoint {
        return Err("gateway configuration does not bind selected network and endpoint".into());
    }
    if auth.bearer_token.is_empty()
        || auth.bearer_token.len() > 2048
        || !auth.bearer_token.bytes().all(|b| b.is_ascii_graphic())
    {
        return Err("invalid gateway bearer token".into());
    }
    let url = url::Url::parse(endpoint).map_err(|_| "invalid gateway URL")?;
    let local = matches!(url.host_str(), Some("localhost" | "127.0.0.1" | "[::1]"));
    if (!local && url.scheme() != "https")
        || !matches!(url.scheme(), "http" | "https")
        || !url.username().is_empty()
        || url.password().is_some()
        || url.fragment().is_some()
        || url.query().is_some()
    {
        return Err("gateway requires HTTPS (HTTP allowed only on explicit loopback) and no URL credentials/query".into());
    }
    let agent = ureq::AgentBuilder::new()
        .redirects(0)
        .timeout(Duration::from_secs(60))
        .timeout_connect(Duration::from_secs(5))
        .timeout_read(Duration::from_secs(30))
        .timeout_write(Duration::from_secs(30))
        .build();
    let response = agent
        .post(endpoint)
        .set("Authorization", &format!("Bearer {}", auth.bearer_token))
        .send_json(&prepared.rpc_request)
        .map_err(|_| "gateway rejected or failed transaction request")?;
    if response.status() != 200 {
        return Err("unexpected gateway HTTP status".into());
    }
    let mut bytes = Vec::new();
    response
        .into_reader()
        .take(65537)
        .read_to_end(&mut bytes)
        .map_err(|_| "cannot read gateway response")?;
    if bytes.len() > 65536 {
        return Err("gateway response exceeds 64 KiB".into());
    }
    super::json::guard(&bytes)?;
    let value: serde_json::Value =
        serde_json::from_slice(&bytes).map_err(|_| "invalid gateway JSON response")?;
    if value.get("jsonrpc").and_then(|v| v.as_str()) != Some("2.0")
        || value.get("id").and_then(|v| v.as_u64()) != Some(1)
        || value.get("error").is_some()
        || value
            .get("result")
            .and_then(|v| v.get("success"))
            .and_then(|v| v.as_bool())
            != Some(true)
    {
        return Err("gateway did not confirm transaction acceptance".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{Read, Write},
        net::TcpListener,
        thread,
    };
    fn receipt() -> PreparedTransaction {
        PreparedTransaction {
            format: "test",
            upstream_revision: super::super::UPSTREAM_REVISION,
            operation: "transport-only-test",
            network: "regtest".into(),
            program_digest: [0; 5],
            kernel_digest: [0; 5],
            output_commitments: vec![],
            compiled_lock_outputs: vec![],
            single_proof_verified: false,
            current_chain_admission_checked: false,
            rpc_request: serde_json::json!({"jsonrpc":"2.0","id":1,"method":"wallet_submitTransaction","params":[{"opaque":"exact-test-transaction"}]}),
        }
    }
    #[test]
    fn gateway_sends_exact_request_and_rejects_wrong_receipts() {
        for (body, accepted) in [
            (
                r#"{"jsonrpc":"2.0","id":1,"result":{"success":true}}"#,
                true,
            ),
            (
                r#"{"jsonrpc":"2.0","id":2,"result":{"success":true}}"#,
                false,
            ),
            (
                r#"{"jsonrpc":"2.0","id":1,"result":{"success":false}}"#,
                false,
            ),
            (
                r#"{"jsonrpc":"2.0","id":1,"error":{"message":"private"}}"#,
                false,
            ),
            (r#"{"id":1,"result":{"success":true}}"#, false),
            (
                r#"{"jsonrpc":"2.0","id":1,"id":1,"result":{"success":true}}"#,
                false,
            ),
        ]
        .into_iter()
        .map(|(body, accepted)| (body.to_owned(), accepted))
        .chain([(" ".repeat(65537), false)])
        {
            let listener = TcpListener::bind("127.0.0.1:0").unwrap();
            let endpoint = format!("http://{}", listener.local_addr().unwrap());
            let server = thread::spawn(move || {
                let (mut socket, _) = listener.accept().unwrap();
                socket
                    .set_read_timeout(Some(Duration::from_secs(5)))
                    .unwrap();
                let mut request = Vec::new();
                let mut block = [0; 4096];
                loop {
                    let count = socket.read(&mut block).unwrap();
                    assert_ne!(count, 0);
                    request.extend_from_slice(&block[..count]);
                    if let Some(end) = request.windows(4).position(|w| w == b"\r\n\r\n") {
                        let header = std::str::from_utf8(&request[..end]).unwrap();
                        let size: usize = header
                            .lines()
                            .find_map(|line| {
                                line.to_ascii_lowercase()
                                    .strip_prefix("content-length: ")
                                    .map(|s| s.parse().unwrap())
                            })
                            .unwrap();
                        if request.len() >= end + 4 + size {
                            assert!(header.contains("Authorization: Bearer mock-private-token"));
                            let payload: serde_json::Value =
                                serde_json::from_slice(&request[end + 4..]).unwrap();
                            assert_eq!(payload, receipt().rpc_request);
                            break;
                        }
                    }
                    assert!(request.len() < 8192);
                }
                write!(
                    socket,
                    "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                    body.len(),
                    body
                )
                .unwrap();
            });
            let auth = GatewayAuth {
                schema_version: 1,
                network: "regtest".into(),
                endpoint: endpoint.clone(),
                bearer_token: "mock-private-token".into(),
            };
            let result = submit(&receipt(), &endpoint, &auth);
            assert_eq!(result.is_ok(), accepted);
            if let Err(error) = result {
                assert!(!error.contains("private"));
            }
            server.join().unwrap();
        }
    }
    #[test]
    fn configuration_rejects_network_mismatch_and_plaintext_remote() {
        let mut auth = GatewayAuth {
            schema_version: 1,
            network: "mainnet".into(),
            endpoint: "http://example.invalid".into(),
            bearer_token: "never-sent".into(),
        };
        assert!(submit(&receipt(), &auth.endpoint, &auth).is_err());
        auth.network = "regtest".into();
        assert!(submit(&receipt(), &auth.endpoint, &auth).is_err());
        auth.endpoint = "https://user:password@example.invalid".into();
        assert!(submit(&receipt(), &auth.endpoint, &auth).is_err());
    }
}
