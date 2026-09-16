# Pinned Neptune policy oracle

This independent tool builds Neptune0.15.1 from the exact source revision in
Cargo.toml. It executes the complete canonical NativeCurrency program for
10 input coins,7 output coins and a kernel-authenticated3-coin fee, and checks
that changing the output to8 is rejected. The salted UTXO lists, their encodings,
kernel MAST paths, amount arithmetic and program digest come from upstream.
The kernel need not constitute a complete valid transaction: this tool's claim
is the canonical type-script relation; SingleProof validates the complete graph.

Running without arguments prints the independently computed native program hash
and public claim. Giving a JSON output path additionally generates and verifies
a fresh default-security Triton7 proof. It does not read a proof/claim cache.
No proof should be generated concurrently with another memory-heavy proof job.

This optional reference tool is outside the release workspace; it is not a
runtime dependency of Trisha, Trident or Joy.

The complete transaction graph driver is independent of the Trident compiler:

```sh
RAYON_NUM_THREADS=4 cargo run --release --example single_proof
TVM_LDE_TRACE=no_cache RAYON_NUM_THREADS=4 cargo run --release --example single_proof -- --prove NEW_DIRECTORY
```

The first command traces all five real component relations without proving.
The second generates five actual proofs and then the complete SingleProof;
it writes canonical kernel/program hashes and native proof JSON. It does not
load cached or mock proof objects. The fresh local Triton7 reference run took
1,155,385 CPU cycles, padded to2,097,152, and518.771seconds for the SingleProof
prove/verify step; measured peak RSS25.83GB, footprint31.74GB, zero swaps.
These are one machine's measurements, not portable resource guarantees.

From the Trisha workspace, `cargo run -p trisha-rs --release --example
neptune_witness -- transaction ORACLE_JSON OUTPUT_TOML` verifies and translates
the real canonical proof into the recursive witness format. Use `native` for
a NativeCurrency proof. `neptune_native_fixture` additionally executes the
complete independent hand and compiled source wrappers and creates positive
and altered-input benchmark manifests.

`single_proof` and the native-currency oracle also write standard Trisha proof
TOML and explicit policy commitments JSON alongside their native oracle JSON.
An existing independently generated artifact can be exported without reproving:

```sh
cargo run --release --example export_proof -- ORACLE_JSON OUTPUT_PREFIX MEASURED_CYCLES MEASURED_PROVING_MS
trisha witness OUTPUT_PREFIX.toml --policy neptune-transaction --commitments OUTPUT_PREFIX.commitments.json --output private-input.json
```

The exporter verifies the actual canonical native proof, including exact proof
item consumption and bounded padded-height/domain arithmetic. It does not
replace the supplied claim or interpret a successful deserialize as verification.
Use `neptune-native-currency` for that fixed policy.

For the local custom-lock deployment gate, first compile the checked-in
`neptune/tests/fixtures/custom_lock.tri` with Neptune/release. Then:

```sh
cargo run --release --example single_proof -- --deploy-lock LOCK_ASSEMBLY
TVM_LDE_TRACE=no_cache RAYON_NUM_THREADS=4 cargo run --release --example single_proof -- --deploy-lock LOCK_ASSEMBLY --prove NEW_DIRECTORY
```

This constructs an actual zero-coin custom-lock UTXO, sender/receiver commitments,
complete kernel and all five component witnesses through pinned consensus APIs.
The second invocation creates the full SingleProof and `deployment-intent.json`.
The custom-output fixture uses the real Testnet(1) genesis accumulator and a
fresh timestamp captured before proving. Its intent selects local-testnet1
(chain4), distinct from public testnet-0. It is not a funded wallet transaction or a
claim of admission to a live network. Run the ignored adapter/CLI deployment
tests with `TRISHA_DEPLOY_INTENT` and `TRISHA_DEPLOY_ASSEMBLY` pointing to these
artifacts. Reserve one heavy proof process and enough RAM before proving.
