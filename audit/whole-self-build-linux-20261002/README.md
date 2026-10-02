# Original native Linux full-self-build attempt: failed deadline

Both complete-compiler producers in [Actions run 36961998100](https://github.com/cyberia-to/trisha/actions/runs/36961998100), attempt 1, failed at the original 7,200-second internal deadline. The run used committed workflow revision `5d14ae46f327a7f0ee1f9812b4ba62b73cf035bc`, the exact accepted C1/C2 compiler and JOB files, Rust 1.89.0, and the original whole-proof bounds. No complete Linux certificate or fresh verification resulted. The proof-retention steps were skipped; the raw success-or-failure metadata steps succeeded.

| Observation | C1 → C2 command | C2 → C3 command |
|---|---:|---:|
| `prove-artifact` elapsed ns | 7,200,797,057,950 | 7,200,774,966,007 |
| Maximum sampled RSS bytes | 922,411,008 | 924,831,744 |
| Maximum sampled attempt-directory bytes | 6,522,480,951 | 6,373,646,574 |
| Elapsed ns at that size sample | 7,199,171,062,273 | 7,199,400,465,589 |
| Minimum sampled free bytes | 114,790,010,880 | 114,940,366,848 |
| Native release-build elapsed ns | 89,655,317,240 | 91,058,296,171 |
| Bootstrap-to-prove elapsed ns | 200,944,366,594 | 197,282,004,658 |
| Resource samples | 7,133 | 7,133 |

These values are replayed from each original artifact's `receipt.json` and `prove-resources.jsonl`; the precise commands, tool identities and source revision are in those receipts. Both prove commands exited 1 with empty stdout and this exact stderr:

```
error: execution error: certificate execution/capture: Capture(Cancelled)
```

The outer guard did not record `resource_stop`. The original host budget was 20 billion charged reductions, 1 billion cumulative allocations, 3,145,728 resident nouns, 65,536 frames, 10 billion collection work, and 7,200,000 ms. Certificate limits were 24 GiB encoded, 96 GiB decoded, 12 billion records, 16 billion expanded steps and 262,144 summary slots. Outer limits remained 7,500 seconds, 6 GiB sampled RSS, 30 GiB attempt storage, 48 GiB free at production start and an 8 GiB free-space floor.

The aggregate directory-size samples do not record individual filenames or their hashes. They measure unpublished partial output, not semantic completion. The final sample in each run records zero attempt bytes. The retained `joy/cli/certificate.rs` calls `atomic_produce`; `joy/cli/publication.rs` removes the private staging file when production returns an error. Partial certificate contents were therefore neither published nor included in the metadata artifacts.

## Deadline source and evidence integrity

`deadline-source/` retains the exact Joy/Nox source involved. Each file is checked against both native runners' committed-source before-inventories. Joy's `pipeline.rs` starts the deadline before admission and passes `Instant::now() >= expires` as the observer cancellation callback. Nox `capture.rs` returns `CaptureFailure::Cancelled` when that callback becomes true. Joy `limits.rs` and `structured-run.md` also impose a 7,200,000 ms compacting host ceiling. A longer command-line timeout alone cannot run on this pin.

The two source before-inventories match exactly: 12 repositories and 14,495 tracked file entries, with identical Cargo package closure. All 145 preparation commands per generation passed, including native release build and exact JOB reconstruction. Compiler, JOB and executable before/after identities match for each prove command. Each complete job took approximately 123 minutes, including setup and failure-artifact retention.

The driver failed before its final full-source and frozen-package inventories. Those final inventories are absent. This evidence therefore establishes the recorded preparation inventory and the actual prove command's before/after identities; it does not establish a complete post-run source-closure replay.

The two actual native executables have different SHA-256 identities, retained without substitution in the original archives. This attempt does not claim identical native executable bytes. No runtime or hashing performance bottleneck was profiled; the measured stopping condition is the physical deadline.

`raw/` contains the original two GitHub metadata artifact ZIPs, the Actions log ZIP, API metadata, API stderr and collection receipt. All 610 archived files are retained, including native executables and full raw resource samples. GitHub's artifact digests match the downloaded ZIPs. The original Actions artifacts expire on 2026-11-01; these committed copies preserve the bytes. The 16,637,580-byte frozen input archive remains asset `604704433` on the existing draft release; its exact 111-file inventory is retained as `frozen-input-files.json`. The archive itself is not duplicated here.

Replay locally from the repository root:

```
python3 -B audit/whole-self-build-linux-20261002/check.py
```

`replay.json` and the empty `replay.stderr` retain that check's output. It reads archives, compares all archived bytes with the collection inventory, verifies raw command log and executable identities, checks source/input bindings, and recomputes resource summaries. It performs no network access and executes no compiler, producer or verifier. `passed-integrity-replay` describes evidence integrity; both execution results remain failed.

`collect.py`, `monitor.py` and `monitor-completed.json` retain the read-only collection/monitoring provenance. `local-proof-reference.json` is an earlier, explicitly parent-reported local comparison reference. Its historical C1 verifier status remains unchanged; no complete local certificate was read or rehashed by this audit. No retry, host-limit change, release promotion or tag was performed to produce this report.
