//! Independent pinned-consensus oracle. No Trident source, cached claim, mock
//! proof or reduced native-currency predicate is used.
mod artifact;
use neptune_consensus::proof_abstractions::tasm::program::TritonProgram;
use neptune_consensus::proof_abstractions::SecretWitness;
use neptune_consensus::transaction::primitive_witness::SaltedUtxos;
use neptune_consensus::transaction::transaction_kernel::TransactionKernelProxy;
use neptune_consensus::transaction::utxo::Utxo;
use neptune_consensus::transaction::validity::single_proof::SingleProof;
use neptune_consensus::type_scripts::native_currency::{NativeCurrency, NativeCurrencyWitness};
use neptune_consensus::type_scripts::native_currency_amount::NativeCurrencyAmount;
use neptune_primitives::timestamp::Timestamp;
use tasm_lib::triton_vm::{self, prelude::*};

fn witness(output_coins: u32) -> NativeCurrencyWitness {
    let kernel = TransactionKernelProxy {
        inputs: vec![],
        outputs: vec![],
        announcements: vec![],
        fee: NativeCurrencyAmount::coins(3),
        coinbase: None,
        timestamp: Timestamp::millis(1_000_000),
        mutator_set_hash: Digest::default(),
        merge_bit: false,
    }
    .into_kernel();
    NativeCurrencyWitness {
        salted_input_utxos: SaltedUtxos {
            utxos: vec![Utxo::new_native_currency(
                Digest::default(),
                NativeCurrencyAmount::coins(10),
            )],
            salt: [bfe!(11), bfe!(12), bfe!(13)],
        },
        salted_output_utxos: SaltedUtxos {
            utxos: vec![Utxo::new_native_currency(
                Digest::default(),
                NativeCurrencyAmount::coins(output_coins),
            )],
            salt: [bfe!(21), bfe!(22), bfe!(23)],
        },
        kernel,
    }
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    let program = NativeCurrency.program();
    assert_eq!(program.hash(), NativeCurrency.hash());
    let native = witness(7);
    let input = native.standard_input();
    let (trace, output) =
        VM::trace_execution(program.clone(), input.clone(), native.nondeterminism()).unwrap();
    eprintln!(
        "native-currency: cycles={}, padded_height={}",
        trace.processor_trace.nrows(),
        trace.padded_height()
    );
    let cycles = trace.processor_trace.nrows() as u64;
    assert!(output.is_empty());
    let invalid = witness(8);
    assert!(
        VM::run(
            program.clone(),
            invalid.standard_input(),
            invalid.nondeterminism()
        )
        .is_err(),
        "canonical inflation check did not reject"
    );
    let description = serde_json::json!({
        "upstream_revision":"9869b5e35b659dc520fad51ba5a9c812fed46db0",
        "program_digest":program.hash().values().map(|x|x.value()),
        "single_proof_digest":SingleProof.hash().values().map(|x|x.value()),
        "input":input.individual_tokens.iter().map(|x|x.value()).collect::<Vec<_>>(),
        "output":[],"relation":"10 input coins = 7 output coins + 3 kernel-authenticated fee coins",
    });
    println!("{}", serde_json::to_string_pretty(&description).unwrap());
    if let Some(path) = args.get(1) {
        let started = std::time::Instant::now();
        let (stark, claim, proof) =
            triton_vm::prove_program(program, input, native.nondeterminism()).unwrap();
        assert!(triton_vm::verify(stark, &claim, &proof));
        artifact::write(
            std::path::Path::new(path),
            &claim,
            &proof,
            cycles,
            started.elapsed().as_millis() as u64,
        );
        let artifact = serde_json::json!({"reference":description,"claim":claim,"proof":proof});
        std::fs::write(path, serde_json::to_vec_pretty(&artifact).unwrap()).unwrap();
    }
}
