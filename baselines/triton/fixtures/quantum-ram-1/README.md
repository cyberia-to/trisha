# RAM matrix application

Together with `quantum-ram-2` and `quantum-ram-3`, these fixtures exercise every target bit for 1–3 qubits with a full non-real complex 2x2 matrix. An independent integer oracle computes all output coordinates modulo Goldilocks; cells immediately outside the buffer must remain unchanged. Invalid dimensions, target indices and end addresses must reject.

`apply_single_gate` accepts 1 <= n <= 12, target < n and a buffer whose first and last address fit U32. Checks precede state mutation. Hand benchmark scratch `[2^40, 2^40 + 64)` is private to this routine and is clobbered; accepted state buffers cannot overlap it. Other RAM contents are preserved.

Regenerate fixtures with `python3 scripts/generate_quantum_ram_fixtures.py`. The hand body comes from `scripts/quantum_ram.py`, integrated by `scripts/generate_quantum_baseline.py`. These are finite-field matrix equations, not a physical quantum experiment or a proof of unitarity. Normalization remains the caller’s responsibility.
