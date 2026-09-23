use std::fs;
use trisha_rs::test::run_tests;

#[test]
fn actual_vm_tests_preserve_main_private_helpers_imports_and_isolate_ram() {
    let dir = tempfile::tempdir().unwrap();
    fs::write(dir.path().join("helper.tri"), "module helper\nfn private_value() -> Field { 7 }\npub fn value() -> Field { private_value() }\n#[test]\nfn imported_test() { assert(value() == 7) }").unwrap();
    let entry = dir.path().join("main.tri");
    fs::write(&entry, "program original\nuse helper\nfn main() -> Field { 11 }\nfn local() -> Field { main() + helper.value() }\n#[test]\nfn preserves_definitions() { assert(local() == 18) }\n#[test]\nfn first() { ram_write(100, 42) }\n#[test]\nfn isolated() { assert(ram_read(100) == 0) }").unwrap();
    let report = run_tests(&entry, "triton", "debug").unwrap();
    assert!(report.contains("4 passed; 0 failed; 0 skipped"), "{report}");
    assert!(report.contains("helper.imported_test ... ok"), "{report}");
}

#[test]
fn failures_are_aggregated_and_main_is_not_implicitly_executed() {
    let dir = tempfile::tempdir().unwrap();
    let entry = dir.path().join("main.tri");
    fs::write(&entry, "program failures\nfn main() { assert(false) }\n#[test]\nfn first() { assert(true) }\n#[test]\nfn second() { assert(false) }\n#[test]\nfn third() { assert(true) }").unwrap();
    let report = run_tests(&entry, "triton", "debug").unwrap_err();
    assert!(report.contains("2 passed; 1 failed"), "{report}");
    assert!(report.contains("failures.third ... ok"), "{report}");
}

#[test]
fn manifest_entry_dependency_and_profile_apply_to_tests() {
    let dir = tempfile::tempdir().unwrap();
    fs::create_dir(dir.path().join("vendor")).unwrap();
    fs::write(dir.path().join("trident.toml"), "[project]\nname = \"fixture\"\nentry = \"entry.tri\"\ntarget = \"triton\"\n[targets.debug]\nflags = [\"custom\"]\n[dependencies]\nhelper = { path = \"vendor\" }\n").unwrap();
    fs::write(dir.path().join("main.tri"), "invalid source").unwrap();
    fs::write(
        dir.path().join("vendor/helper.tri"),
        "module helper\n#[cfg(custom)]\npub fn value() -> Field { 7 }",
    )
    .unwrap();
    fs::write(dir.path().join("entry.tri"), "program configured\nuse helper\nfn main() { assert(false) }\n#[cfg(test)]\n#[test]\nfn enabled() { assert(helper.value() == 7) }\n#[cfg(release)]\n#[test]\nfn skipped() { assert(false) }").unwrap();
    let report = run_tests(dir.path(), "triton", "debug").unwrap();
    assert!(report.contains("1 passed; 0 failed; 1 skipped"), "{report}");
}

#[test]
fn no_tests_and_invalid_signatures_are_not_counted_as_passes() {
    let dir = tempfile::tempdir().unwrap();
    let entry = dir.path().join("main.tri");
    fs::write(
        &entry,
        "program none\nfn main() {}\n#[cfg(release)]\n#[test]\nfn skipped() { assert(false) }",
    )
    .unwrap();
    let report = run_tests(&entry, "triton", "debug").unwrap();
    assert!(report.contains("0 passed; 0 failed; 1 skipped"), "{report}");
    fs::write(
        &entry,
        "program invalid\nfn main() {}\n#[test]\nfn invalid(x: Field) { assert(true) }",
    )
    .unwrap();
    assert!(run_tests(&entry, "triton", "debug").is_err());
}

#[test]
fn aggregate_loop_assignments_preserve_counters_and_neighboring_values() {
    let dir = tempfile::tempdir().unwrap();
    let entry = dir.path().join("main.tri");
    fs::write(&entry, "program aggregate\nuse os.neptune.recursive\nuse vm.io.mem\nfn main() {}\n#[test]\nfn xfield_loop() { mem.write(100,2) mem.write(101,3) mem.write(102,4) mem.write(200,5) let (acc,a,b)=recursive.xb_inner_product(100,200,1) let (x,y,z)=acc assert(x == 10) assert(y == 15) assert(z == 20) assert(a == 103) assert(b == 201) }\n#[test]\nfn tuple_loop() { let guard = 9\n let mut pair: (Field, Field) = (1,2)\n for i in 0..3 { pair = (3,4) }\n let (a,b) = pair\n assert(a == 3) assert(b == 4) assert(guard == 9) }").unwrap();
    let report = run_tests(&entry, "neptune", "debug").unwrap();
    assert!(report.contains("2 passed; 0 failed"), "{report}");
}

#[test]
fn imported_nested_struct_field_paths_use_declared_types_and_offsets() {
    let dir = tempfile::tempdir().unwrap();
    let entry = dir.path().join("main.tri");
    fs::write(&entry, "program nested\nuse std.quantum.gates\nfn main() {}\n#[test]\nfn cnot_fields() { let state=gates.TwoQubit { q00: gates.Complex { re: 1, im: 2 }, q01: gates.Complex { re: 3, im: 4 }, q10: gates.Complex { re: 5, im: 6 }, q11: gates.Complex { re: 7, im: 8 } } let result=gates.cnot(state) assert(result.q00.re == 1) assert(result.q00.im == 2) assert(result.q01.re == 3) assert(result.q01.im == 4) assert(result.q10.re == 7) assert(result.q10.im == 8) assert(result.q11.re == 5) assert(result.q11.im == 6) }").unwrap();
    let report = run_tests(&entry, "triton", "debug").unwrap();
    assert!(report.contains("1 passed; 0 failed"), "{report}");
}
