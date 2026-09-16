//! Freeze the independent integer matrix oracle as full benchmark vectors.
#[path = "../tests/quantum_gates.rs"]
mod oracle;
use std::{fs, path::Path};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let dir =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../baselines/triton/fixtures/quantum-pure");
    fs::create_dir_all(&dir)?;
    fs::write(dir.join("main.tri"), oracle::source())?;
    let mut prefix = String::new();
    for i in 0..8 {
        prefix.push_str(&format!("read_io 1 push {} write_mem 1 pop 1\n", 10000 + i));
    }
    for &(name, width, _) in oracle::GATES {
        for i in 0..width {
            prefix.push_str(&format!("push {} read_mem 1 pop 1\n", 10000 + i));
        }
        prefix.push_str(&format!("call __{name}\n"));
        for remaining in (1..=oracle::reference(name, &[0; 8]).len()).rev() {
            if remaining > 1 {
                prefix.push_str(&format!("pick {}\n", remaining - 1));
            }
            prefix.push_str("write_io 1\n");
        }
    }
    prefix.push_str("halt\n");
    let p = triton_vm::prelude::BFieldElement::P;
    let inputs = [
        [0; 8],
        [1, 2, 3, 4, 5, 6, 7, 8],
        [p - 1, p - 2, 1, 2, 3, 5, 7, 11],
        [1 << 32, 3, 1, 5, 0, 1, 1, 0],
    ];
    for (i, input) in inputs.iter().enumerate() {
        let expected: Vec<_> = oracle::GATES
            .iter()
            .flat_map(|(name, _, _)| oracle::reference(name, input))
            .collect();
        let fields = |values: &[u64]| {
            values
                .iter()
                .map(|v| format!("\"{v}\""))
                .collect::<Vec<_>>()
                .join(", ")
        };
        fs::write(dir.join(format!("{i}.bench.toml")),format!(
            "source = \"main.tri\"\nhand = \"../../std/quantum/gates.tasm\"\ntarget = \"triton\"\ninput = [{}]\noutput = [{}]\nreference = \"Independent Rust u128 modular complex arithmetic and explicit gate matrices; all21 pure gate routines, every output coordinate. Measurement checks the documented signed-field surrogate.\"\nhand_prefix = \"\"\"\n{prefix}\"\"\"\n",
            fields(input),fields(&expected)))?;
    }
    Ok(())
}
