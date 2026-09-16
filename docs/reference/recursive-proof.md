# Triton recursive proof contract (version 1)

`vm.triton.proof.verify(expected_claim: Digest)` verifies an official Triton 7 proof using fixed `Stark::default()` parameters. The caller supplies `Tip5::hash(&expected_native_claim)`, which commits to the native claim's program digest, claim version, complete public input/output vectors and their lengths. Reading this expected commitment from public input binds it into the outer proof. A witness-supplied, unauthenticated expected commitment must never authorize a computation.

Warrior `stark-triton-v7` proof bytes use the existing fixed-width bincode layout:
one little-endian u64 field count, followed by exactly that many little-endian
canonical Goldilocks u64 values. Extra bytes, field representatives at or above
the modulus, inconsistent lengths, and artifacts above 64 MiB are rejected
before allocation/verification. The recursive adapter additionally enforces its
smaller version1 proof-word bound. The byte layout is unchanged; legacy proof versions and artifact formats are rejected. Native verification also bounds padded height and requires the exact proof-stream item count.

The operation returns no value. A malformed witness, mismatched claim commitment or invalid proof aborts execution. Host preprocessing is an encoding convenience: the executing program checks the claim commitment and official proof again.

The existing secret token stream contains:

1. Schema version 1.
2. A nonzero U32 claim length and that many canonical fields of its native `BFieldCodec` encoding.
3. A nonzero U32 proof length and that many canonical fields of its native `BFieldCodec` encoding.

Limits are 131072 claim fields and 1048576 proof fields. The proof's internal encoded length must equal the external length minus one. The claim commitment covers its entire declared encoding, including all size words; the host adapter additionally requires canonical decode/encode round trips. The existing secret digest queue contains the paths produced by official `StarkVerify::update_nondeterminism`.

Reserved RAM: proof `[2^24,2^24+2^20)`, claim `[2^25,2^25+2^17)`, controls `[2^26,2^26+16)`, fixed protocol claim construction `[2^26+256,2^26+320)`, and current-program digest `[2^26+320,2^26+325)`. Callers must avoid those ranges. These are this intrinsic's explicit memory preconditions; ordinary compiler stack operations preserve source RAM and introduce no additional reserved interval. The official verifier retains its documented upper-memory allocator ranges.

The pinned upstream memory convention additionally reserves the allocator counter at field address `p-1`, dynamically allocated pages 1 through `2^31-1` (each page contains `2^32` fields), and the three full pages immediately below `p-1` for verifier/static memory. The operation changes the sponge state and consumes exactly its encoded private witness stream and proof paths; callers must start a fresh sponge transcript afterward. It preserves caller stack values below its five-field argument, including across repeated calls.

The host encoder takes the caller's explicit expected native claim and an official proof, validates their relation, and returns the existing `ProgramInput` representation. No shared runtime transport change is required.

Acceptance requires a real compiled SDK program to accept an official proof and reject changed program/input/output claims, commitment, version and lengths. The compiled SDK integration accepts an official proof and rejects altered commitments. Historical experimental Neptune verifier prototypes remain excluded and are not aliases for this operation.

The Rust adapters are `trisha_rs::recursive::encode(expected_claim, native_proof)` and `encode_proof_data(expected_claim, warrior_proof)`. Both require the caller's expected native claim; proof-file metadata cannot select the authorized computation. Their public input is the five commitment fields, while secret tokens and digest paths remain private witness data.

## CLI workflow

`run` and `prove`, including their `batch` forms and single `--tasm` input, accept `--input-file`. It conflicts with `--input-values`, `--secret` and `--digests`. The version 1 JSON document is:

```json
{"schema_version":1,"public":["2"],"secret":[],"digests":[]}
```

Every digest is an array of exactly five fields. Fields may be JSON unsigned integers or unsigned decimal strings; strings preserve full precision in other JSON tools. Values must be below the Goldilocks modulus. Unknown keys, unsupported versions and noncanonical fields are rejected. Input, expected-claim and proof-file readers accept regular files only; symbolic links, pipes, directories and devices are rejected. On released macOS and Linux x86_64/aarch64 platforms, opening is nonblocking and does not follow the final symbolic link, and the opened file identity is checked again. Other platforms perform regular-file checks before and after opening without this race-protection guarantee. These readers have a 64 MiB transport limit; decoded ProgramInput is additionally bounded at8Mi canonical field words across public, secret and digest streams, counting five words per digest. Sequence decoding stops at its bound, and the SDK applies the same total limit; recursive encoding additionally enforces its smaller claim/proof field limits.

Prepare a private witness from a proof file and an independently authorized expected claim:

