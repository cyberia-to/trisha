# Isolated Neptune node acceptance gate

Status: **PASS on 2026-09-12**, including genuine SingleProof, adapter/CLI
mutation tests and actual isolated node admission. The exact kernel was observed
uniquely in the mempool; altered kernel/original proof and wrong gateway token
were rejected. No host wallet, public node, funded transaction, composer or
guesser was used. Node cleanup was confirmed after the gate.

The source is upstream Neptune0.15.1 commit
`9869b5e35b659dc520fad51ba5a9c812fed46db0`. Exact tracked-source archive SHA256:
`71a40abfb0b86aa294eed6aab1d9fd3442b2e1893f56dc680a39b76e5e4a3339`.
It was copied into the dedicated Linux ARM64 Lima guest, with no host mounts or
port forwarding. Node source/build/bin remain isolated under guest
`/home/master.guest/release-validation/neptune-node-0151`.

The first node build used Rust1.89 and two jobs, release LTO disabled/debug0.
It reached the final node crate but failed on upstream Duration::from_mins and
Duration::from_hours. Those APIs stabilized in Rust1.91; this requirement is not
reported in upstream Cargo metadata. First attempt:350.4s, peak process-tree
RSS4,287,000,576bytes, no memory guard stop. A separate node-only1.91.0 toolchain is installed (rustc
`f8297e351`,2025-10-28); its build passed in475.6s with peak process-tree
RSS4,817,473,536bytes. The three product binaries separately passed their1.89 build.
Build guard:6.5GiB RSS,512MiB minimum MemAvailable,1GiB free disk, two jobs.

`tools/neptune_node_gate.py` requires a fresh Linux network namespace with only
loopback and no external route or shared host mount. Guard tests in the actual
VM passed: initial namespace is rejected before node startup; `sudo unshare
--net --fork --kill-child` produces a permitted loopback-only namespace. This
blocks upstream's unconditional UPnP activity as well as public peer traffic.

Reproduction uses the pinned node, installed archived product binary and a
fresh local-testnet1 fixture copied into the guest:

```sh
sudo unshare --net --fork --kill-child python3 neptune_node_gate.py \
  --node PINNED_NEPTUNE_CORE --trisha CANDIDATE_TRISHA \
  --source custom_lock.tri --intent deployment-intent.json \
  --receipt NEW_RECEIPT.json
```

The harness creates a private fresh node data directory, starts testnet-1 with
empty peer allowlist, max peers0 and no wallet transaction initiation. Wallet,
Mempool and Mining JSON-RPC modules are loopback-only; Personal/unsafe RPC are
not enabled. The gateway authenticates only the exact request freshly validated
by `trisha deploy prepare`; `trisha deploy submit` repeats validation before
sending. Incorrect credentials must fail before forwarding. After acceptance,
the exact canonical kernel must be observed uniquely in the real mempool;
an altered kernel with the original proof must be rejected without changing it.
The receipt records binary/input hashes, full kernel digest and actual mempool
transaction ID. The latter is not assumed equal to the full kernel MAST digest.

This gate checks real consensus proof/admission and CLI/gateway/node binding.
It does not mine a block or claim confirmation. Regtest accepts only mock proofs
and cannot substitute for this testnet-1 gate. Testnet-1 fixtures use its real
genesis accumulator and capture current wall time before proving; the node's
10-hour mempool age limit makes admission receipts time-dependent.

## Executed receipts

The [machine-readable node receipt](neptune-local-node-receipt.json) binds the
node binary, installed Trisha binary and exact intent by SHA256. The node was
built from the pinned archive above; Trisha was built from the source candidate
in Linux ARM64, without source relabeling. Gate time after preparation:1.608s.
The mempool transaction ID is recorded independently from the full kernel MAST.
Node height remained0; this is admission, not block confirmation.

The fresh deployment fixture has1,155,385 SingleProof cycles, padded height
2,097,152. Five component proofs were generated and verified first; full
SingleProof proving and verification took575.958s, whole process589.83s.
Peak RSS23,307,108,352bytes (process-tree monitor23,307,567,104), peak footprint
31,742,958,560bytes, swaps0. Default security was preserved with four threads
and `TVM_LDE_TRACE=no_cache`; the40GiB/8% resource guard did not trigger.

Both genuine release tests passed without ignoring their assertions:
`trisha-neptune` deployment API1/1 and Trisha deployment CLI1/1. They check
compiled program identity, kernel, output commitments, canonical encodings,
changed fee with recomputed expected kernel/original proof, exact mock request
and rejected response. The actual node subsequently repeated proof/admission
validation on Testnet(1), with no mock proofs.

Local logs: `/tmp/neptune-deployment-proof-full.log`,
`/tmp/neptune-deployment-proof-memory.log`, `/tmp/neptune-deployment-api-gate.log`,
`/tmp/neptune-deployment-cli-gate.log`, `/tmp/neptune-node-admission-rerun.log`.
The first harness attempt stopped at the unauthorized gateway request because
its early401 closed a large body while Python was sending it. The negative now
uses a small unauthorized request and still requires401 before any forwarding;
production adapter code did not change. A fresh namespace/node run then passed.
