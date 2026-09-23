# Native proof 7, recursive witness and Joy v3 input review

Date: 2026-09-11. Scope: current working tree, not a cryptographic security audit
or a claim of complete release readiness. Production changes belong to the
parent agent; this review changes only this report. No new proofs were generated.

## Findings

### 1. Native FRI domain must fit its index type — high availability risk, corrected during review

The initial guard in `rs/convert.rs::verify_native_proof` rejected unchecked
shifts and usize overflow, but admitted padded log height 29. With the pinned
default parameters this produces a FRI domain of exactly 2^32. The upstream
FRI index sampler narrows that bound to u32; a direct malformed FRI transcript
panics before opening authentication. A small transcript with one zero Merkle
root per round followed by empty last-codeword/polynomial objects reproduces
this without constructing a large domain or generating a proof:

```rust
let fri = Stark::default().fri(1usize << 29).unwrap();
assert_eq!(fri.domain.len(), 1usize << 32);
let mut stream = ProofStream::new();
for _ in 0..=fri.num_rounds() {
    stream.enqueue(ProofItem::MerkleRoot(Digest::default()));
}
stream.enqueue(ProofItem::FriCodeword(vec![]));
stream.enqueue(ProofItem::FriPolynomial(Polynomial::new(vec![])));
let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
    fri.verify(&mut stream)
}));
assert!(result.is_err());
```

Observed domain 4294967296, 23 rounds, panic in the native Tip5 index sampler.
This reproduces the lower-level FRI panic, **not a complete outer STARK proof
accepted through `verify_native_proof`**: that path additionally requires a
consistent out-of-domain prefix. No soundness forgery was demonstrated.

The parent added rejection when the derived domain does not fit u32, before
`stark.fri`, with a wrapper-level log-height regression. That closes this
admission path; direct upstream FRI remains a lower-level API with preconditions.
Evidence: `/tmp/proof-review-probe.rs`, `/tmp/proof-review-probe.log`.

### 2. Canonical ProgramInput acceptance differs between SDK and CLI — medium, open at review

`convert::to_triton_inputs` constructs every input via `BFieldElement::new`,
which reduces noncanonical u64 values. `Warrior::run`, `run_bounded` and
`prove_full` call it without an input canonicality check. In contrast, CLI
arguments, version-1 input files and the expected-claim decoder reject values
at or above the modulus.

Reproducer using `ProgramInput { public: vec![p], secret: vec![u64::MAX],
digests: vec![[p; 5]] }` and `to_triton_inputs` yielded:

```
public p -> 0
secret u64::MAX -> 4294967294
digest coordinate p -> 0
```

A caller can therefore obtain execution/proof behavior for reduced inputs that
CLI consumers reject. Native claim verification is still canonical; this is an
API-contract inconsistency, not an accepted proof for a different canonical
claim. Use a shared fallible ProgramInput validator at all runner/prover entry
points; retain reduction only in explicitly mathematical conversion helpers.

### 3. JSON transport bound is not a decoded-word bound — medium availability risk, open at review

`cli/input_file.rs` reads at most 64MiB, but its input and expected-claim vectors
use ordinary derived `Vec<Field>` deserialization. `Field` has a String variant,
so dense numeric arrays expand substantially before conversion into u64 words.
There is no independent element-count or aggregate-word limit during decoding.

A 2,097,208-byte version-1 file containing 1,048,576 numeric zero secrets was
accepted by `trisha run --tasm halt.tasm --input-file file.json`. On this host:

| Input | Maximum RSS | Peak footprint |
|---|---:|---:|
| Empty vectors | 9,240,576 bytes | baseline |
| 1,048,576 zero secrets | 47,153,152 bytes | 40,468,936 bytes |

The 64MiB textual cap permits approximately 33 million single-digit elements.
The resulting Field-vector allocation can reach roughly a GiB before other
buffers and conversions. This maximum is an extrapolation from representation
and the measured smaller case; **no OOM experiment was performed**.

Use bounded sequence visitors, limits for public/secret/digest streams and an
aggregate-word budget, checked before allocating the next element. Ensure the
chosen limits still accommodate the recursive encoder's claim/proof envelope
and Merkle digest queue. Expected-claim JSON should use the recursive claim
limit directly. Do not merely check vector lengths after deserialization.
Evidence: `/tmp/proof-review-input-1048576.json` and
`/tmp/proof-review-memory-{small,large}.log`.

## Confirmed protections and limits

- Native proof bytes enforce exact fixed-int count/length, a 64MiB envelope,
  canonical field encodings and no trailing bytes. ProofStream's vector codec
  avoids allocating from an untrusted advertised count before checking available
  data. The native wrapper pins claim version/default security and exact item
  count, closing the known extra-item acceptance difference with recursion.
- Recursive `encode_proof_data` checks the format and complete caller-supplied
  expected claim before proof decoding. Claim and proof word budgets are bounded,
  codec round trips are exact, and native verification precedes official witness
  extraction. The VM loader has separate bounded RAM regions, authenticates the
  whole claim encoding, checks the outer proof word length, and calls the owned
  official verifier. This review did not repeat the expensive positive recursive
  proof test; its full proof-consumption/security tests remain separate gates.
- `fixed_claim_assembly` has intentional assertions on trusted owner configuration
  (label syntax, digest count, marker collision). It must not be exposed directly
  to untrusted configuration without a fallible validation wrapper. No witness
  path from the reviewed CLI supplies those configuration parameters.
- Input JSON rejects unknown fields, wrong digest widths, noncanonical numbers
  and unsupported schema versions. Recursive witness output uses create-new and
  Unix mode 0600. No overwrite permission or secret logging was added.
