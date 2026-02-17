//! Batch and streaming prover for compositional proofs and mining.

use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::thread;

use trident::runtime::{ProgramBundle, ProgramInput, ProofData, Prover};

use crate::error::TrishaError;
use crate::proof_file::{ClaimSection, DataSection, ProofFile, ProofMeta};
use crate::warrior::TrishaWarrior;

/// A single proving job.
pub struct ProveJob {
    pub bundle: ProgramBundle,
    pub input: ProgramInput,
    pub output_path: PathBuf,
}

/// Result of a proving job.
pub struct ProveResult {
    pub output_path: PathBuf,
    pub proof_data: Result<ProofData, TrishaError>,
    pub proving_time_ms: u64,
}

/// Prove multiple programs in parallel across available cores.
///
/// Used for compositional proofs where a program decomposes into N
/// sub-programs, each needing an independent proof.
pub fn prove_batch(jobs: Vec<ProveJob>, max_parallel: usize) -> Vec<ProveResult> {
    let max_parallel = max_parallel.max(1);

    thread::scope(|scope| {
        let mut results = Vec::with_capacity(jobs.len());
        let mut handles: Vec<thread::ScopedJoinHandle<'_, ProveResult>> = Vec::new();

        for job in jobs {
            if handles.len() >= max_parallel {
                let handle = handles.remove(0);
                results.push(handle.join().expect("proving thread panicked"));
            }

            let handle = scope.spawn(move || prove_one(job));
            handles.push(handle);
        }

        for handle in handles {
            results.push(handle.join().expect("proving thread panicked"));
        }

        results
    })
}

/// Streaming prover: continuous proving pipeline.
///
/// Receives jobs through a channel, proves them, sends results back.
/// Runs until the input channel is closed. Throughput-maximized for
/// mining workloads.
pub fn prove_stream(
    rx: mpsc::Receiver<ProveJob>,
    tx: mpsc::Sender<ProveResult>,
    max_parallel: usize,
) {
    let max_parallel = max_parallel.max(1);

    thread::scope(|scope| {
        let mut handles: Vec<thread::ScopedJoinHandle<()>> = Vec::new();

        for job in rx.iter() {
            // Drain finished threads
            handles.retain(|h| !h.is_finished());

            while handles.len() >= max_parallel {
                thread::yield_now();
                handles.retain(|h| !h.is_finished());
            }

            let tx = tx.clone();
            let handle = scope.spawn(move || {
                let result = prove_one(job);
                let _ = tx.send(result);
            });
            handles.push(handle);
        }

        for handle in handles {
            let _ = handle.join();
        }
    });
}

fn prove_one(job: ProveJob) -> ProveResult {
    let start = std::time::Instant::now();
    let warrior = TrishaWarrior::new();

    let result = warrior
        .prove(&job.bundle, &job.input)
        .map_err(|e| TrishaError::Prove(e));

    let proving_time_ms = start.elapsed().as_millis() as u64;

    if let Ok(ref proof_data) = result {
        let proof_file = ProofFile {
            proof: ProofMeta {
                format: proof_data.format.clone(),
                program_name: job.bundle.name.clone(),
                cycle_count: 0,
                padded_height: 0,
                proving_time_ms,
            },
            claim: ClaimSection {
                program_hash: proof_data.claim.program_hash.clone(),
                public_input: proof_data.claim.public_input.clone(),
                public_output: proof_data.claim.public_output.clone(),
            },
            data: DataSection {
                proof: ProofFile::encode_proof_bytes(&proof_data.proof_bytes),
            },
        };
        if let Err(e) = proof_file.save(&job.output_path) {
            return ProveResult {
                output_path: job.output_path,
                proof_data: Err(e),
                proving_time_ms,
            };
        }
    }

    ProveResult {
        output_path: job.output_path,
        proof_data: result,
        proving_time_ms,
    }
}

/// Build a batch of ProveJobs from input paths, compiling each source file.
pub fn build_jobs(
    inputs: &[PathBuf],
    target: &str,
    profile: &str,
    output_dir: &Path,
) -> Result<Vec<ProveJob>, TrishaError> {
    let mut jobs = Vec::with_capacity(inputs.len());
    for input in inputs {
        let bundle = crate::compile::compile_source(input, target, profile)?;
        let stem = input.file_stem().unwrap_or_default().to_string_lossy();
        let output_path = output_dir.join(format!("{}.proof.toml", stem));
        jobs.push(ProveJob {
            bundle,
            input: ProgramInput {
                public: Vec::new(),
                secret: Vec::new(),
            },
            output_path,
        });
    }
    Ok(jobs)
}