```sh
trisha prove inner.tri --input-file inner.json --output inner.proof.toml
trisha witness inner.proof.toml --expected-claim expected.json --output witness.json
trisha run examples/triton/recursive_verifier.tri --input-file witness.json
trisha prove examples/triton/recursive_verifier.tri --input-file witness.json --output outer.proof.toml
trisha verify outer.proof.toml
```

`expected.json` contains exactly `schema_version: 1`, `program_hash` (five canonical fields), `public_input` and `public_output` (complete field arrays). It refers to the native claim version 5 for `stark-triton-v7`. The caller must obtain the expected program digest and IO from its authorized computation, not copy them from an untrusted proof. The adapter verifies the proof against that expected claim before emitting a witness. Its output contains only the five full-claim commitment fields as public input, plus the private proof transport. On Unix the new file has permissions 0600; an existing file is not overwritten.

Run the transport, compiled SDK and upstream attack regressions with:

```sh
RAYON_NUM_THREADS=4 cargo test -p trisha-rs --test recursive_verifier --test recursive_witness
```

The full outer proof gate is explicit because it uses substantial memory. It generates an inner proof, executes compiled SDK verification, proves that outer execution at default security, verifies the outer proof, and rejects changed outer program, public commitment and output:

```sh
RAYON_NUM_THREADS=4 cargo test -p trisha-rs --release --test recursive_witness outer_proof_binds_compiled_recursive_sdk_to_public_claim -- --ignored --nocapture
```

## Fixed Neptune policy claims

`os.neptune.transaction.verify(kernel)` binds the program to the pinned Neptune consensus 0.15.1 `HardforkGamma` SingleProof program. `os.neptune.native_currency.verify(kernel, inputs, outputs)` binds its complete native currency type-script program. Both require the Neptune target; the bare Triton package does not export these protocol intrinsics.

The owned assembly constructs the full native claim from the fixed program digest, native version 5, each supplied digest reversed into the public input, and an empty public output. It hashes the authoritative `Claim` codec encoding before calling the same recursive verifier. The witness cannot choose a different program, version, IO width or output. The caller must authenticate the kernel and salted UTXO commitments against its intended transaction/state. Native currency verification alone does not establish the complete transaction graph.

Program digests are reproduced by `tools/neptune-policy-oracle` against the exact upstream revision `9869b5e35b659dc520fad51ba5a9c812fed46db0`. This standalone oracle has no dependency on Trident compilation and does not use mock proofs or upstream claim-verification caches. `examples/single_proof.rs` traces all five required subrelations for a deterministic empty transaction; its explicit `--prove NEW_DIRECTORY` mode generates their real proofs and the complete SingleProof sequentially. This is a consensus-proof relation, not a network submission or a replacement for node state/admission checks.

The shared fixed-claim binder's real proof regressions are in `rs/tests/fixed_claim.rs`. Full protocol fixtures and outer proofs are separate release gates; successful binding tests alone do not establish that these gates have completed.

`vm.triton.context.program_digest()` returns the VM-authenticated hash of the currently executing program. The linker captures Triton's initial stack digest before source execution and only emits this prologue when the operation is reachable. This avoids embedding a program's own hash into its source. Callers must preserve the reserved context RAM range; the runtime oracle regression compares all five returned words with native `Program::hash()` across repeated nested calls.

### CLI policy adapter

For a native proof artifact whose expected policy is known to the caller:

```sh
trisha witness single-proof.toml --policy neptune-transaction --commitments kernel.json --output transaction-input.json
trisha run examples/neptune/transaction_validation.tri --target neptune --input-file transaction-input.json
```

`kernel.json` contains `schema_version: 1` and `kernel`, an array of five canonical fields. The native currency policy is `neptune-native-currency`; its commitments document additionally requires `inputs` and `outputs`, each a five-field salted UTXO digest. Those fields are caller-authorized commitments, not values copied from an untrusted proof. Unknown fields, noncanonical words, wrong widths, missing commitments and mismatched claims are rejected.

`--policy` conflicts with `--expected-claim`. The adapter supplies the fixed program digest, native version and empty output itself, verifies the actual proof, and writes public input in the shape the selected SDK operation consumes. It does not expose a user-selectable program hash. Generic `--expected-claim` retains its full-claim commitment output. Both paths write the same private version-1 witness transport with the same limits and file permissions.

The process regression in `cli/tests/recursive_input.rs` reconstructs genuine independent SingleProof and NativeCurrency artifacts from the stored fixtures, invokes both policy adapters and executes their compiled SDK programs. It rejects altered caller kernels and noncanonical commitments without creating an output file.
