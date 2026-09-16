#[path = "../src/artifact.rs"]
mod artifact;
// Deterministic complete Neptune HardforkGamma transaction proof fixture.
// No mock proof, verification cache, wallet or network endpoint is involved.
use neptune_consensus::proof_abstractions::SecretWitness;
use neptune_consensus::transaction::primitive_witness::PrimitiveWitness;
use neptune_consensus::transaction::transaction_kernel::{
    TransactionKernelField, TransactionKernelProxy,
};
use neptune_consensus::transaction::validity::{
    collect_lock_scripts::CollectLockScriptsWitness,
    collect_type_scripts::CollectTypeScriptsWitness, kernel_to_outputs::KernelToOutputsWitness,
    proof_collection::ProofCollection, removal_records_integrity::RemovalRecordsIntegrityWitness,
    single_proof::SingleProofWitness,
};
use neptune_consensus::type_scripts::native_currency::NativeCurrencyWitness;
use neptune_consensus::type_scripts::native_currency_amount::NativeCurrencyAmount;
use neptune_mutator_set::mutator_set_accumulator::MutatorSetAccumulator;
use neptune_primitives::{mast_hash::MastHash, network::Network, timestamp::Timestamp};
use tasm_lib::triton_vm::prelude::*;

fn primitive(lock: Option<Digest>) -> PrimitiveWitness {
    // Real deployment fixture must be synchronized to the isolated network's
    // actual genesis, including premine and guesser-fee additions.
    let accumulator = if lock.is_some() {
        neptune_consensus::block::Block::genesis(Network::Testnet(1))
            .mutator_set_accumulator_after()
            .expect("canonical genesis accumulator")
    } else {
        MutatorSetAccumulator::default()
    };
    // Capture wall time at witness creation, just before component proving.
    // Never mutate the timestamp after any authenticated proof has been made.
    let timestamp = if lock.is_some() {
        Timestamp::now()
    } else {
        Timestamp::millis(1_000_000)
    };
    let outputs: Vec<_> = lock
        .map(|hash| neptune_consensus::transaction::utxo::Utxo::new(hash, vec![]))
        .into_iter()
        .collect();
    let senders = vec![Digest::new([bfe!(101); 5]); outputs.len()];
    let receivers = vec![Digest::new([bfe!(201); 5]); outputs.len()];
    let additions = outputs
        .iter()
        .zip(&senders)
        .zip(&receivers)
        .map(|((utxo, sender), receiver)| {
            neptune_mutator_set::commit(Tip5::hash(utxo), *sender, *receiver)
        })
        .collect();
    let kernel = TransactionKernelProxy {
        inputs: vec![],
        outputs: additions,
        announcements: vec![],
        fee: NativeCurrencyAmount::coins(0),
        coinbase: None,
        timestamp,
        mutator_set_hash: accumulator.hash(),
        merge_bit: false,
    }
    .into_kernel();
    PrimitiveWitness::generate_primitive_witness(
        vec![],
        outputs,
        senders,
        receivers,
        kernel,
        accumulator,
    )
}

fn execute_or_prove(
    label: &str,
    witness: &dyn SecretWitness,
    directory: Option<&std::path::Path>,
) -> Option<Proof> {
    let claim = witness.claim();
    let (trace, output) = VM::trace_execution(
        witness.program(),
        witness.standard_input(),
        witness.nondeterminism(),
    )
    .expect("canonical transaction relation must execute");
    assert_eq!(output, claim.output);
    eprintln!(
        "{label}: cycles={}, padded_height={}",
        trace.processor_trace.nrows(),
        trace.padded_height()
    );
    let cycles = trace.processor_trace.nrows() as u64;
    let directory = directory?;
    let started = std::time::Instant::now();
    let proof = Stark::default()
        .prove(&claim, &trace)
        .expect("default-security proof");
    drop(trace);
    Stark::default()
        .verify(&claim, &proof)
        .expect("fresh native verification");
    eprintln!(
        "{label}: proved and verified in {:.3}s",
        started.elapsed().as_secs_f64()
    );
    std::fs::write(
        directory.join(format!("{label}.json")),
        serde_json::to_vec(&serde_json::json!({"claim":claim,"proof":proof})).unwrap(),
    )
    .unwrap();
    artifact::write(
        &directory.join(label),
        &claim,
        &proof,
        cycles,
        started.elapsed().as_millis() as u64,
    );
    Some(proof)
}

