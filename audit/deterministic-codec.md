# Deterministic codec derives

Trisha `765819f02b2dd69b83dd083544072d07352a5237` owns the pinned macro overlay; Joy `c2aa7862f46ea3f70f9a694c9c33d92e383ced5c`
selects its existing macro version. Trident input is `a166c8de6fb39e992a8dbc2bd6fe0466e1629ad7`.
The [receipt](deterministic-codec-validation.json) records the source revisions,
commands, exact outputs and binary identities.

`bfieldcodec_derive` generated error variants and display arms by iterating a
randomized HashMap. An executable regression reproduces the differing expansion.
The overlay uses BTreeMap at the existing versions0.7.0 (Trisha) and0.7.1 (Joy).
Each patched macro passes8 tests; four upstream doc tests remain ignored per
version. Source enum wire tags, field order and encode/decode logic retain their
upstream definitions. Generated error enums have no stable Rust discriminant ABI.

Two fresh builds at the same source/target paths produce identical Trident,
Joy and Trisha bytes. A clean post-commit install matches them. C1 and the module
graph artifact retain their prior complete bytes. A fresh temporary bootstrap
reproduces every macro Rust/manifest file used by those builds. Reproduction
across different paths, toolchains or platforms is outside this check.

All seven owner gates pass without warnings:1175 Trident tests,122 Joy tests,
380 Trisha tests and4 pre-existing ignored tests. All133 benchmark rows, including
43 manual baselines, equal the accepted baseline. Three archive/pin tests pass.
Earlier differing binary receipts are retained; cached reinstalls alone did not
establish clean-build reproducibility.

The coordinated guest nominal-import corpus is being rerun against these frozen
binaries in Trident. Complete self-hosting and native compiler proofs retain
their own gates.
