# Trinity arithmetic fixtures

Together with `../trinity-descending`, this runs all 29 arguments through the composed arithmetic demo and rejects an incorrect decryption witness. Regenerate both fixtures and the independent hand implementation with `python3 scripts/generate_trinity_baseline.py` from the Trisha repository.

The fixed plaintexts, matrix outputs, custom hash, LUT witness and PBS witness transport are computed independently. These are functional checks, not a security claim for TFHE, private inference or quantum commitments. See Trident `reference/trinity-arithmetic.md` for the missing cryptographic bindings.
