// ---
// tags: trident, rust
// crystal-type: source
// crystal-domain: comp
// ---
//! Moved from trident's api/tests/ — the core no longer lowers to Triton
//! assembly in-process (.claude/plans/warrior-owns-lowering.md S3 in
//! trident); this is now the warrior's own correctness suite.

use std::path::Path;

/// Compile a Triton source string, temp-file bridged (`build_tasm` takes a
/// path, not a source string).
#[allow(dead_code)]
fn compile_triton(source: &str, filename: &str) -> Result<String, String> {
    // A unique dir per call — parallel #[test] threads must not share a
    // path (build_tasm needs a real file: full module resolution runs
    // from it, unlike the in-memory compile this bridges).
    let dir = tempfile::tempdir().map_err(|e| e.to_string())?;
    let path = dir.path().join(filename);
    std::fs::write(&path, source).map_err(|e| e.to_string())?;
    trisha_rs::build_tasm(&path, "triton", "debug")
}

/// Like `compile_triton`, at a named profile (debug/release).
#[allow(dead_code)]
fn compile_triton_profile(source: &str, filename: &str, profile: &str) -> Result<String, String> {
    let dir = tempfile::tempdir().map_err(|e| e.to_string())?;
    let path = dir.path().join(filename);
    std::fs::write(&path, source).map_err(|e| e.to_string())?;
    trisha_rs::build_tasm(&path, "triton", profile)
}

/// Compile a project entry point (a real .tri file, resolved against the
/// trident repo checked out beside this one).
#[allow(dead_code)]
fn compile_project_triton(path: &Path) -> Result<String, String> {
    ensure_trident_lib_env();
    trisha_rs::build_tasm(path, "triton", "debug")
}

/// Point the module resolver at trident's std/os libraries. Its own search
/// (env var, then walking up from the compiler binary or the cwd) assumes a
/// process running inside the trident repo; trisha's tests run from their
/// own workspace, so name the sibling repo explicitly (env vars win over
/// every other search step trident's resolver tries).
#[allow(dead_code)]
fn ensure_trident_lib_env() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../trident");
    std::env::set_var("TRIDENT_STDLIB", root.join("std"));
    std::env::set_var(
        "TRIDENT_OSLIB",
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../os"),
    );
}

/// A stdlib/vm/os path is relative to the trident repo root; trisha's own
/// tests run from trisha's workspace root, so re-root them at `../trident`
/// (the sibling-repo layout every companion-repo doc in this stack assumes).
#[allow(dead_code)]
fn trident_repo_path(rel: &str) -> std::path::PathBuf {
    if rel.starts_with("os/neptune/") {
        return Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join(rel);
    }
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../trident")
        .join(rel)
}

/// Helper: compile a .tri file and assert it succeeds, returning the TASM.
fn assert_compiles(rel_path: &str) -> String {
    let p = trident_repo_path(rel_path);
    if !p.exists() {
        panic!("{} does not exist", p.display());
    }
    match compile_project_triton(&p) {
        Ok(tasm) => {
            if tasm.is_empty() {
                // Intrinsic/type-only libraries intentionally emit no functions.
                let source = std::fs::read_to_string(&p).unwrap();
                let file = trident::parse_source_silent(&source, rel_path).unwrap();
                assert!(
                    !file.items.iter().any(
                        |item| matches!(&item.node, trident::ast::Item::Fn(f) if f.body.is_some())
                    ),
                    "{} lost function bodies",
                    rel_path
                );
            } else {
                triton_vm::prelude::Program::from_code(&tasm)
                    .unwrap_or_else(|e| panic!("{} emitted invalid TASM: {}", rel_path, e));
            }
            tasm
        }
        Err(msg) => {
            panic!("{} failed to compile: {}", rel_path, msg);
        }
    }
}

// ── VM layer ──

#[test]
fn vm_core_field_compiles() {
    assert_compiles("vm/core/field.tri");
}

#[test]
fn vm_core_convert_compiles() {
    assert_compiles("vm/core/convert.tri");
}

#[test]
fn vm_core_u32_compiles() {
    assert_compiles("vm/core/u32.tri");
}

#[test]
fn vm_core_assert_compiles() {
    assert_compiles("vm/core/assert.tri");
}

#[test]
fn vm_io_io_compiles() {
    assert_compiles("vm/io/io.tri");
}

#[test]
fn vm_io_mem_compiles() {
    assert_compiles("vm/io/mem.tri");
}

#[test]
fn vm_crypto_hash_compiles() {
    assert_compiles("vm/crypto/hash.tri");
}

