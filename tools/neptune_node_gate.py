#!/usr/bin/env python3
"""Real pinned-node admission gate, only inside a loopback-only Linux netns.

Run via: sudo unshare --net --fork --kill-child python3 THIS_SCRIPT ...
No wallet import, peer, composer, guesser or public listener is configured.
"""
import argparse
import copy
import hashlib
import hmac
import http.server
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request

MAX_BYTES = 64 * 1024 * 1024
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def document(path):
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, "invalid bounded input file")
    return json.loads(path.read_bytes())


def run(command, timeout=60):
    result = subprocess.run(command, capture_output=True, timeout=timeout)
    require(result.returncode == 0, "local command failed: " + command[0])
    return result.stdout


def post(url, body, token=None):
    raw = json.dumps(body, separators=(",", ":")).encode()
    require(len(raw) <= MAX_BYTES, "request too large")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, raw, headers=headers)
    with OPENER.open(request, timeout=30) as response:
        raw = response.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "response too large")
    reply = json.loads(raw)
    require(reply.get("jsonrpc") == "2.0" and reply.get("id") == body["id"], "wrong RPC envelope")
    return reply


def call(url, method, params=None):
    reply = post(url, {"jsonrpc": "2.0", "id": 17, "method": method, "params": params or []})
    require("error" not in reply and "result" in reply, "native RPC rejected query")
    return reply["result"]


def isolate():
    require(os.name == "posix" and Path("/proc/self/ns/net").exists(), "Linux network namespace required")
    require(os.readlink("/proc/self/ns/net") != os.readlink("/proc/1/ns/net"), "refusing initial network namespace")
    interfaces = json.loads(run(["ip", "-j", "link", "show"]))
    require([item["ifname"] for item in interfaces] == ["lo"], "namespace must contain only loopback")
    run(["ip", "link", "set", "lo", "up"])
    require(not json.loads(run(["ip", "-j", "route", "show"])), "namespace has an external route")
    mounts = Path("/proc/mounts").read_text().splitlines()
    require(not any(line.split()[2] in {"9p", "virtiofs", "nfs", "nfs4", "cifs"} for line in mounts), "host/shared mounts are forbidden")


def gateway(native_url, expected, token):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            self.connection.settimeout(15)
            authorized = hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token)
            lengths = self.headers.get_all("Content-Length", [])
            valid_length = len(lengths) == 1 and lengths[0].isdigit() and int(lengths[0]) <= MAX_BYTES
            if not authorized or self.path != "/" or not valid_length or self.headers.get("Transfer-Encoding"):
                self.send_error(401)
                return
            try:
                body = json.loads(self.rfile.read(int(lengths[0])))
                require(body == expected, "gateway request differs from validated artifact")
                reply = post(native_url, body)
                raw = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                self.server.forwarded += 1
            except Exception:
                self.send_error(502)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.forwarded = 0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, "http://127.0.0.1:" + str(server.server_port)


