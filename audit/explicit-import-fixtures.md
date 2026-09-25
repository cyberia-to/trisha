# Explicit import fixture compatibility

Trisha source `ef186c359e9e268c815055ff69356fa7ff84fd60` with Trident
`ef4ea23f75446a4f87a12714653f37e1315b9e44`. [Pinned validation](explicit-import-fixtures.json)
records commands, sibling inputs, installed binaries and baseline rows.

Halting fixtures use exact `ext.*` and `a.*` owner paths and direct imports.
Their debug/release execution assertions are retained. Malformed source is now
rejected by Trident's TIR builder; a separate external error-comment input still
verifies Trisha's own admission boundary. Runtime implementation is unchanged.

`cargo check --workspace --all-targets --locked --offline` and
`cargo test --release --locked --offline -p trisha-rs --no-fail-fast` pass with
380 CPU tests, four existing ignores and zero Rust warnings. The
`cargo run --release --locked --offline -p trisha -- bench` output retains all
133 fixture rows and 43 manual baselines. Fourteen packaged Trisha libraries pass
installed target checks. The coordinated receipt also records 27 cross-backend
observations and 15 direct-TIR executions. All three installed binaries reproduce
the executed bytes after both source commits.

This is development acceptance for `release/0.4`. Guest imports, self-compilation,
six-platform fixed-point acceptance and native Zheng compiler proof gates remain
open in the [coordinated ledger](../../trident/audit/self-hosting-progress.md).
