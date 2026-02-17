# Trisha — Claude Code Instructions

Triton VM warrior. Execute, prove, verify, deploy Trident programs.

## Architecture

Trisha implements trident's `Runner`, `Prover`, `Verifier`, `Deployer`
traits for Triton VM + Neptune. Standalone binary (`trisha`) discovered
by trident via `find_warrior()`.

```
src/
  main.rs        Entry point, clap dispatch
  cli.rs         CLI subcommands (run, prove, verify, deploy)
  error.rs       TrishaError enum
  compile.rs     Source → ProgramBundle via trident API
  warrior.rs     TrishaWarrior: trait implementations
  proof_file.rs  TOML envelope + bincode proof bytes
  batch.rs       Batch/streaming prover
  deploy/        Neptune deployment (RPC, LockScript, UTXO, tx)
  gpu/           GPU acceleration (wgpu + WGSL shaders)
```

## Forbidden Patterns

- No `HashMap` — use `BTreeMap`
- No `.unwrap()` outside tests
- No `println!` in library code — stderr for progress, stdout for output
- No floating point
- No file > 500 lines

## Estimation Model

- **Pomodoro** = 30 minutes of focused work
- **Session** = 3 focused hours (6 pomodoros)

## Build & Test

```
cargo check
cargo test
cargo install --path .
```

## Git Workflow

Atomic commits. Conventional prefixes: `feat:`, `fix:`, `refactor:`,
`test:`, `docs:`, `chore:`.

## License

Cyber License: Don't trust. Don't fear. Don't beg.