def exact_mempool_kernel(url, transaction):
    ids = call(url, "mempool_transactions")["transactions"]
    require(len(ids) <= 16, "unexpected mempool growth in isolated node")
    matches = []
    for transaction_id in ids:
        actual = call(url, "mempool_getTransactionKernel", [transaction_id])["kernel"]
        if actual == transaction["kernel"]:
            matches.append(transaction_id)
    return ids, matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", required=True, type=Path)
    parser.add_argument("--trisha", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--intent", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    args.node, args.trisha = args.node.resolve(), args.trisha.resolve()
    args.source, args.intent = args.source.resolve(), args.intent.resolve()
    require(not args.receipt.exists(), "receipt must be a new file")
    isolate()
    require(b"neptune-cash 0.15.1" in run([str(args.node), "--version"]), "pinned node version required")
    intent = document(args.intent)
    require(intent["network"] == "local-testnet1", "fixture must select real-proof local-testnet1")
    require(intent["transaction"]["kernel"]["inputs"] == [], "gate must not consume wallet funds")
    require(intent["transaction"]["kernel"]["fee"] == "0", "gate must not spend a fee")
    require(all(output["utxo"]["coins"] == [] for output in intent["outputs"]), "gate accepts only zero-coin outputs")
    work = Path(tempfile.mkdtemp(prefix="trisha-neptune-local-gate-"))
    work.chmod(0o700)
    print(json.dumps({"stage": "local-gate-created", "local_work_directory": str(work)}), flush=True)
    prepared_path = work / "prepared.json"
    run([str(args.trisha), "deploy", "prepare", str(args.source), "--intent", str(args.intent), "--state", "local-testnet1", "--output", str(prepared_path)])
    prepared = document(prepared_path)
    require(prepared["single_proof_verified"] is True, "actual SingleProof validation required")
    transaction = prepared["rpc_request"]["params"][0]
    require(transaction == intent["transaction"], "prepared transaction changed")
    native_url = "http://127.0.0.1:29797"
    command = [str(args.node), "--network", "testnet-1", "--data-dir", str(work / "node"),
               "--peer-listen-addr", "127.0.0.1", "--peer-port", "29798", "--rpc-port", "29799",
               "--quic-port", "29800", "--tcp-port", "29801", "--listen-rpc", "127.0.0.1:29797",
               "--rpc-modules", "Node,Chain,Wallet,Mempool,Mining", "--restrict-peers-to-list",
               "--max-num-peers", "0", "--no-transaction-initiation", "--tx-proving-capability", "lockscript",
               "--max-mempool-size", "64M"]
    node_log = open(work / "node.log", "wb")
    node = subprocess.Popen(command, cwd=work, stdout=node_log, stderr=subprocess.STDOUT, start_new_session=True)
    proxy = None
    started = time.monotonic()
    try:
        for _ in range(180):
            require(node.poll() is None, "isolated node exited during startup")
            try:
                if call(native_url, "node_network")["network"] == "testnet-1":
                    break
            except (OSError, ValueError, RuntimeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError("isolated node startup timed out")
        require(call(native_url, "chain_height")["height"] in [0, "0"], "node must remain at genesis")
        require(call(native_url, "mempool_transactions")["transactions"] == [], "fresh node mempool must be empty")
        token = secrets.token_urlsafe(32)
        proxy, endpoint = gateway(native_url, prepared["rpc_request"], token)
        auth_path = work / "gateway.json"
        with open(auth_path, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as auth:
            json.dump({"schema_version": 1, "network": "local-testnet1", "endpoint": endpoint, "bearer_token": token}, auth)
        try:
            post(endpoint, {"jsonrpc": "2.0", "id": 1, "method": "wallet_submitTransaction", "params": []}, "incorrect-local-test-token")
            raise RuntimeError("gateway accepted incorrect credentials")
        except urllib.error.HTTPError as error:
            require(error.code == 401 and proxy.forwarded == 0, "gateway auth did not reject before forwarding")
        run([str(args.trisha), "deploy", "submit", str(args.source), "--intent", str(args.intent), "--state", "local-testnet1", "--endpoint", endpoint, "--auth-file", str(auth_path)])
        for _ in range(30):
            ids, matches = exact_mempool_kernel(native_url, transaction)
            if matches:
                break
            time.sleep(1)
        require(len(matches) == 1 and len(ids) == 1, "exact submitted kernel was not uniquely admitted")
        admitted_id = matches[0]
        bad = copy.deepcopy(transaction)
        bad["kernel"]["fee"] = "1"
        reply = post(native_url, {"jsonrpc": "2.0", "id": 1, "method": "wallet_submitTransaction", "params": [bad]})
        require("error" in reply, "node accepted altered public kernel with original proof")
        ids, matches = exact_mempool_kernel(native_url, transaction)
        require(ids == [admitted_id] and matches == [admitted_id], "rejected mutation changed mempool")
        require(call(native_url, "chain_height")["height"] in [0, "0"], "gate unexpectedly produced a block")
        receipt = {"format": "trisha-neptune-local-node-gate-v1", "network": "testnet-1", "chain_id": 4,
                   "upstream_revision": "9869b5e35b659dc520fad51ba5a9c812fed46db0",
                   "node_sha256": hashlib.sha256(args.node.read_bytes()).hexdigest(),
                   "trisha_sha256": hashlib.sha256(args.trisha.read_bytes()).hexdigest(),
                   "intent_sha256": hashlib.sha256(args.intent.read_bytes()).hexdigest(),
                   "kernel_digest": prepared["kernel_digest"], "mempool_transaction_id": admitted_id,
                   "actual_single_proof_verified": True, "exact_kernel_observed_in_mempool": True,
                   "altered_kernel_rejected": True, "incorrect_gateway_credentials_rejected": True,
                   "loopback_only_namespace": True, "wallet_funds_used": False, "block_confirmation": False,
                   "elapsed_seconds": time.monotonic() - started, "local_work_directory": str(work)}
        with args.receipt.open("x") as target:
            json.dump(receipt, target, indent=2)
        print(json.dumps({"status": "PASS", "receipt": str(args.receipt)}))
    finally:
        if proxy:
            proxy.shutdown()
            proxy.server_close()
        if node.poll() is None:
            os.killpg(node.pid, signal.SIGINT)
            try:
                node.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(node.pid, signal.SIGKILL)
                node.wait()
        node_log.close()


if __name__ == "__main__":
    main()