- Legacy proof TOML is read with a 64MiB bound. Its informational cycle count,
  padded height and program name are not proof-authenticated fields. Acceptance
  must come from the native proof and expected claim, never those metadata.
- Joy `JOYZK003` enforces the coordinated Triton7 backend/format, bounded reads,
  exact postcard consumption, bounded assembly parsing (256KiB, 4096 nodes,
  depth 128), and canonical statement vectors with pre-allocation visitors.
  It regenerates the relation and checker from public statement/state data;
  the proof-supplied checker hash cannot choose a different accepted relation.
  The outer ProofData claim must match the decoded artifact's claim.
- Private-state preparation requires all ten authenticated namespaces and at
  most 2048 field words. Certificate shape/canonicality and each table commitment
  are checked before table bytes become relation constants. The statement binds
  the root and subject ABI, and the outer proof binding includes certificate
  versions and all leaves. No bypass of these bindings was found in this review.
- Joy's certificate and statement decoding limits are tighter than the generic
  transport limit. Those limits are not an assertion that every valid nox program
  or arbitrary large private state is supported.

## Lightweight malformed-input checks

A deterministic 20,000-case short-stream corpus (lengths 0..47, small words,
u32::MAX and p-1) exercised native ProofStream verification and CCS envelope
decoding under `catch_unwind`: **zero panics, zero accepted native proofs**.
A separate 20,000-case `JOYZK003` short-envelope corpus exercised artifact
decoding: **zero panics, zero decoded artifacts**. These are smoke fuzz checks,
not coverage-guided fuzzing or evidence about valid proof cryptography.

Evidence: `/tmp/proof-review-fuzz.rs`, `/tmp/proof-review-fuzz.log`,
`/tmp/joy-review-fuzz.rs`, `/tmp/joy-review-fuzz.log`. The probes link existing
release libraries with rustc and do not occupy the proof-generation slot.

Remaining validation should prioritize shared canonical input rejection,
pre-allocation JSON limits, then sustained structured fuzzing of near-valid
proof streams and artifact envelopes. No new cryptographic security guarantee
is inferred from these parser checks.

## Remediation checkpoint — 2026-09-12

All three findings now have owner-side fixes. `to_triton_inputs` is fallible and
validates canonical input plus8Mi total field words before allocating native
copies. CPU and wgpu share this implementation and exact native verification.
The JSON Field representation is one u64, with immediate canonical parsing,
bounded sequence visitors, aggregate counts and expected-claim limits. The
height guard also rejects domains outside u32 index bounds before native FRI.

Six input/wire tests, two JSON parser tests and one actual-proof GPU verifier
regression pass with zero warnings. Logs: `/tmp/trisha7-input-guards.log`,
`/tmp/trisha7-json-input-guards.log`, `/tmp/trisha7-gpu-proof-guards.log`.
The all-feature/all-target workspace check passed after these boundary changes.
This closes the specific reported admission inconsistencies; it does not turn
short-stream fuzzing into a complete cryptographic audit.

## CLI regular-file loading — 2026-09-12 correction

An independent temporary FIFO without a writer caused both exact installed
FINAL5 commands to block: `trisha run entry.tri --input-file fifo` and
`trisha verify fifo`. Each owned subprocess was terminated and reaped after its
2-second timeout. Receipts `/tmp/trisha-final5-input-fifo-before.json` and
`/tmp/trisha-final5-proof-fifo-before.json` record the exact arguments and binary
SHA256 `9265f599c5200f330d29da19f1fccfeb18d5b9cdd905ba713bd15a068532d47b`.
Neither the frozen executable nor source archive was modified.

The file contract in `docs/reference/recursive-proof.md` was made explicit before
implementation: bounded regular files, not stream devices. The live
`cli/input_file.rs::read_regular_bounded` now checks `symlink_metadata` before
opening, rejecting symbolic links and every nonregular type, and checks the
64MiB bound before allocating input data. On released platforms it uses
`OpenOptionsExt::custom_flags` with O_NONBLOCK|O_NOFOLLOW, preventing a replacement
FIFO from hanging the open. Verified platform ABI values are macOS0x4|0x100,
Linux x86_64 0x800|0x20000, and Linux aarch64 0x800|0x8000 (GNU and musl).
They were checked against locally available libc0.2.184 platform definitions;
no dependency or Cargo lock was changed.

The opened descriptor must still be a regular file within the limit. Unix
metadata device/inode must equal the pre-open identity. Reads remain limited to
64MiB+1 to detect growth. Other platforms retain regular-file checks before and
after opening; this audit does not claim the same nonblocking race protection
there. This is not a filesystem snapshot or a guarantee against concurrent
writes to an already-open regular inode.

`cli/proof_file.rs::load` now uses this same bounded byte reader, retains
proof-specific error categorization and UTF-8/TOML schema decoding, and does not
print malformed proof contents through parser diagnostics. Input/claim errors
likewise contain no witness payload. The recursive and native proof semantics
are unchanged.

The new persistent `cli/tests/input_file_kind.rs` executes public CLI commands
with a3-second owned subprocess deadline. It checks FIFO, directory, regular-file
symlink and FIFO symlink through both run and verify; a valid regular JSON yields5
from input2; malformed JSON/TOML/non-UTF-8 proof reject; a private sentinel is not
printed; sparse files above64MiB reject before reading. Result:1 test passed,
0 failures,0.64 s (`/tmp/trisha-input-file-kind.log`).

As a separate real positive proof-file check, the rebuilt live CLI verified
`/tmp/cyber-final5-darwin-artifact-gate/fresh.proof.toml` successfully, exit0
(`/tmp/trisha-regular-proof-reader-check.log`). It reused an existing genuine
proof; no new proving process or heavy workload was started, and the running
frozen baseline proof gate was not changed.
