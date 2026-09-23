# Validated Neptune transaction submission

The `trisha-neptune` adapter owns Neptune0.15.1 canonical RPC and transaction
codecs pinned to upstream revision `9869b5e35b659dc520fad51ba5a9c812fed46db0`.
The compiler and generic CPU engine do not own these network transaction types.

`trisha deploy prepare PROGRAM --intent intent.json --output prepared.json
--state STATE` validates a complete caller-supplied transaction. The intent
contains schema_version1, network, independently selected expected_kernel,
canonical RpcTransaction, and every output's canonical RpcUtxo,
sender_randomness, receiver_digest and compiled_lock flag, in kernel order.
At least one output must use the actual compiled Program.hash(). Each output
preimage is rehashed using the canonical UTXO codec and mutator-set commitment;
the complete kernel MAST must equal the explicit expected digest. The complete
SingleProof is checked against the pinned policy program, native proof version5,
that kernel digest and empty output. Unknown/noncanonical RPC encodings fail.

The preparation artifact contains the exact JSON-RPC request and verification
receipt. It excludes output preimage randomness. It is created with private
permissions and cannot overwrite an existing file. Preparation does not select
wallet coins, construct funded transaction proofs, or establish current-chain
admission. Those are separate responsibilities of the transaction producer/node.

`trisha deploy submit PROGRAM --intent intent.json --endpoint URL --auth-file
private-gateway.json --state STATE` repeats all preparation checks and sends
exactly that transaction using `wallet_submitTransaction`. Submission is an
explicit external action. Tests use loopback mocks and a real isolated Testnet(1) node.

The native Neptune HTTP JSON-RPC endpoint does **not** implement bearer/cookie
authentication. This adapter requires an explicitly configured authenticated
HTTP gateway/proxy. Its private auth file contains schema_version1, network,
endpoint and bearer_token. HTTPS is required outside explicit loopback. Redirects
are disabled; credentials cannot occur in URL/query; requests time out and
responses are capped at64KiB. Gateway acceptance is not chain confirmation.
The older authenticated tarpc RPC is a distinct protocol.

Release acceptance requires a genuine transaction proof with a custom compiled
lock output, altered kernel/program/output negatives, canonical encoding checks,
and mock submission tests. These gates passed with a fresh genuine SingleProof;
a real isolated Testnet(1) node also admitted the exact kernel and rejected an
altered kernel using the original proof. The [audit receipt](../../audit/neptune-local-node-validation.md) records this result. Funded wallet deployment remains a separate workflow.

Before assembling a full transaction, `trisha deploy output PROGRAM --spec
output-spec.json --output new-output.json` constructs its canonical custom-lock
UTXO and addition record. The bounded spec contains canonical RPC coins,
sender_randomness and receiver_digest. The receipt retains the exact preimage
for transaction construction and is written privately. This step does not
produce a transaction proof. A zero-coin independent oracle fixture exercises
the complete construction and proof path; funded wallet coin selection remains
outside this caller-supplied transaction interface.


## Isolated real-proof network

`local-testnet1` is an explicit non-default state: upstream `testnet-1`, chain4,
legacy RPC29799; its local JSON-RPC gate uses127.0.0.1:29797. It is separate
from public `testnet`/testnet-0/chain3. Unmodified RegTest accepts only mock
proofs and cannot replace this genuine SingleProof admission gate.

Deployment oracle fixtures use the real Testnet(1) genesis accumulator (including
premine and guesser additions) and capture `Timestamp::now()` immediately before
component proving. Timestamp/accumulator cannot be patched after proving: both
belong to the authenticated kernel. Node admission rejects transactions older
than10hours or at least60,001ms in the future. An archived proof remains a valid
mathematical fixture after that window, but must not be reported as a fresh
node-admission receipt.

The node, gateway and client must run with loopback-only OS network isolation:
upstream enables UPnP without a disable switch. Use a fresh private data root,
no peers, no Personal RPC/unsafe mode and no transaction initiation. Admission
success must be followed by observing the exact kernel in the node mempool;
RPC success alone confirms only channel enqueue. No chain confirmation is
claimed. Mining template refresh is a separate gate requiring a real proposal;
without a composer the native endpoint returns null.
