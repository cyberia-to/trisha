//! Build the complete fixed-NativeCurrency reference program and validate a real witness.
use trisha_rs::recursive;
use triton_vm::prelude::*;
fn main() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap();
    let text =
        std::fs::read_to_string(std::env::args().nth(1).expect("canonical oracle JSON")).unwrap();
    let value: serde_json::Value = serde_json::from_str(&text).unwrap();
    let claim: Claim = serde_json::from_value(value["claim"].clone()).unwrap();
    let proof: Proof = serde_json::from_value(value["proof"].clone()).unwrap();
    let mut public = vec![];
    for d in claim.input.chunks_exact(5) {
        public.extend(d.iter().rev().map(|x| x.value()));
    }
    let witness = recursive::encode(&claim, &proof).unwrap();
    let hand=format!("// Complete pinned Neptune0.15.1 NativeCurrency proof contract.\n// All3 digests bind the full canonical Claim; no independent amount hints.\n{}\ncall {}\nhalt\n{}\n{}",vec!["read_io 1";15].join("\n"),recursive::neptune::NATIVE_CURRENCY_ENTRYPOINT,recursive::neptune::protocol_assembly(recursive::neptune::NATIVE_CURRENCY_ENTRYPOINT).unwrap(),recursive::assembly());
    std::fs::write(
        root.join("baselines/triton/os/neptune/types/native_currency.tasm"),
        &hand,
    )
    .unwrap();
    let source = root.join("examples/neptune/types/native_currency.tri");
    for (label, code) in [
        ("hand", hand),
        (
            "source",
            trisha_rs::build_tasm(&source, "neptune", "release").unwrap(),
        ),
    ] {
        let program = Program::from_code(&code).unwrap();
        let nondet = NonDeterminism::new(
            witness
                .secret
                .iter()
                .copied()
                .map(BFieldElement::new)
                .collect::<Vec<_>>(),
        )
        .with_digests(
            witness
                .digests
                .iter()
                .map(|d| Digest::new(d.map(BFieldElement::new)))
                .collect::<Vec<_>>(),
        );
        let (aet, output) = VM::trace_execution(
            program.clone(),
            PublicInput::new(
                public
                    .iter()
                    .copied()
                    .map(BFieldElement::new)
                    .collect::<Vec<_>>(),
            ),
            nondet.clone(),
        )
        .unwrap();
        assert!(output.is_empty());
        eprintln!(
            "{label}: cycles={}, padded={}",
            aet.processor_trace.nrows(),
            aet.padded_height()
        );
        for i in [0, 5, 10] {
            let mut wrong = public.clone();
            wrong[i] ^= 1;
            assert!(VM::run(
                program.clone(),
                PublicInput::new(
                    wrong
                        .into_iter()
                        .map(BFieldElement::new)
                        .collect::<Vec<_>>()
                ),
                nondet.clone()
            )
            .is_err());
        }
    }
    let words = |v: &[u64]| {
        format!(
            "[{}]",
            v.iter()
                .map(|x| format!("\"{x}\""))
                .collect::<Vec<_>>()
                .join(",")
        )
    };
    for (name, bad) in [
        ("neptune-native-currency", false),
        ("neptune-native-currency-wrong-input", true),
    ] {
        let dir = root.join("baselines/triton/fixtures").join(name);
        std::fs::create_dir_all(&dir).unwrap();
        let mut p = public.clone();
        if bad {
            p[5] ^= 1;
        }
        let text=format!("source = \"../../../../examples/neptune/types/native_currency.tri\"\nhand = \"../../os/neptune/types/native_currency.tasm\"\ntarget = \"neptune\"\ninput = {}\noutput = []\nwitness_files = [\"../neptune-native-currency/witness.toml\"]\nexpect_failure = {bad}\nmax_cycles = 3000000\nreference = \"Fresh proof of pinned Neptune0.15.1 full NativeCurrency program: authenticated10input=7output+3kernelFee, canonical program/version5/all15inputwords/emptyoutput.\"\n",words(&p));
        std::fs::write(dir.join("vector.bench.toml"), text).unwrap();
    }
}
