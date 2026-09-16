# FINAL3 native Linux validation

2026-09-12: frozen-source verification, native candidate build, full installed
proof smoke, binary packaging and repeated isolated Neptune node admission all
passed. This receipt identifies exact local artifacts; nothing was published.

## Frozen input and isolation

Source archive `/tmp/cyber-release-source-v7-20260912-final3.tar.gz`,
29,276,242 bytes, SHA-256
`515cf5a8d5565ad5f2551533c76847c0052c65c6510f4bd449189d341b28dc9b`.
Copied into the existing isolated Lima ARM64 Ubuntu26.04 guest without host
mounts and extracted under
`/home/master.guest/release-validation/final3-20260912/cyber-source`.
The previous rehearsal and failed FINAL2 sources/receipts remain preserved.

The archived verifier passed all11 repositories, 2442 repository entries and
557 vendor entries. `sources.json` SHA-256
`cc831a7da282d7998eb63756e96fc56915a8c1fa0c23f24daac06cb840a88a87`;
`vendor-sources.json` SHA-256
`c80346aea2594e3a51a6ed3f2fc78f0421ebc25601e7cbaaf99efd745f9fdcbf`.
Receipt `/tmp/cyber-final3-linux-source.log`.

## Build configuration

Archived `trisha/scripts/build-candidate.nu`, Nushell0.112.2 with
`--no-config-file`, Rust1.89.0, native GCC, jobs2, fresh candidate prefix.
The atomic staging directory and pre/post inventory verification are part of
the archived builder. Source edits and host binaries are not substituted.
Initial guest disk availability20GiB; VM16GiB memory,4CPU. No node process or
host filesystem mounts existed at launch.

Build log `/tmp/cyber-final3-linux-build.log`. The separately prepared proof
memory guard will use the archived smoke script, four Rayon threads and
`TVM_LDE_TRACE=no_cache`, with maximum14GiB summed process RSS and minimum1GiB
available memory. Its completed run is recorded below.

## Native candidate passed

Archived builder exit0, elapsed7m47.75s, maximum process RSS4,816,980KiB, no
swaps. All four logs (three products and fixture helper) have zero warnings.
Pre/post inventory receipt SHA-256
`1d08cde1a6061c3c7e2cb0564031b889e862704c3517969b29616dfc5423ecaa`
matches the independently built Darwin candidate's source receipt.

| Binary | SHA-256 |
|---|---|
| trident | 7aec6d61b72fb8f15180fe35c78a090c207eb3a6a68986c20ac5c12758fd62c4 |
| trisha | 6b34512d9c43f4789a7d12121c3f0dd0d8c16c3b5264802f3c5be94eb6c6cce0 |
| joy | 93520a1cff67eb2b535b217a34df90299706c5dab2dd0ae9e8de79bed5b89de7 |

Host receipts `/tmp/cyber-final3-linux/candidate.json`,
`/tmp/cyber-final3-linux/source-verification.json`, and the four `*-build.log`
files in that directory. Native ELF and fixture identities are recorded in
`/tmp/cyber-final3-linux-artifacts.log`.

The installed returning-loop aggregate-shadow regression passed12 cases:
inputs0/1/9, debug/release, nox/Triton, each output11. Nox uses the exact archived
`returning_loop_seals_shadowed_aggregate_type_with_its_name` test snippet. Triton
preserves that body as `regression` and adds explicit public-read/public-write
main because a raw main return is not public output. Both sources and the receipt
are retained in guest `final3-20260912/installed-loop-checked`; log
`/tmp/cyber-final3-linux-loop.log`. This is execution coverage, not proof coverage.


## Full archived installed proof smoke passed

The archived smoke script SHA-256 is
`616ef0406a71c2a68b501cd423048d83f5a4d744d6deebc17464a483de5156c3`.
Actual exit0 and genuine `smoke.json` with `all_checks_passed: true`;
elapsed196.699seconds, peak summed process-group RSS7,856,787,456bytes,
minimum available memory8,346,509,312bytes,949 samples, no guard stop.
The heavy slot was released after completion.

Executed real recursive Triton outer proving/verification; Joy source/build and
public `JOYEXEC2`, private `JOYZK003`, authenticated-public-state `JOYST001` paths;
hidden queries over bounded authenticated public tables; delegated tests; and
wrong claim/input/state/secret and tamper rejection. Public tables remain public;
this provides no private-database claim.

Receipts under `/tmp/cyber-final3-linux/`: `full-smoke.log`,
`full-smoke-memory.json`, `smoke.json`. Guest work:
`final3-20260912/installed-full`. The receipt binds the exact source verification,
product hashes, fixture bytes and smoke harness.

## Packaged native binaries passed

Used the **archived** `package-binaries.nu`, verified candidate/source inventory
and genuine complete smoke receipt. Host archive:
`/tmp/cyber-final3-linux/cyber-tools-linux-aarch64-final3.tar.gz`.
Size10,760,063bytes, SHA-256
`f182bccaf6996265ad20dcebe6cea953206204b4d261ab160b98f95e10315878`.

Independent host inspection verified19 entries with fixed `cyber-tools/` prefix,
all three ARM64 ELF binary hashes, exact genuine smoke receipt, all fixture hashes,
archived smoke script hash, source-verification hash, and license presence. Shipped
candidate metadata omits the machine-specific absolute source path. A second
packaging from the same inputs passed byte-for-byte `cmp`.

Receipts: `/tmp/cyber-final3-linux-package.log` and
`/tmp/cyber-final3-linux/archive-reproducibility.log`. This is native Ubuntu26.04
ARM64 execution; older glibc and native x86_64 are not established here.

## Actual pinned Neptune node admission passed

Archived `tools/neptune_node_gate.py` ran under a fresh `sudo unshare --net`
namespace using the new candidate Trisha and the preserved genuine zero-input,
zero-fee, zero-coin intent. Node0.15.1, revision
`9869b5e35b659dc520fad51ba5a9c812fed46db0`; node binary SHA-256
`442dc3da0977a6cba54db45cc9c251893351e690ca6807ff061693783d9dda00`.
Intent SHA-256
`4f3d8d38bef5911a57d07ff7f1fba83819b10388f26a9c2dd9974fe0b013c839`.

Actual SingleProof verification passed. Exactly the submitted kernel appeared
uniquely in the fresh mempool. Reusing its proof with an altered kernel was
rejected; incorrect gateway credentials were rejected before forwarding. Network
was real-proof `testnet-1`/chain4 in a loopback-only namespace. Elapsed2.597seconds.
No wallet funds, block production/confirmation or public network service was used.

Host receipt `/tmp/cyber-final3-linux/node-admission.json`, log
`/tmp/cyber-final3-linux-node.log`. The receipt's Trisha SHA matches the packaged
binary above. Cleanup completed; `/tmp/cyber-final3-linux/node-cleanup.log` records
no remaining node or gate process. Guest candidate/source and all prior receipts
are retained. No publication or repository commit was performed by this task.
