# Final Joy host deadline package evidence

Status: contract, source dependency scope and conditional full198 inheritance
checker are reviewed. Native final package source export remains pending the
remaining source guard and runner review.

`installed-probe-trial/` records the actual installed Joy binary from merged
source `dd61df9128f6da1f97d4698f45f154f05312fe51` (the measured implementation
commit has the same tree), SHA-256
`d81d61c400148f7b674b4e1a471f6b828773416681d210ccdd34437431357bd9`.
The explicit helper candidate is a probe harness against unchanged compiler
vectors from source734; it is not a final coordinated package.

The recorded command passed 23 bounded installed commands: 15 accepted and
8 rejected. Compaction proof generation at 30000, 7200000 and 14400000 ms
produced byte-identical certificates; all nine producer/verifier deadline
combinations had identical claims and extracted program bytes. The extracted
program returned the expected result. Zero, 14400001 and u64-max limits were
rejected by both commands without replacing an existing output. Ordinary
non-compacting prove/verify accepted 300000 and rejected 300001 ms. Exact
binary, fixture and original command streams are preserved with a manifest.
The native final runner will repeat this check on each actual final package.

`root-inheritance-review/` retains the independent source review, actual
positive replay and six mutation checks for conditional inherited full198
coverage. Its original review JSON has SHA-256
`39ac96ee5f669f776163b0fea0a8145f1e7e00c4e5c6b0ba50043710a03bb652`.
This helper check uses the original tested source734 worker as its positive
control; it does not assert that any future rebuilt Trisha is identical.
