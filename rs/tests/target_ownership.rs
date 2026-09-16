use trident::tir::TIROp;
use trisha_rs::lower::{StackLowering, TritonLowering};
use triton_vm::prelude::*;

fn execute(ops: Vec<TIROp>, input: Vec<u64>) -> Vec<u64> {
    let assembly = TritonLowering::new().lower(&ops).join("\n") + "\nhalt";
    let program = Program::from_code(&assembly).expect("legal Triton instructions");
    VM::run(
        program,
        PublicInput::new(input.into_iter().map(BFieldElement::new).collect()),
        NonDeterminism::default(),
    )
    .expect("legalized program executes")
    .into_iter()
    .map(|v| v.value())
    .collect()
}

#[test]
fn deep_stack_operations_preserve_every_word() {
    for depth in [16, 17, 31, 64] {
        for duplicate in [false, true] {
            let mut ops: Vec<_> = (0..=depth).map(|v| TIROp::Push(u64::from(v))).collect();
            ops.push(if duplicate {
                TIROp::Dup(depth)
            } else {
                TIROp::Swap(depth)
            });
            ops.push(TIROp::WriteIo(depth + 1 + u32::from(duplicate)));
            let mut expected: Vec<_> = (0..=u64::from(depth)).rev().collect();
            if duplicate {
                expected.insert(0, 0);
            } else {
                expected.swap(0, depth as usize);
            }
            assert_eq!(execute(ops, vec![]), expected);
        }
    }
}

#[test]
fn wide_io_and_pop_are_legalized() {
    let input: Vec<_> = (0..13).collect();
    assert_eq!(
        execute(vec![TIROp::ReadIo(13), TIROp::WriteIo(13)], input),
        (0..13).rev().collect::<Vec<_>>()
    );
    assert_eq!(
        execute(
            vec![
                TIROp::Push(99),
                TIROp::ReadIo(13),
                TIROp::Pop(13),
                TIROp::WriteIo(1)
            ],
            (0..13).collect()
        ),
        vec![99]
    );
    let mut memory: Vec<_> = (0..13).map(TIROp::Push).collect();
    memory.extend([
        TIROp::Push(200),
        TIROp::WriteMem(13),
        TIROp::Pop(1),
        TIROp::Push(212),
        TIROp::ReadMem(13),
        TIROp::Pop(1),
        TIROp::WriteIo(13),
    ]);
    assert_eq!(execute(memory, vec![]), (0..13).rev().collect::<Vec<_>>());
}

#[test]
fn embedded_package_owns_network_and_modules() {
    let package = trisha_rs::target::package("neptune").expect("embedded package");
    package.validate().expect("package integrity");
    assert_eq!(package.terrain.digest_width, 5);
    assert_eq!(package.states.len(), 3);
    let local = package
        .states
        .iter()
        .find(|state| state.name == "local-testnet1")
        .expect("explicit local real-proof state");
    assert_eq!(local.chain_id, "4");
    assert_eq!(local.rpc_url, "http://127.0.0.1:29799");
    assert!(!local.is_default);
    assert!(package.modules.contains_key("os.neptune.kernel"));
    assert!(!package.runtime.deploy);
    let actual: std::collections::BTreeSet<_> = triton_vm::isa::instruction::ALL_INSTRUCTION_NAMES
        .into_iter()
        .map(str::to_owned)
        .collect();
    assert_eq!(
        package
            .instructions
            .into_iter()
            .collect::<std::collections::BTreeSet<_>>(),
        actual
    );
    assert!(trisha_rs::target::package("nox").is_err());
}

#[test]
fn incorrect_intrinsic_abi_is_rejected_before_lowering() {
    let directory = tempfile::tempdir().unwrap();
    let source = directory.path().join("wrong.tri");
    std::fs::write(
        &source,
        "module wrong\n#[intrinsic(hash)]\npub fn wrong(x: Field) -> Digest\n",
    )
    .unwrap();
    let error = trisha_rs::build_tasm(&source, "triton", "debug").unwrap_err();
    assert!(
        error.contains("intrinsic") && error.contains("hash"),
        "{error}"
    );
}

#[test]
fn neptune_sdk_requires_neptune_target() {
    let bare = trisha_rs::target::package("triton").unwrap();
    assert!(bare.modules.keys().all(|name| !name.starts_with("os.")));
    assert!(bare.union.is_none() && bare.states.is_empty());
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("network.tri");
    std::fs::write(
        &path,
        "program network\nuse os.neptune.xfield\nfn main() { pub_write(1) }\n",
    )
    .unwrap();
    assert!(trisha_rs::build_tasm(&path, "triton", "debug").is_err());
    assert!(trisha_rs::build_tasm(&path, "neptune", "debug").is_ok());
}

#[test]
fn typed_extension_dot_steps_execute_with_both_pointers() {
    let directory = tempfile::tempdir().unwrap();
    for (operation, next_b) in [("xx_dot_step", 303), ("xb_dot_step", 301)] {
        let path = directory.path().join("dot.tri");
        let source = format!("program dot\nuse os.neptune.xfield\nfn main() {{\nram_write(200,2)\nram_write(201,3)\nram_write(202,4)\nram_write(300,5)\nram_write(301,0)\nram_write(302,0)\nlet (acc,a,b) = xfield.{operation}(xfield.new(1,2,3),200,300)\nlet (c0,c1,c2) = acc\npub_write(c0)\npub_write(c1)\npub_write(c2)\npub_write(a)\npub_write(b)\n}}\n");
        std::fs::write(&path, source).unwrap();
        let assembly = trisha_rs::build_tasm(&path, "neptune", "debug").unwrap();
        let output = VM::run(
            Program::from_code(&assembly).unwrap(),
            PublicInput::default(),
            NonDeterminism::default(),
        )
        .unwrap();
        assert_eq!(
            output.into_iter().map(|v| v.value()).collect::<Vec<_>>(),
            vec![11, 17, 23, 203, next_b]
        );
    }
}

