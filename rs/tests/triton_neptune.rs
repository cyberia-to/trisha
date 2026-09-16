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
    trisha_rs::build_tasm(&path, "neptune", "debug")
}

/// Like `compile_triton`, at a named profile (debug/release).
#[allow(dead_code)]
fn compile_triton_profile(source: &str, filename: &str, profile: &str) -> Result<String, String> {
    let dir = tempfile::tempdir().map_err(|e| e.to_string())?;
    let path = dir.path().join(filename);
    std::fs::write(&path, source).map_err(|e| e.to_string())?;
    trisha_rs::build_tasm(&path, "neptune", profile)
}

/// Compile a project entry point (a real .tri file, resolved against the
/// trident repo checked out beside this one).
#[allow(dead_code)]
fn compile_project_triton(path: &Path) -> Result<String, String> {
    trisha_rs::build_tasm(path, "neptune", "debug")
}

/// A stdlib/vm/os path is relative to the trident repo root; trisha's own
/// tests run from trisha's workspace root, so re-root them at `../trident`
/// (the sibling-repo layout every companion-repo doc in this stack assumes).
#[allow(dead_code)]
fn trident_repo_path(rel: &str) -> std::path::PathBuf {
    if let Some(name) = rel.strip_prefix("os/neptune/") {
        if name.starts_with("locks/") || name.starts_with("types/") || matches!(name, "standards/coin.tri" | "standards/card.tri") {
            return Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/neptune").join(name);
        }
    }
    if let Some(name) = rel.strip_prefix("os/neptune/programs/") {
        return Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../examples/experimental/neptune")
            .join(name);
    }
    if rel.starts_with("os/neptune/") || rel.starts_with("vm/triton/") {
        return Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../lib")
            .join(rel);
    }
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../trident/lib")
        .join(rel)
}

#[test]
fn test_recursive_verifier_is_rejected() {
    assert_experimental_rejected("recursive_verifier.tri");
}

#[test]
fn test_xfield_dot_step_intrinsics() {
    let dir = tempfile::tempdir().unwrap();
    // Write the entry program that uses xx_dot_step via os.neptune.xfield
    let main_path = dir.path().join("main.tri");
    std::fs::write(
        &main_path,
        r#"program test
use os.neptune.xfield

fn main() {
let ptr_a: Field = divine()
let ptr_b: Field = divine()
let result = xfield.xx_dot_step(xfield.new(0, 0, 0), ptr_a, ptr_b)
let (acc, r3, r4) = result
let (r0, r1, r2) = acc
pub_write(r0)
}
"#,
    )
    .unwrap();
    // Create os/neptune directory and copy xfield.tri
    let ext_dir = dir.path().join("os").join("neptune");
    std::fs::create_dir_all(&ext_dir).unwrap();
    std::fs::copy(
        trident_repo_path("os/neptune/xfield.tri"),
        ext_dir.join("xfield.tri"),
    )
    .unwrap_or_default();

    let result = compile_project_triton(&main_path);
    assert!(
        result.is_ok(),
        "xx_dot_step intrinsic should compile: {:?}",
        result.err()
    );
    let tasm = result.unwrap();
    assert!(
        tasm.contains("xx_dot_step"),
        "emitted TASM should contain xx_dot_step"
    );
}

#[test]
fn test_xb_dot_step_intrinsic() {
    let dir = tempfile::tempdir().unwrap();
    let main_path = dir.path().join("main.tri");
    std::fs::write(
        &main_path,
        r#"program test
use os.neptune.xfield

fn main() {
let ptr_a: Field = divine()
let ptr_b: Field = divine()
let result = xfield.xb_dot_step(xfield.new(0, 0, 0), ptr_a, ptr_b)
let (acc, r3, r4) = result
let (r0, r1, r2) = acc
pub_write(r0)
}
"#,
    )
    .unwrap();
    let ext_dir = dir.path().join("os").join("neptune");
    std::fs::create_dir_all(&ext_dir).unwrap();
    std::fs::copy(
        trident_repo_path("os/neptune/xfield.tri"),
        ext_dir.join("xfield.tri"),
    )
    .unwrap_or_default();

    let result = compile_project_triton(&main_path);
    assert!(
        result.is_ok(),
        "xb_dot_step intrinsic should compile: {:?}",
        result.err()
    );
    let tasm = result.unwrap();
    assert!(
        tasm.contains("xb_dot_step"),
        "emitted TASM should contain xb_dot_step"
    );
}

