# Explicit imported aggregate fields

Trisha source `f472d6bad61f42626dba33bfc872bbcb324299a2`, tested against
Trident `2c66db3cb133ee6b461b7dc9f6e3cb0662a59c54`.

The imported aggregate and generic fixtures intentionally access fields across
module boundaries. Their fields now declare `pub`, matching Trident's enforced
module privacy. Input leaf validation, execution, and proof assertions remain.

`CARGO_TARGET_DIR=../trident/target cargo test --release --locked -p trisha-rs`:
362 passed, no failures, 4 existing heavy proof tests ignored.
`CARGO_TARGET_DIR=../trident/target cargo run --release --locked -p trisha -- bench`:
133/133 fixtures and 43/43 independent baselines verified. Every fixture
result/cycle row matches the preceding control-delivery bench with Trident
`4317c767607ce83210348d285c1390df0bed5d94`.
Tests and bench ran before the fixture commit; tested source was committed
unchanged. The subsequent
`CARGO_TARGET_DIR=../trident/target cargo check -p trisha-rs --all-targets --locked`
also passes without Rust warnings.

The coordinated receipt is `trident/audit/self-hosting/sh1-privacy-validation.json`.
Earlier fixture and raw-library visibility failures are retained there with
their log paths. This is local `release/0.4` compatibility evidence.