fn main() {
    let mut args: Vec<_> = std::env::args().skip(1).collect();
    let deploy_lock = if let Some(position) = args.iter().position(|arg| arg == "--deploy-lock") {
        assert!(
            position + 1 < args.len(),
            "--deploy-lock requires an assembly file"
        );
        let path = args.remove(position + 1);
        args.remove(position);
        Some(
            Program::from_code(&std::fs::read_to_string(path).unwrap())
                .unwrap()
                .hash(),
        )
    } else {
        None
    };
    let directory = match args.as_slice() {
        [] => None,
        [flag, directory] if flag == "--prove" => {
            let directory = std::path::PathBuf::from(directory);
            std::fs::create_dir(&directory).expect("new output directory required");
            Some(directory)
        }
        _ => panic!("usage: single_proof [--prove NEW_DIRECTORY]"),
    };
    let primitive = primitive(deploy_lock);
    assert!(primitive.lock_scripts_and_witnesses.is_empty());
    assert_eq!(
        primitive.type_scripts_and_witnesses.len(),
        1,
        "native currency must be checked even for an empty transaction"
    );
    let native = NativeCurrencyWitness {
        salted_input_utxos: primitive.input_utxos.clone(),
        salted_output_utxos: primitive.output_utxos.clone(),
        kernel: primitive.kernel.clone(),
    };
    let witnesses: Vec<(&str, Box<dyn SecretWitness>)> = vec![
        (
            "removal-records",
            Box::new(RemovalRecordsIntegrityWitness::from(&primitive)),
        ),
        (
            "collect-lock-scripts",
            Box::new(CollectLockScriptsWitness::from(&primitive)),
        ),
        (
            "kernel-to-outputs",
            Box::new(KernelToOutputsWitness::from(&primitive)),
        ),
        (
            "collect-type-scripts",
            Box::new(CollectTypeScriptsWitness::from(&primitive)),
        ),
        ("native-currency", Box::new(native)),
    ];
    let mut proofs = Vec::new();
    for (label, witness) in witnesses {
        if let Some(proof) = execute_or_prove(label, witness.as_ref(), directory.as_deref()) {
            proofs.push(proof);
        }
    }
    let Some(directory) = directory else {
        return;
    };
    let mut proofs = proofs.into_iter();
    let collection = ProofCollection {
        removal_records_integrity: proofs.next().unwrap().into(),
        collect_lock_scripts: proofs.next().unwrap().into(),
        lock_scripts_halt: vec![],
        kernel_to_outputs: proofs.next().unwrap().into(),
        collect_type_scripts: proofs.next().unwrap().into(),
        type_scripts_halt: vec![proofs.next().unwrap().into()],
        lock_script_hashes: vec![],
        type_script_hashes: primitive
            .type_scripts_and_witnesses
            .iter()
            .map(|witness| witness.program.hash())
            .collect(),
        kernel_mast_hash: primitive.kernel.mast_hash(),
        salted_inputs_hash: Tip5::hash(&primitive.input_utxos),
        salted_outputs_hash: Tip5::hash(&primitive.output_utxos),
        merge_bit_mast_path: primitive.kernel.mast_path(TransactionKernelField::MergeBit),
    };
    std::fs::write(
        directory.join("proof-collection.json"),
        serde_json::to_vec(&collection).unwrap(),
    )
    .unwrap();
    let single = SingleProofWitness::from_collection(collection);
    assert!(single.claim().output.is_empty());
    assert_eq!(
        single.claim().input,
        primitive.kernel.mast_hash().reversed().values()
    );
    assert_eq!(single.claim().version, 5);
    let proof = execute_or_prove("single-proof", &single, Some(&directory)).unwrap();
    if deploy_lock.is_some() {
        let transaction = neptune_consensus::transaction::Transaction {
            kernel: primitive.kernel.clone(),
            proof: neptune_consensus::transaction::transaction_proof::TransactionProof::SingleProof(
                proof.into(),
            ),
        };
        let rpc =
            neptune_rpc_api::model::wallet::transaction::RpcTransaction::try_from(transaction)
                .unwrap();
        let utxo = neptune_rpc_api::model::wallet::transaction::RpcUtxo::from(
            primitive.output_utxos.utxos[0].clone(),
        );
        let intent = serde_json::json!({"schema_version":1,"network":"local-testnet1","expected_kernel":primitive.kernel.mast_hash().values().map(|v|v.value()),"transaction":rpc,"outputs":[{"utxo":utxo,"sender_randomness":[101,101,101,101,101],"receiver_digest":[201,201,201,201,201],"compiled_lock":true}]});
        std::fs::write(
            directory.join("deployment-intent.json"),
            serde_json::to_vec_pretty(&intent).unwrap(),
        )
        .unwrap();
    }
    println!(
        "{}",
        serde_json::json!({"protocol":"Neptune0.15.1/HardforkGamma", "kernel_digest":primitive.kernel.mast_hash().values().map(|word|word.value()), "program_digest":single.claim().program_digest.values().map(|word|word.value())})
    );
}
