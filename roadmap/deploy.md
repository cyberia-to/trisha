---
tags: trisha, roadmap
crystal-type: spec
crystal-domain: cyber
status: open
---
# deploy — neptune integration

`trisha deploy` prints metadata and exits. shipping a program on-chain requires neptune-core as a dependency and a UTXO transaction constructed around the TASM digest.

## tasks

```
B1  add neptune-core dependency, study its RPC/tarpc API
B2  implement deploy/lockscript.rs — TASM → LockScript wrapping
B3  implement deploy/neptune.rs — tarpc client, send_transaction
B4  implement deploy/transaction.rs — UTXO construction
B5  wire into cmd_deploy, test on testnet
```
