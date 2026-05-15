---
tags: trisha, docs
crystal-type: pattern
crystal-domain: cyber
alias: trisha patching, vendor patching
---
# vendor patching

trisha needs GPU acceleration hooks inside triton-vm — dispatch points that don't exist upstream. the options are:

1. maintain a fork — merge upstream changes manually forever
2. patch at build time — fetch upstream, overlay changes, reference via path

trisha uses option 2. `patches/apply.nu` fetches triton-vm from cargo registry and surgically applies five named layers.

## layers

```
layer 0  copy gpu.rs into vendor/
layer 1  export `pub mod gpu` in triton-vm's lib.rs
layer 2  widen `pub(crate)` → `pub` on types trisha needs
layer 3  insert GPU dispatch for Tip5 batch hashing
layer 4  insert GPU dispatch for iNTT (polynomial interpolation)
```

the result lands in `.vendor/triton-vm/`. `Cargo.toml` patches the crates.io version via:

```toml
[patch.crates-io]
twenty-first = { path = ".vendor/twenty-first" }

[dependencies]
triton-vm = { path = ".vendor/triton-vm" }
```

`.vendor/` is gitignored. every developer runs `nu patches/apply.nu` once after clone.

## upgrading triton-vm

1. update `version` in `patches/apply.nu`
2. run `nu patches/apply.nu`
3. fix any patch conflicts (the string-replace targets may have moved)
4. rebuild: `cargo check`

the patch is intentionally minimal — only what trisha needs. the smaller the patch, the easier the upgrade.

## why not a fork

a fork requires tracking upstream commits, resolving merge conflicts, and eventually diverging. the patch script is idempotent and version-pinned. when triton-vm ships native GPU hooks upstream, `patches/apply.nu` can be deleted and the path dependency replaced with the crates.io version.