#[test]
fn test_xfe_inner_product_library() {
    let dir = tempfile::tempdir().unwrap();
    let main_path = dir.path().join("main.tri");
    std::fs::write(
        &main_path,
        r#"program test
use os.neptune.recursive

fn main() {
let ptr_a: Field = divine()
let ptr_b: Field = divine()
let count: Field = divine()
let result = recursive.xfe_inner_product(ptr_a, ptr_b, count)
let (acc, r3, r4) = result
let (r0, r1, r2) = acc
pub_write(r0)
pub_write(r1)
pub_write(r2)
}
"#,
    )
    .unwrap();
    // Copy library files
    let ext_dir = dir.path().join("os").join("neptune");
    std::fs::create_dir_all(&ext_dir).unwrap();
    std::fs::copy(
        trident_repo_path("os/neptune/xfield.tri"),
        ext_dir.join("xfield.tri"),
    )
    .unwrap_or_default();
    std::fs::copy(
        trident_repo_path("os/neptune/recursive.tri"),
        ext_dir.join("recursive.tri"),
    )
    .unwrap_or_default();
    // Copy vm files that recursive.tri depends on
    let vm_io = dir.path().join("vm").join("io");
    let vm_core = dir.path().join("vm").join("core");
    std::fs::create_dir_all(&vm_io).unwrap();
    std::fs::create_dir_all(&vm_core).unwrap();
    std::fs::copy(trident_repo_path("vm/io/io.tri"), vm_io.join("io.tri")).unwrap_or_default();
    std::fs::copy(
        trident_repo_path("vm/core/assert.tri"),
        vm_core.join("assert.tri"),
    )
    .unwrap_or_default();

    let result = compile_project_triton(&main_path);
    assert!(
        result.is_ok(),
        "xfe_inner_product should compile: {:?}",
        result.err()
    );
    let tasm = result.unwrap();
    assert!(
        tasm.contains("xx_dot_step"),
        "inner product should use xx_dot_step"
    );
}

#[test]
fn test_xb_inner_product_library() {
    let dir = tempfile::tempdir().unwrap();
    let main_path = dir.path().join("main.tri");
    std::fs::write(
        &main_path,
        r#"program test
use os.neptune.recursive

fn main() {
let ptr_a: Field = divine()
let ptr_b: Field = divine()
let count: Field = divine()
let result = recursive.xb_inner_product(ptr_a, ptr_b, count)
let (acc, r3, r4) = result
let (r0, r1, r2) = acc
pub_write(r0)
}
"#,
    )
    .unwrap();
    let ext_dir = dir.path().join("os").join("neptune");
    std::fs::create_dir_all(&ext_dir).unwrap();
    std::fs::copy(
        trident_repo_path("os/neptune/xfield.tri"),
        ext_dir.join("xfield.tri"),
    )
    .unwrap_or_default();
    std::fs::copy(
        trident_repo_path("os/neptune/recursive.tri"),
        ext_dir.join("recursive.tri"),
    )
    .unwrap_or_default();
    let vm_io = dir.path().join("vm").join("io");
    let vm_core = dir.path().join("vm").join("core");
    std::fs::create_dir_all(&vm_io).unwrap();
    std::fs::create_dir_all(&vm_core).unwrap();
    std::fs::copy(trident_repo_path("vm/io/io.tri"), vm_io.join("io.tri")).unwrap_or_default();
    std::fs::copy(
        trident_repo_path("vm/core/assert.tri"),
        vm_core.join("assert.tri"),
    )
    .unwrap_or_default();

    let result = compile_project_triton(&main_path);
    assert!(
        result.is_ok(),
        "xb_inner_product should compile: {:?}",
        result.err()
    );
    let tasm = result.unwrap();
    assert!(
        tasm.contains("xb_dot_step"),
        "xb inner product should use xb_dot_step"
    );
}

#[test]
fn test_proof_composition_library() {
    assert!(trisha_rs::target::package("neptune")
        .unwrap()
        .modules
        .get("os.neptune.proof")
        .is_none());
    let error = compile_triton(
        "program rejected\nuse os.neptune.proof\nfn main() { proof.verify_inner_proof(0) }\n",
        "rejected.tri",
    )
    .unwrap_err();
    assert!(error.contains("os.neptune.proof"), "{error}");
}

#[test]
fn test_proof_aggregation() {
    assert_experimental_rejected("proof_aggregator.tri");
}

#[test]
fn test_proof_relay_example_is_rejected() {
    assert_experimental_rejected("proof_relay.tri");
}

#[test]
fn test_proof_aggregator_example_is_rejected() {
    assert_experimental_rejected("proof_aggregator.tri");
}

#[test]
fn test_transaction_validation_is_rejected() {
    assert_experimental_rejected("transaction_validation.tri");
}

#[test]
fn test_neptune_lock_scripts_compile() {
    for name in &["generation", "symmetric", "multisig", "timelock"] {
        let path_str = format!("os/neptune/locks/{}.tri", name);
        let path = trident_repo_path(&path_str);
        if !path.exists() {
            continue;
        }
        let result = compile_project_triton(&path);
        assert!(
            result.is_ok(),
            "{} should compile: {:?}",
            name,
            result.err()
        );
    }
}

#[test]
fn test_neptune_type_scripts_compile() {
    for name in &["native_currency", "custom_token"] {
        let path_str = format!("os/neptune/types/{}.tri", name);
        let path = trident_repo_path(&path_str);
        if !path.exists() {
            continue;
        }
        let result = compile_project_triton(&path);
        assert!(
            result.is_ok(),
            "{} should compile: {:?}",
            name,
            result.err()
        );
    }
}

#[test]
fn coin_formatting_is_idempotent() {
    let source = include_str!("../../examples/neptune/standards/coin.tri");
    let formatted = trident::format_source(source, "coin.tri").unwrap();
    let twice = trident::format_source(&formatted, "coin.tri").unwrap();
    assert_eq!(formatted, twice);
}

fn assert_experimental_rejected(name: &str) {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../examples/experimental/neptune")
        .join(name);
    let error = trisha_rs::build_tasm(&path, "neptune", "debug").unwrap_err();
    assert!(error.contains("os.neptune.proof"), "{error}");
}