#[test]
fn extension_inverse_preserves_coefficient_order() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("inverse.tri");
    std::fs::write(&path, "program inverse\nuse os.neptune.xfield\nfn main() {\nlet (a,b,c) = xfield.inv(xfield.new(2,3,4))\npub_write(a)\npub_write(b)\npub_write(c)\n}\n").unwrap();
    let assembly = trisha_rs::build_tasm(&path, "neptune", "debug").unwrap();
    let output = VM::run(
        Program::from_code(&assembly).unwrap(),
        PublicInput::default(),
        NonDeterminism::default(),
    )
    .unwrap();
    let expected = XFieldElement::new([2, 3, 4].map(BFieldElement::new)).inverse();
    assert_eq!(output, expected.coefficients);
}

#[test]
fn local_functions_shadow_imported_and_builtin_names_at_execution() {
    let directory = tempfile::tempdir().unwrap();
    for (imports, name, increment, expected) in [
        ("use vm.crypto.hash\n", "native", 7, 11),
        ("", "ram_read", 9, 13),
    ] {
        let path = directory.path().join("shadow.tri");
        let source = format!("program shadow\n{imports}fn {name}(x: Field) -> Field {{ x + {increment} }}\nfn main() {{ pub_write({name}(4)) }}\n");
        std::fs::write(&path, source).unwrap();
        let assembly = trisha_rs::build_tasm(&path, "triton", "debug").unwrap();
        let output = VM::run(
            Program::from_code(&assembly).unwrap(),
            PublicInput::default(),
            NonDeterminism::default(),
        )
        .unwrap();
        assert_eq!(
            output,
            vec![BFieldElement::new(expected)],
            "local function {name} must be called"
        );
    }
}

#[test]
fn checked_u32_wrapper_rejects_high_limbs() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("checked.tri");
    std::fs::write(&path, "program checked\nfn checked(x: Field) -> U32 { as_u32(x) }\nfn field(x: U32) -> Field { as_field(x) }\nfn main() { pub_write(field(checked(pub_read()))) }\n").unwrap();
    let assembly = trisha_rs::build_tasm(&path, "triton", "release").unwrap();
    let program = Program::from_code(&assembly).unwrap();
    let maximum = BFieldElement::new(u64::from(u32::MAX));
    assert_eq!(
        VM::run(
            program.clone(),
            PublicInput::new(vec![maximum]),
            NonDeterminism::default()
        )
        .unwrap(),
        vec![maximum]
    );
    assert!(VM::run(
        program,
        PublicInput::new(vec![BFieldElement::new(1 << 32)]),
        NonDeterminism::default()
    )
    .is_err());
}

#[test]
fn power_uses_base_then_exponent_source_order() {
    for (base, exponent, expected) in [(3, 5, 243), (5, 3, 125), (7, 0, 1)] {
        assert_eq!(
            execute(
                vec![
                    TIROp::Push(base),
                    TIROp::Push(exponent),
                    TIROp::Pow,
                    TIROp::WriteIo(1)
                ],
                vec![]
            ),
            vec![expected]
        );
    }
}

#[test]
fn owner_legalizes_wide_source_frames_in_both_profiles() {
    let width = 40;
    let reverse = (0..width)
        .rev()
        .map(|i| format!("words[{i}]"))
        .collect::<Vec<_>>()
        .join(", ");
    let reads = vec!["pub_read()"; width].join(", ");
    let mut source = format!("program deep_frames\nfn reverse(words: [Field; {width}]) -> [Field; {width}] {{ [{reverse}] }}\nfn main() {{ let sentinel: Field = 997\nlet words: [Field; {width}] = [{reads}]\nlet reversed = reverse(words)\n");
    for name in ["reversed", "words"] {
        for i in 0..width {
            source.push_str(&format!("pub_write({name}[{i}])\n"));
        }
    }
    source.push_str("pub_write(sentinel)\n}");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("deep_frames.tri");
    std::fs::write(&path, source).unwrap();
    let input: Vec<u64> = (1..=width as u64).collect();
    let expected: Vec<u64> = input
        .iter()
        .rev()
        .chain(input.iter())
        .copied()
        .chain([997])
        .collect();
    for profile in ["debug", "release"] {
        let assembly = trisha_rs::build_tasm(&path, "triton", profile).unwrap();
        assert!(
            assembly.contains("stack_scratch"),
            "owner scratch must handle deep access"
        );
        let actual = VM::run(
            Program::from_code(&assembly).unwrap(),
            PublicInput::new(input.iter().copied().map(BFieldElement::new).collect()),
            NonDeterminism::default(),
        )
        .unwrap();
        assert_eq!(
            actual.iter().map(|v| v.value()).collect::<Vec<_>>(),
            expected,
            "{profile}"
        );
    }
}