#[test]
fn vm_crypto_merkle_compiles() {
    assert_compiles("vm/crypto/merkle.tri");
}

// ── std layer ──

#[test]
fn std_crypto_poseidon2_compiles() {
    assert_compiles("std/crypto/poseidon2.tri");
}

#[test]
fn std_crypto_poseidon_compiles() {
    assert_compiles("std/crypto/poseidon.tri");
}

#[test]
fn std_crypto_sha256_compiles() {
    assert_compiles("std/crypto/sha256.tri");
}

#[test]
fn std_crypto_keccak256_compiles() {
    assert_compiles("std/crypto/keccak256.tri");
}

#[test]
fn std_crypto_auth_compiles() {
    assert_compiles("std/crypto/auth.tri");
}

#[test]
fn std_crypto_merkle_compiles() {
    assert_compiles("std/crypto/merkle.tri");
}

#[test]
fn std_crypto_bigint_compiles() {
    assert_compiles("std/crypto/bigint.tri");
}

#[test]
fn std_crypto_ecdsa_compiles() {
    assert_compiles("std/crypto/ecdsa.tri");
}

#[test]
fn std_crypto_ed25519_compiles() {
    assert_compiles("std/crypto/ed25519.tri");
}

#[test]
fn std_crypto_secp256k1_compiles() {
    assert_compiles("std/crypto/secp256k1.tri");
}

#[test]
fn std_io_storage_compiles() {
    assert_compiles("std/io/storage.tri");
}

#[test]
fn std_nn_tensor_compiles() {
    assert_compiles("std/nn/tensor.tri");
}

#[test]
fn std_private_poly_compiles() {
    assert_compiles("std/private/poly.tri");
}

#[test]
fn std_quantum_gates_compiles() {
    assert_compiles("std/quantum/gates.tri");
}

#[test]
fn std_trinity_inference_compiles() {
    assert_compiles("std/trinity/inference.tri");
}

#[test]
fn std_target_compiles() {
    assert_compiles("std/target.tri");
}

// ── OS layer ──

#[test]
fn os_neptune_kernel_compiles() {
    assert_compiles("os/neptune/kernel.tri");
}

#[test]
fn os_neptune_proof_compiles() {
    assert_compiles("os/neptune/proof.tri");
}

#[test]
fn os_neptune_recursive_compiles() {
    assert_compiles("os/neptune/recursive.tri");
}

#[test]
fn os_neptune_xfield_compiles() {
    assert_compiles("os/neptune/xfield.tri");
}

#[test]
fn os_neptune_utxo_compiles() {
    assert_compiles("os/neptune/utxo.tri");
}

#[test]
fn os_neptune_plumb_compiles() {
    assert_compiles("os/neptune/standards/plumb.tri");
}

// Programs requiring runtime input — compilation must succeed

#[test]
fn os_neptune_locks_generation_compiles() {
    assert_compiles("os/neptune/locks/generation.tri");
}

#[test]
fn os_neptune_locks_symmetric_compiles() {
    assert_compiles("os/neptune/locks/symmetric.tri");
}

#[test]
fn os_neptune_locks_multisig_compiles() {
    assert_compiles("os/neptune/locks/multisig.tri");
}

#[test]
fn os_neptune_locks_timelock_compiles() {
    assert_compiles("os/neptune/locks/timelock.tri");
}

#[test]
fn os_neptune_standards_coin_compiles() {
    assert_compiles("os/neptune/standards/coin.tri");
}

#[test]
fn os_neptune_standards_card_compiles() {
    assert_compiles("os/neptune/standards/card.tri");
}

#[test]
fn os_neptune_types_custom_token_compiles() {
    assert_compiles("os/neptune/types/custom_token.tri");
}

#[test]
fn os_neptune_types_native_currency_compiles() {
    assert_compiles("os/neptune/types/native_currency.tri");
}

#[test]
fn os_neptune_programs_proof_relay_compiles() {
    assert_compiles("os/neptune/programs/proof_relay.tri");
}

#[test]
fn os_neptune_programs_proof_aggregator_compiles() {
    assert_compiles("os/neptune/programs/proof_aggregator.tri");
}

#[test]
fn os_neptune_programs_recursive_verifier_compiles() {
    assert_compiles("os/neptune/programs/recursive_verifier.tri");
}

#[test]
fn os_neptune_programs_transaction_validation_compiles() {
    assert_compiles("os/neptune/programs/transaction_validation.tri");
}
