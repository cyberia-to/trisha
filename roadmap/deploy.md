---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
status: open
---
# Neptune deployment preparation

`trisha deploy --dry-run` retains explicit offline program inspection. A program
execution proof alone does not establish Neptune transaction validity.

The dedicated `trisha-neptune` crate owns canonical Neptune0.15.1 transaction
and RPC types pinned to revision9869b5e35b659dc520fad51ba5a9c812fed46db0. The
full warrior CLI enables it; the mining-only feature path excludes it.

- `deploy output` constructs a canonical custom-lock UTXO and mutator-set addition
  from the actual compiled Program.hash(), explicit coins and sender/receiver
  commitments. It reports no transaction proof or submission.
- `deploy prepare` validates a complete caller-supplied transaction, every output
  preimage, explicit selected kernel/network and a genuine fixed-policy
  SingleProof. It writes an immutable, private, reviewable exact RPC artifact.
- `deploy submit` repeats validation and submits that exact transaction using
  `wallet_submitTransaction` to an explicitly configured authenticated gateway.
  Neptune's native HTTP JSON-RPC has no bearer/cookie authentication; the gateway
  is distinct from the older authenticated tarpc protocol. Tests include local mocks and a real isolated Testnet(1) node.

The [transaction contract](../docs/reference/neptune-submission.md) defines the
bounded schemas, immutable receipt, transport authentication and admission limits.

Current release gates:

| Gate | Evidence / remaining work |
|---|---|
| B1 pinned API and protocol | Canonical consensus/RPC crates; native proof version5, Triton7; exact method and tuple params |
| B2 compiled lock identity | Actual Program.hash(), canonical UTXO construction and alias rejection tests |
| B3 validated submission adapter | Exact immutable request, bounded authenticated gateway; loopback response rejection tests |
| B4 transaction construction | Real zero-coin custom output/kernel, five component proofs and full SingleProof pass; altered kernel/program/output cases reject |
| B5 CLI and acceptance | Output/prepare/submit process tests pass; real isolated Testnet(1) node admits exact kernel into mempool and rejects altered claim |

Funded wallet coin selection and recipient/change policy are not implemented
by the caller-supplied transaction interface. Public network current-chain
admission remains an external gate. A
successful gateway response means acceptance, not chain confirmation. The local
zero-coin fixture is not a funded deployment or evidence of live network admission.

The validated real deployment fixture targets explicit `local-testnet1` (chain4),
uses its complete genesis accumulator and captures wall time before proving.
Actual node admission passed with loopback-only OS network isolation and the
exact kernel observed in the mempool. See the [receipt and limits](../audit/neptune-local-node-validation.md). Regtest mock acceptance cannot replace this gate.
