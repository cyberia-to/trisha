# Checked TIR builder compatibility — 2026-09-23

The Trident 0.4 native Noun extension makes TIRBuilder::build_file fallible so
native trees cannot silently enter a fixed-word backend. The two direct test
call sites now unwrap their expected successful fixed-layout construction.
Production Trisha APIs already propagate Trident's Result-returning APIs.
No Triton instruction selection or proof relation changes in this patch.

Validation with the coordinated Trident feature: trisha-rs: 362 passed, 0 failed,
4 existing expensive proof gates ignored. `trisha bench` executes 133/133
fixtures and verifies 43/43 independent baselines. Ignored tagged/outer proof
gates were not rerun and are not claimed as validation of this change.
Logs: /tmp/trisha-04-tir-tests.log and /tmp/trisha-04-tir-bench.log.
Integration branch release/0.4 starts from released ba5fca686c81dbf4c5cd1970b309553b0d875b14.
Master stays unchanged.
