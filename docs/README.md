---
tags: trisha, docs
crystal-type: entity
crystal-domain: cyber
alias: Trisha documentation, Trisha docs
---
# Trisha documentation

## explanation

why Trisha works the way it does — design decisions and rationale.

- [[architecture]] — how trisha fits in the soft3 stack
- [[gpu-backend]] — seven shaders, one pipeline, Metal/Vulkan/DX12
- [[proof-file-format]] — TOML envelope + bincode proof bytes
- [[patching]] — vendor patching strategy: no fork, one script

## guides

task-oriented how-tos (not yet written).

- cli.md — run, prove, verify, batch, guess
- gpu.md — enabling GPU, reading dispatch stats, forcing CPU fallback
- proof-roundtrip.md — prove locally, transfer, verify remotely

## tutorials

learning by building (not yet written).

- first-proof.md — compile a hello.tri, prove it, verify it
- batch-proving.md — prove 10 programs in parallel, collect results

## reference

canonical spec lives in [reference/](../reference/).
