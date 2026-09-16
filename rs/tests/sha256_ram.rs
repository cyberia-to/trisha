//! Full SHA256 compression/double-hash paths, independent hashlib vectors and
//! caller-owned RAM rejection/preservation contracts.
use std::path::PathBuf;
use triton_vm::prelude::*;
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../baselines/triton/fixtures")
}
fn vector(text: &str, key: &str) -> Vec<BFieldElement> {
    let prefix = format!("{key} = [");
    text.lines()
        .find_map(|s| s.strip_prefix(&prefix))
        .unwrap()
        .trim_end_matches(']')
        .split(',')
        .filter(|s| !s.trim().is_empty())
        .map(|s| BFieldElement::new(s.trim().parse().unwrap()))
        .collect()
}
fn execute(code: &str, input: Vec<BFieldElement>, limit: u32) -> VMState {
    let mut vm = VMState::new(
        Program::from_code(code).unwrap(),
        PublicInput::new(input),
        NonDeterminism::default(),
    );
    while !vm.halting && vm.cycle_count < limit {
        vm.step().unwrap();
    }
    assert!(vm.halting, "execution budget exceeded");
    vm
}
#[test]
fn complete_double_hash_aggregate_and_ram_match_hashlib() {
    for driver in ["main.tri", "struct.tri"] {
        let code = trisha_rs::build_tasm(
            &root().join(format!("sha256-abc/{driver}")),
            "triton",
            "release",
        )
        .unwrap();
        for name in ["abc", "empty", "55bytes", "carry"] {
            let fixture =
                std::fs::read_to_string(root().join(format!("sha256-{name}/vector.bench.toml")))
                    .unwrap();
            let vm = execute(&code, vector(&fixture, "input"), 3_000_000);
            assert_eq!(
                vm.public_output,
                vector(&fixture, "output"),
                "{driver}/{name}"
            );
            if driver == "main.tri" {
                assert!(vm.cycle_count < 1_000_000);
            }
        }
    }
}
#[test]
fn double_hash_ram_preserves_input_and_rejects_invalid_regions() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("ram.tri");
    std::fs::write(
        &path,
        r#"program sha_ram_contract
use std.crypto.sha256
use vm.io.mem
use vm.core.convert
fn main() {
    let block = pub_read()
    let out = pub_read()
    let scratch = pub_read()
    for i in 0..16 bounded 16 { mem.write(block + convert.as_field(i),pub_read()) }
    mem.write(500,12345)
    mem.write(600,67890)
    sha256.double_sha256_single_block_in_ram(block,out,scratch)
    for i in 0..8 bounded 8 { pub_write(mem.read(out + convert.as_field(i))) }
}"#,
    )
    .unwrap();
    let code = trisha_rs::build_tasm(&path, "triton", "release").unwrap();
    let fixture = std::fs::read_to_string(root().join("sha256-abc/vector.bench.toml")).unwrap();
    let words = vector(&fixture, "input");
    for (block, out, scratch) in [(1000, 1016, 1024), (1000, 992, 904), (1000, 2000, 3000)] {
        let input = [vec![bfe!(block), bfe!(out), bfe!(scratch)], words.clone()].concat();
        let vm = execute(&code, input, 1_000_000);
        assert_eq!(vm.public_output, vector(&fixture, "output"));
        for (i, word) in words.iter().enumerate() {
            assert_eq!(vm.ram.get(&bfe!(block + i as u64)), Some(word));
        }
        assert_eq!(vm.ram.get(&bfe!(500)), Some(&bfe!(12345)));
        assert_eq!(vm.ram.get(&bfe!(600)), Some(&bfe!(67890)));
    }
    for (block, out, scratch, bad_limb) in [
        (1000u64, 1015u64, 3000u64, false),
        (1000, 2000, 1015, false),
        (1000, 2000, 1999, false),
        (u32::MAX as u64 - 8, 2000, 3000, false),
        (1000, 2000, u32::MAX as u64 - 20, false),
        (1000, 2000, 3000, true),
    ] {
        let mut input_words = words.clone();
        if bad_limb {
            input_words[0] = bfe!(1u64 << 32);
        }
        let input = [
            vec![bfe!(block), bfe!(out), bfe!(scratch)],
            input_words.clone(),
        ]
        .concat();
        let mut vm = VMState::new(
            Program::from_code(&code).unwrap(),
            PublicInput::new(input),
            NonDeterminism::default(),
        );
        let mut rejected = false;
        while !vm.halting && vm.cycle_count < 100_000 {
            if vm.step().is_err() {
                rejected = true;
                break;
            }
        }
        assert!(rejected, "invalid buffer/limb accepted");
        for (i, word) in input_words.iter().enumerate() {
            assert_eq!(
                vm.ram.get(&bfe!(block + i as u64)),
                Some(word),
                "input changed before rejection"
            );
        }
        assert_eq!(vm.ram.get(&bfe!(500)), Some(&bfe!(12345)));
        assert_eq!(vm.ram.get(&bfe!(600)), Some(&bfe!(67890)));
    }
}

#[test]
fn compression_chains_non_iv_state_and_checks_initial_state() {
    let fixture =
        std::fs::read_to_string(root().join("sha256-two-blocks/vector.bench.toml")).unwrap();
    let code = trisha_rs::build_tasm(
        &root().join("sha256-two-blocks/main.tri"),
        "triton",
        "release",
    )
    .unwrap();
    let vm = execute(&code, vector(&fixture, "input"), 1_000_000);
    assert_eq!(vm.public_output, vector(&fixture, "output"));

    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("bad-state.tri");
    std::fs::write(
        &path,
        r#"program bad_chaining_state
use std.crypto.sha256
use vm.io.mem
use vm.core.convert
fn main() {
    for i in 0..8 bounded 8 { mem.write(2000 + convert.as_field(i),0) }
    for i in 0..16 bounded 16 { mem.write(1000 + convert.as_field(i),0) }
    mem.write(2007,4294967296)
    mem.write(3000,77)
    sha256.compress_in_ram(2000,1000,3000)
}"#,
    )
    .unwrap();
    let code = trisha_rs::build_tasm(&path, "triton", "release").unwrap();
    let mut vm = VMState::new(
        Program::from_code(&code).unwrap(),
        PublicInput::default(),
        NonDeterminism::default(),
    );
    let mut rejected = false;
    while !vm.halting && vm.cycle_count < 100_000 {
        if vm.step().is_err() {
            rejected = true;
            break;
        }
    }
    assert!(rejected, "oversized chaining word was accepted");
    assert_eq!(
        vm.ram.get(&bfe!(3000)),
        Some(&bfe!(77)),
        "scratch mutated before input validation"
    );
    assert_eq!(vm.ram.get(&bfe!(2007)), Some(&bfe!(4294967296u64)));
}
