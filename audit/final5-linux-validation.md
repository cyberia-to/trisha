# FINAL5 native Linux validation — 2026-09-12

Native build, full installed smoke, isolated Neptune admission, reproducible
binary packaging, fresh-unpack verification and Mac→Linux proof interoperability
all passed for the exact artifacts below. No release was published. Failed
FINAL4 sources and receipts remain preserved separately.

## Frozen source and native build

Source archive `/tmp/cyber-release-source-v7-20260912-final5.tar.gz`,
29,383,684bytes, SHA-256
`7c63fcad9d12a220036b531f85eacc1a91984ff87c18687703aeeac57b3df415`.
All11 repositories/2497 source entries and557 vendor entries verified inside the
Lima `cyber-release-check` guest. Native Ubuntu26.04 ARM64,4CPU,16GiB RAM, no swap
or host filesystem mounts. Fresh guest directory:
`/home/master.guest/release-validation/final5-20260912`.

Archived `scripts/build-candidate.nu`, Rust/Cargo1.89.0, Nushell0.112.2
`--no-config-file`, native GCC, jobs2. Build exit0,8m19.55s, maximum process
RSS4,977,308KiB. All three product builds and state-fixture helper emitted zero
warnings. Source inventory before/after matched:

- `sources.json`: `41c924603d1ed20b78844a4a5cc1aa78e3dff759349d98f1713015e5cfb124a0`
- Source verification receipt: `c9c1ddb3c3d7e24104a9329c073b9cbb1f83fceb426daead1d1ed4b7ed67cb73`

| Binary | SHA-256 |
|---|---|
| trident | 6dc7043c6e074b56628fc0629924a21189417c77c8acc5dc4fba631cf506d866 |
| trisha | 10a4ab5ea8b31684992508d8e571f7cfcbacd8bdb728a862973bb3252e0747aa |
| joy | 581c8ebe26c0e70d3ec008379e9f63204f2fd91cb76c9b03ca83f676d368d7ae |

Build logs `/tmp/cyber-final5-linux-build.log` and
`/tmp/cyber-final5-linux/{trident,trisha,joy,fixture}-build.log`; candidate and
source-verification JSON are retained in the latter directory.

## Quick regression and full smoke

Before proving, the exact archived imported-generic fold fixture ran through
installed Trident and Joy in debug/release: all4 cases with input3,5 returned803.
Receipt `/tmp/cyber-final5-linux/imported-check.log`.

Archived smoke SHA-256
`73c48275e69574eabfe3c99f1009e05617ab7532449ecab04f3cf5bd229fd988`.
Actual exit0, genuine `smoke.json` with `all_checks_passed: true`;222.810seconds,
peak summed process-group RSS7,822,966,784bytes, minimum available memory
8,408,342,528bytes,1101 samples. Four Rayon threads, `TVM_LDE_TRACE=no_cache`,
14GiB RSS limit/minimum1GiB available; no guard stop.

Real recursive outer proving/verification; typed entry parameters; imported
explicit/inferred generics; terminal branches; struct declaration order; loop
returns/scope; public `JOYEXEC2`, private `JOYZK003` and authenticated public-state
`JOYST001`; exact claims, tamper and invalid-input rejection all passed. Hidden
state queries use bounded fully public tables, with no private-database claim.
Receipts `/tmp/cyber-final5-linux/{full-smoke.log,full-smoke-memory.json,smoke.json}`.

## Isolated Neptune admission

Preserved genuine intent SHA-256
`4f3d8d38bef5911a57d07ff7f1fba83819b10388f26a9c2dd9974fe0b013c839`
was10908.256seconds old, below the10-hour expiry limit. No expiry rule changed.
Archived node gate ran the new Trisha binary with pinned Neptune0.15.1 in a fresh
loopback-only network namespace. Actual SingleProof verification and unique exact
kernel admission passed; modified-kernel and wrong-auth rejection passed. No
wallet funds, public network submission or block confirmation was involved.
Node process cleanup completed.

Receipts `/tmp/cyber-final5-linux/{node-intent-age.json,node-admission.json,node.log,cleanup.json}`.

## Reproducible archive and fresh unpack

Archive `/tmp/cyber-final5-linux/cyber-tools-linux-aarch64-final5.tar.gz`,
10,960,544bytes, SHA-256
`de77709b3d46d312e9f04ef28d4d1747d8b3634668a5b1db0d70c2c1166368c5`.
Two invocations of the archived packager produced byte-identical archives.
Independent host inspection verified19 entries, ARM64 ELF binary hashes, genuine
smoke receipt, fixtures, harness and source-verification identities. After fresh
unpack inside Linux, the packaged binaries verified8 original Linux proof files
with exact expected claims/inputs and state certificates.

Receipts `/tmp/cyber-final5-linux/{archive-reproducibility.log,archive-verification.json,unpacked-verification.json}`.
Older glibc distributions and native x86_64 execution are outside this receipt.

## Mac→Linux proof interoperability

After the independently successful Mac FINAL5 smoke, copied exactly these original
artifacts: `outer.proof.toml`, `typed-entry-release.proof.toml`,
`imported.proof.toml`, `imported.zheng`, `private.zheng`, `typed-private.zheng`,
`state.zheng`, `private-state.zheng`. No forged variants were used. All8 verified
with fresh-unpacked Linux binaries; the three native claims matched corresponding
Linux smoke claims exactly, and Joy claims/inputs plus public state certificates
were checked explicitly. Per-file hashes matched before/after transport.

Receipts `/tmp/cyber-final5-linux/{mac-proof-input-hashes.json,mac-proof-verification.json}`.
The reverse-direction inputs were provided to the root owner as
`/tmp/cyber-final5-linux/linux-proof-artifacts.tar.gz`, SHA-256
`4d3ae06090181926449f8c78923432feb4365e521b30d8e7b33015119265de0a`.
Reverse-direction results and the complete198-baseline proof gate belong to their
separate receipts; neither is inferred from this installed smoke.
