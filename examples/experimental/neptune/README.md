# Unimplemented recursive proof prototypes

These sources are preserved for research and are excluded from the installed target package. They are not recursive STARK verifiers or transaction validators. In particular, `proof.verify_inner_proof` computes FRI/OOD/constraint values without enforcing their required consistency. Its former acceptance behavior must not authorize transactions or be treated as proof verification.

The production Neptune package does not export `os.neptune.proof`; these entry programs intentionally fail compilation when they import it. CPU Triton proofs generated and verified by Trisha remain available, separately from these unimplemented recursive protocols. No security level is established by selecting a number of prototype FRI rounds.
