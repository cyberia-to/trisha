# Independent Neptune adapter review

Scope: current `neptune/lib.rs`, `neptune/json.rs`, `neptune/transport.rs`,
`cli/deploy.rs` and `cli/deploy/transaction.rs`. Primary protocol source:
Neptune0.15.1 revision9869b5e35b659dc520fad51ba5a9c812fed46db0 at
`/tmp/trisha-neptune-policy-v0.15.1`. Read-only review; no live node/gateway,
wallet or transaction submission was performed. The actual positive complete
SingleProof preparation/submission fixture belongs to the owner's pending proof
queue, not this review's evidence.

## Concrete finding

**Local input availability: bounded bytes do not bound opening a special file.**
`neptune::read_json` calls File::open before checking file kind. A named pipe with
no writer blocks before the64MiB read limit or JSON guard can run. Reproduced
using a temporary FIFO and the built release binary:

```
trisha deploy prepare custom_lock.tri --intent TEMP_FIFO --output TEMP_JSON
```

The command exceeded a2-second process timeout and was terminated locally. This
is a hostile-local-path availability issue, not a proof forgery. It also applies
to the new output-spec reader using the same API. Reported to the owning agent
and root: reject nonregular input files, with appropriate race handling. The
more restrictive gateway-auth reader already checks regular-file type.

**Resolved by the owner:** read_json now rejects nonregular paths with
symlink_metadata and rejects oversized regular-file metadata before opening.
The owner regression covers FIFO without a writer, directory and symlink
(`/tmp/trisha-neptune-file-kind.log`, one test passed). The updated code was
independently inspected and exercised again in the successful final workspace
run (`/tmp/trisha-workspace-final-current-rerun.log`,428 passed,3 ignored).
This is not an atomic defense against same-user concurrent path replacement.

## Confirmed boundaries

- The independently compiled program hash binds every output marked
  compiled_lock; at least one such output is mandatory. Every described output
  is checked, in kernel order, against its actual mutator-set addition record.
  The output count must equal the kernel count and remain within1..1024.
- Output construction preserves all coin type-script hashes and state words,
  uses upstream Utxo and Tip5, and computes the upstream commitment formula
  `hash_pair(hash_pair(hash(utxo), sender_randomness), receiver_digest)`.
  It does not claim to construct or prove the complete transaction.
- Full kernel MAST hash must equal caller-selected expected_kernel; proof
  verification uses the pinned full SingleProof claim. Proof collections and
  unverified witnesses cannot become prepared submissions. Generic native proof
  validation supplies the version/domain/item-count checks.
- PreparedTransaction fields are private and it is not deserializable. External
  callers cannot load an arbitrary serialized receipt and pass it off as a
  prepared transaction through the public constructor. CLI submit independently
  recompiles and revalidates the intent rather than trusting a preparation file.
- RPC objects are decoded using pinned upstream types and compared against their
  re-encoding. This rejects ignored fields, reducing field aliases and alternate
  hex/number encodings. Lexical admission checks decoded duplicate keys,
  depth64,262144 nodes,65536 elements per array,128 keys per object,16MiB per
  string and32MiB total strings, before constructing the serde tree.
- SubmitTransactionRequest uses upstream Serialize_tuple; the request's params
  are the actual one-element tuple expected by wallet_submitTransaction.
- Gateway auth binds the exact selected endpoint and network, uses a bounded
  regular private file, excludes header injection, disables redirects and
  permits plaintext only on explicit loopback hosts. Responses are bounded and
  require JSON-RPC2.0, matching id1 and success=true without an error member.
- CLI compilation requires a program entry; a library module cannot silently
  become a deployable lock script. Output and preparation files are created
  exclusively, with mode0600 on Unix.

## Explicit limits and outstanding evidence

The intent file is the caller's trusted choice of kernel/output intent. Its
expected_kernel field is not an independently authenticated wallet policy by
itself. The adapter does not select wallet coins or prove current-chain
admission, timestamp freshness or absence of conflicting spends; it records
current_chain_admission_checked=false. The gateway is an explicitly trusted
transport endpoint. A success response is acceptance by that endpoint, not
on-chain confirmation or an independently verified remote network identity.

File-admission bounds apply to read_json callers. The public in-memory prepare
and construct_output APIs accept already allocated serde Values; they should not
be described as bounded network deserializers on their own.

At review time, source contained `deploy output` but the existing release binary
help still listed only prepare/submit/batch. The owner was notified to rebuild
and exercise the new CLI route before final release evidence. The final
all-features workspace run now includes the passing output construction CLI
process test. This closes that stale-binary test gap; it does not establish
live node interoperability.

No proof-binding or RPC canonicality bypass was identified in this bounded
review. This is not a cryptographic audit of Neptune/Triton or a live gateway
interoperability test.
