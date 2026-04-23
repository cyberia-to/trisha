use std::path::Path;

use trident::runtime::{ProgramInput, Prover, Runner, Verifier};

use trisha::compile::compile_source;
use trisha::convert;
use trisha::proof_file::ProofFile;
use trisha::warrior::TrishaWarrior;

// ─── Runner Tests ──────────────────────────────────────────────────

#[test]
fn run_hello_world() {
    std::fs::write(
        "/tmp/test_hello.tri",
        "program test_hello\nfn main() {\n    pub_write(42)\n}\n",
    )
    .unwrap();
    let bundle = compile_source(Path::new("/tmp/test_hello.tri"), "triton", "debug").unwrap();
    let warrior = TrishaWarrior::new();
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };
    let result = warrior.run(&bundle, &input).unwrap();
    assert_eq!(result.output, vec![42]);
}

#[test]
fn run_with_public_input() {
    std::fs::write(
        "/tmp/test_square.tri",
        "program test_square\nfn main() {\n    let x = pub_read()\n    pub_write(x * x)\n}\n",
    )
    .unwrap();
    let bundle = compile_source(Path::new("/tmp/test_square.tri"), "triton", "debug").unwrap();
    let warrior = TrishaWarrior::new();
    let input = ProgramInput {
        public: vec![7],
        secret: vec![],
        digests: vec![],
    };
    let result = warrior.run(&bundle, &input).unwrap();
    assert_eq!(result.output, vec![49]);
}

#[test]
fn run_multiple_outputs() {
    std::fs::write(
        "/tmp/test_multi.tri",
        "program test_multi\nfn main() {\n    pub_write(10)\n    pub_write(20)\n    pub_write(30)\n}\n",
    )
    .unwrap();
    let bundle = compile_source(Path::new("/tmp/test_multi.tri"), "triton", "debug").unwrap();
    let warrior = TrishaWarrior::new();
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };
    let result = warrior.run(&bundle, &input).unwrap();
    assert_eq!(result.output, vec![10, 20, 30]);
}

// ─── Prover + Verifier Tests ──────────────────────────────────────

#[test]
fn prove_and_verify_hello() {
    std::fs::write(
        "/tmp/test_pv_hello.tri",
        "program test_pv_hello\nfn main() {\n    pub_write(42)\n}\n",
    )
    .unwrap();
    let bundle = compile_source(Path::new("/tmp/test_pv_hello.tri"), "triton", "debug").unwrap();
    let warrior = TrishaWarrior::new();
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };

    let proof_data = warrior.prove(&bundle, &input).unwrap();

    assert_eq!(proof_data.claim.public_output, vec![42]);
    assert_eq!(proof_data.format, "stark-triton-v2");
    assert!(!proof_data.proof_bytes.is_empty());

    let valid = warrior.verify(&proof_data).unwrap();
    assert!(valid, "valid proof should verify");
}

#[test]
fn prove_and_verify_with_input() {
    std::fs::write(
        "/tmp/test_pv_sq.tri",
        "program test_pv_sq\nfn main() {\n    let x = pub_read()\n    pub_write(x * x)\n}\n",
    )
    .unwrap();
    let bundle = compile_source(Path::new("/tmp/test_pv_sq.tri"), "triton", "debug").unwrap();
    let warrior = TrishaWarrior::new();
    let input = ProgramInput {
        public: vec![5],
        secret: vec![],
        digests: vec![],
    };

    let proof_data = warrior.prove(&bundle, &input).unwrap();
    assert_eq!(proof_data.claim.public_input, vec![5]);
    assert_eq!(proof_data.claim.public_output, vec![25]);

    let valid = warrior.verify(&proof_data).unwrap();
    assert!(valid);
}

#[test]
fn tampered_proof_fails_verification() {
    std::fs::write(
        "/tmp/test_tamper.tri",
        "program test_tamper\nfn main() {\n    pub_write(99)\n}\n",
    )
    .unwrap();
    let bundle = compile_source(Path::new("/tmp/test_tamper.tri"), "triton", "debug").unwrap();
    let warrior = TrishaWarrior::new();
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };

    let mut proof_data = warrior.prove(&bundle, &input).unwrap();

    // Tamper with proof bytes
    if let Some(byte) = proof_data.proof_bytes.get_mut(100) {
        *byte = byte.wrapping_add(1);
    }

    // Tampered proof should either fail deserialization or verification
    let result = warrior.verify(&proof_data);
    match result {
        Ok(false) => {} // verification failed — correct
        Err(_) => {}    // deserialization error — also correct
        Ok(true) => panic!("tampered proof should not verify"),
    }
}

// ─── Proof File Tests ──────────────────────────────────────────────

#[test]
fn proof_file_roundtrip() {
    std::fs::write(
        "/tmp/test_pf_rt.tri",
        "program test_pf_rt\nfn main() {\n    pub_write(7)\n}\n",
    )
    .unwrap();
    let bundle = compile_source(Path::new("/tmp/test_pf_rt.tri"), "triton", "debug").unwrap();
    let warrior = TrishaWarrior::new();
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };

    let proof_data = warrior.prove(&bundle, &input).unwrap();

    // Save proof file
    let proof_file = trisha::proof_file::ProofFile {
        proof: trisha::proof_file::ProofMeta {
            format: proof_data.format.clone(),
            program_name: "test_pf_rt".to_string(),
            cycle_count: 0,
            padded_height: 0,
            proving_time_ms: 0,
        },
        claim: trisha::proof_file::ClaimSection {
            program_hash: proof_data.claim.program_hash.clone(),
            public_input: proof_data.claim.public_input.clone(),
            public_output: proof_data.claim.public_output.clone(),
        },
        data: trisha::proof_file::DataSection {
            proof: ProofFile::encode_proof_bytes(&proof_data.proof_bytes),
        },
    };

    let path = Path::new("/tmp/test_roundtrip.proof.toml");
    proof_file.save(path).unwrap();

    // Load it back
    let loaded = ProofFile::load(path).unwrap();
    assert_eq!(loaded.proof.format, "stark-triton-v2");
    assert_eq!(loaded.proof.program_name, "test_pf_rt");
    assert_eq!(loaded.claim.public_output, vec![7]);

    // Decode proof bytes and verify
    let decoded_bytes = ProofFile::decode_proof_bytes(&loaded.data.proof).unwrap();
    assert_eq!(decoded_bytes, proof_data.proof_bytes);

    std::fs::remove_file(path).ok();
}

// ─── Convert Tests ─────────────────────────────────────────────────

#[test]
fn u64_bfe_roundtrip() {
    // Goldilocks p = 2^64 - 2^32 + 1 = 0xFFFFFFFF00000001
    // Valid field elements are 0..p-1
    let values = vec![0, 1, 42, 1000000007, 0xFFFFFFFF00000000];
    let bfes = convert::u64s_to_bfes(&values);
    let back = convert::bfes_to_u64s(&bfes);
    assert_eq!(back, values);
}

#[test]
fn empty_input_conversion() {
    let input = ProgramInput {
        public: vec![],
        secret: vec![],
        digests: vec![],
    };
    let (pub_in, non_det) = convert::to_triton_inputs(&input);
    assert!(pub_in.individual_tokens.is_empty());
    assert!(non_det.individual_tokens.is_empty());
}

// ─── Compile Error Tests ───────────────────────────────────────────

#[test]
fn invalid_source_compile_error() {
    std::fs::write("/tmp/test_invalid.tri", "this is not valid trident code").unwrap();
    let result = compile_source(Path::new("/tmp/test_invalid.tri"), "triton", "debug");
    assert!(result.is_err());
}

#[test]
fn missing_file_compile_error() {
    let result = compile_source(
        Path::new("/tmp/nonexistent_file_12345.tri"),
        "triton",
        "debug",
    );
    assert!(result.is_err());
}

// ─── GPU Backend Tests ─────────────────────────────────────────────

#[test]
fn select_backend_returns_valid_name() {
    let backend = trisha::gpu::select_backend();
    let name = backend.name();
    assert!(
        name == "cpu" || name == "wgpu",
        "unexpected backend: {}",
        name
    );
}

/// Test that GPU iNTT produces identical results to CPU.
#[cfg(feature = "gpu")]
#[test]
fn gpu_intt_matches_cpu() {
    use triton_vm::gpu::GpuAccelerator;
    use twenty_first::math::ntt::intt;
    use twenty_first::prelude::*;

    let accel = match trisha::gpu::wgpu_backend::create_tip5_accelerator() {
        Some(a) => a,
        None => {
            eprintln!("No GPU available, skipping gpu_intt_matches_cpu");
            return;
        }
    };

    // Test various power-of-2 sizes
    for log_n in [10, 12, 14] {
        let n = 1usize << log_n;

        // Create test data
        let data: Vec<BFieldElement> = (0..n)
            .map(|i| BFieldElement::new((i as u64 * 97 + 13) % (1u64 << 60)))
            .collect();

        // CPU reference
        let mut cpu_result = data.clone();
        intt(&mut cpu_result);

        // GPU
        let mut gpu_result = data.clone();
        accel.intt_bfe(&mut gpu_result);

        assert_eq!(
            cpu_result, gpu_result,
            "GPU and CPU iNTT disagree for n=2^{}",
            log_n
        );
    }
}

/// Test that GPU XFE iNTT produces identical results to CPU.
#[cfg(feature = "gpu")]
#[test]
fn gpu_intt_xfe_matches_cpu() {
    use triton_vm::gpu::GpuAccelerator;
    use twenty_first::math::ntt::intt;
    use twenty_first::prelude::*;

    let accel = match trisha::gpu::wgpu_backend::create_tip5_accelerator() {
        Some(a) => a,
        None => {
            eprintln!("No GPU available, skipping gpu_intt_xfe_matches_cpu");
            return;
        }
    };

    for log_n in [10, 12, 14] {
        let n = 1usize << log_n;

        // Create test XFE data: 3 BFE coefficients per element
        let data: Vec<XFieldElement> = (0..n)
            .map(|i| {
                XFieldElement::new([
                    BFieldElement::new((i as u64 * 97 + 13) % (1u64 << 60)),
                    BFieldElement::new((i as u64 * 31 + 7) % (1u64 << 60)),
                    BFieldElement::new((i as u64 * 53 + 41) % (1u64 << 60)),
                ])
            })
            .collect();

        // CPU reference
        let mut cpu_result = data.clone();
        intt(&mut cpu_result);

        // GPU
        let mut gpu_result = data.clone();
        accel.intt_xfe(&mut gpu_result);

        assert_eq!(
            cpu_result, gpu_result,
            "GPU and CPU XFE iNTT disagree for n=2^{}",
            log_n
        );
    }
}

/// Test that GPU FRI fold produces identical results to CPU.
#[cfg(feature = "gpu")]
#[test]
fn gpu_fri_fold_matches_cpu() {
    use triton_vm::gpu::GpuAccelerator;
    use twenty_first::math::traits::FiniteField;
    use twenty_first::math::traits::PrimitiveRootOfUnity;
    use twenty_first::prelude::*;

    let accel = match trisha::gpu::wgpu_backend::create_tip5_accelerator() {
        Some(a) => a,
        None => {
            eprintln!("No GPU available, skipping gpu_fri_fold_matches_cpu");
            return;
        }
    };

    // Test various codeword sizes
    for log_n in [10, 12, 14] {
        let n = 1usize << log_n;
        let half_n = n / 2;

        // Generate deterministic XFE codeword
        let codeword: Vec<XFieldElement> = (0..n)
            .map(|i| {
                XFieldElement::new([
                    BFieldElement::new((i as u64 * 97 + 13) % (1u64 << 60)),
                    BFieldElement::new((i as u64 * 31 + 7) % (1u64 << 60)),
                    BFieldElement::new((i as u64 * 53 + 41) % (1u64 << 60)),
                ])
            })
            .collect();

        // Generate domain point inverses (simulate ArithmeticDomain)
        let omega = BFieldElement::primitive_root_of_unity(n as u64).unwrap();
        let offset = BFieldElement::new(7); // arbitrary offset
        let domain_points: Vec<BFieldElement> = (0..half_n)
            .map(|i| {
                let mut w = offset;
                for _ in 0..i {
                    w *= omega;
                }
                w
            })
            .collect();
        let domain_point_inverses = BFieldElement::batch_inversion(domain_points);

        // Folding challenge
        let folding_challenge = XFieldElement::new([
            BFieldElement::new(123456789),
            BFieldElement::new(987654321),
            BFieldElement::new(112233445),
        ]);

        // CPU reference (same algorithm as triton-vm split_and_fold)
        let one = XFieldElement::new([
            BFieldElement::new(1),
            BFieldElement::new(0),
            BFieldElement::new(0),
        ]);
        let two_inverse = XFieldElement::new([
            BFieldElement::new(2),
            BFieldElement::new(0),
            BFieldElement::new(0),
        ])
        .inverse();
        let cpu_result: Vec<XFieldElement> = (0..half_n)
            .map(|i| {
                let scaled_offset_inv = folding_challenge * domain_point_inverses[i];
                let left_summand = (one + scaled_offset_inv) * codeword[i];
                let right_summand = (one - scaled_offset_inv) * codeword[n / 2 + i];
                (left_summand + right_summand) * two_inverse
            })
            .collect();

        // GPU
        let gpu_result = accel.fri_fold(&codeword, &domain_point_inverses, folding_challenge);

        assert_eq!(
            cpu_result.len(),
            gpu_result.len(),
            "GPU and CPU FRI fold output lengths disagree for n=2^{}",
            log_n
        );
        for (j, (cpu, gpu)) in cpu_result.iter().zip(&gpu_result).enumerate() {
            assert_eq!(
                cpu, gpu,
                "GPU and CPU FRI fold disagree at index {} for n=2^{}",
                j, log_n
            );
        }
    }
}

/// Test that GPU forward NTT (BFE) produces identical results to CPU.
#[cfg(feature = "gpu")]
#[test]
fn gpu_ntt_bfe_matches_cpu() {
    use triton_vm::gpu::GpuAccelerator;
    use twenty_first::math::ntt::ntt;
    use twenty_first::prelude::*;

    let accel = match trisha::gpu::wgpu_backend::create_tip5_accelerator() {
        Some(a) => a,
        None => {
            eprintln!("No GPU available, skipping gpu_ntt_bfe_matches_cpu");
            return;
        }
    };

    for log_n in [10, 12, 14] {
        let n = 1usize << log_n;

        let data: Vec<BFieldElement> = (0..n)
            .map(|i| BFieldElement::new((i as u64 * 97 + 13) % (1u64 << 60)))
            .collect();

        let mut cpu_result = data.clone();
        ntt(&mut cpu_result);

        let mut gpu_result = data.clone();
        accel.ntt_bfe(&mut gpu_result);

        assert_eq!(
            cpu_result, gpu_result,
            "GPU and CPU forward NTT (BFE) disagree for n=2^{}",
            log_n
        );
    }
}

/// Test that GPU forward NTT (XFE) produces identical results to CPU.
#[cfg(feature = "gpu")]
#[test]
fn gpu_ntt_xfe_matches_cpu() {
    use triton_vm::gpu::GpuAccelerator;
    use twenty_first::math::ntt::ntt;
    use twenty_first::prelude::*;

    let accel = match trisha::gpu::wgpu_backend::create_tip5_accelerator() {
        Some(a) => a,
        None => {
            eprintln!("No GPU available, skipping gpu_ntt_xfe_matches_cpu");
            return;
        }
    };

    for log_n in [10, 12, 14] {
        let n = 1usize << log_n;

        let data: Vec<XFieldElement> = (0..n)
            .map(|i| {
                XFieldElement::new([
                    BFieldElement::new((i as u64 * 97 + 13) % (1u64 << 60)),
                    BFieldElement::new((i as u64 * 31 + 7) % (1u64 << 60)),
                    BFieldElement::new((i as u64 * 53 + 41) % (1u64 << 60)),
                ])
            })
            .collect();

        let mut cpu_result = data.clone();
        ntt(&mut cpu_result);

        let mut gpu_result = data.clone();
        accel.ntt_xfe(&mut gpu_result);

        assert_eq!(
            cpu_result, gpu_result,
            "GPU and CPU forward NTT (XFE) disagree for n=2^{}",
            log_n
        );
    }
}

/// Test that GPU forward NTT is the inverse of GPU iNTT.
#[cfg(feature = "gpu")]
#[test]
fn gpu_ntt_intt_roundtrip() {
    use triton_vm::gpu::GpuAccelerator;
    use twenty_first::prelude::*;

    let accel = match trisha::gpu::wgpu_backend::create_tip5_accelerator() {
        Some(a) => a,
        None => {
            eprintln!("No GPU available, skipping gpu_ntt_intt_roundtrip");
            return;
        }
    };

    let n = 1usize << 12;
    let original: Vec<BFieldElement> = (0..n)
        .map(|i| BFieldElement::new((i as u64 * 97 + 13) % (1u64 << 60)))
        .collect();

    // Forward then inverse should give back the original
    let mut data = original.clone();
    accel.ntt_bfe(&mut data);
    accel.intt_bfe(&mut data);

    assert_eq!(original, data, "NTT followed by iNTT should be identity");
}

/// Test that GPU GEMV (BFE × XFE) produces identical results to CPU.
#[cfg(feature = "gpu")]
#[test]
fn gpu_gemv_bfe_matches_cpu() {
    use triton_vm::gpu::GpuAccelerator;
    use twenty_first::prelude::*;

    let accel = match trisha::gpu::wgpu_backend::create_tip5_accelerator() {
        Some(a) => a,
        None => {
            eprintln!("No GPU available, skipping gpu_gemv_bfe_matches_cpu");
            return;
        }
    };

    // Test: 1024 rows × 32 columns
    let nrows = 1024;
    let ncols = 32;

    let matrix: Vec<BFieldElement> = (0..nrows * ncols)
        .map(|i| BFieldElement::new((i as u64 * 97 + 13) % (1u64 << 60)))
        .collect();

    let weights: Vec<XFieldElement> = (0..ncols)
        .map(|i| {
            XFieldElement::new([
                BFieldElement::new((i as u64 * 31 + 7) % (1u64 << 60)),
                BFieldElement::new((i as u64 * 53 + 41) % (1u64 << 60)),
                BFieldElement::new((i as u64 * 17 + 59) % (1u64 << 60)),
            ])
        })
        .collect();

    // CPU reference
    let cpu_result: Vec<XFieldElement> = (0..nrows)
        .map(|i| {
            let row = &matrix[i * ncols..(i + 1) * ncols];
            row.iter()
                .zip(weights.iter())
                .map(|(&m, &w)| w * m)
                .fold(XFieldElement::new([BFieldElement::new(0); 3]), |acc, x| {
                    acc + x
                })
        })
        .collect();

    // GPU
    let gpu_result = accel.gemv_bfe(&matrix, nrows, ncols, &weights);

    assert_eq!(cpu_result.len(), gpu_result.len());
    for (i, (cpu, gpu)) in cpu_result.iter().zip(&gpu_result).enumerate() {
        assert_eq!(cpu, gpu, "GPU and CPU GEMV BFE disagree at row {}", i);
    }
}

/// Test that GPU GEMV (XFE × XFE) produces identical results to CPU.
#[cfg(feature = "gpu")]
#[test]
fn gpu_gemv_xfe_matches_cpu() {
    use triton_vm::gpu::GpuAccelerator;
    use twenty_first::prelude::*;

    let accel = match trisha::gpu::wgpu_backend::create_tip5_accelerator() {
        Some(a) => a,
        None => {
            eprintln!("No GPU available, skipping gpu_gemv_xfe_matches_cpu");
            return;
        }
    };

    let nrows = 1024;
    let ncols = 16;

    let matrix: Vec<XFieldElement> = (0..nrows * ncols)
        .map(|i| {
            XFieldElement::new([
                BFieldElement::new((i as u64 * 97 + 13) % (1u64 << 60)),
                BFieldElement::new((i as u64 * 31 + 7) % (1u64 << 60)),
                BFieldElement::new((i as u64 * 53 + 41) % (1u64 << 60)),
            ])
        })
        .collect();

    let weights: Vec<XFieldElement> = (0..ncols)
        .map(|i| {
            XFieldElement::new([
                BFieldElement::new((i as u64 * 71 + 23) % (1u64 << 60)),
                BFieldElement::new((i as u64 * 17 + 59) % (1u64 << 60)),
                BFieldElement::new((i as u64 * 43 + 11) % (1u64 << 60)),
            ])
        })
        .collect();

    // CPU reference
    let cpu_result: Vec<XFieldElement> = (0..nrows)
        .map(|i| {
            let row = &matrix[i * ncols..(i + 1) * ncols];
            row.iter()
                .zip(weights.iter())
                .map(|(&m, &w)| m * w)
                .fold(XFieldElement::new([BFieldElement::new(0); 3]), |acc, x| {
                    acc + x
                })
        })
        .collect();

    // GPU
    let gpu_result = accel.gemv_xfe(&matrix, nrows, ncols, &weights);

    assert_eq!(cpu_result.len(), gpu_result.len());
    for (i, (cpu, gpu)) in cpu_result.iter().zip(&gpu_result).enumerate() {
        assert_eq!(cpu, gpu, "GPU and CPU GEMV XFE disagree at row {}", i);
    }
}

/// Test that GPU Merkle tree produces identical results to CPU.
#[cfg(feature = "gpu")]
#[test]
fn gpu_merkle_tree_matches_cpu() {
    use triton_vm::gpu::GpuAccelerator;
    use twenty_first::prelude::*;
    use twenty_first::util_types::merkle_tree::MerkleTree;

    let accel = match trisha::gpu::wgpu_backend::create_tip5_accelerator() {
        Some(a) => a,
        None => {
            eprintln!("No GPU available, skipping gpu_merkle_tree_matches_cpu");
            return;
        }
    };

    // Test various tree sizes (power of 2 leaves)
    for log_n in [9, 10, 12] {
        let n = 1usize << log_n;

        // Generate deterministic leaf digests
        let leaves: Vec<Digest> = (0..n)
            .map(|i| {
                Digest::new([
                    BFieldElement::new((i as u64 * 97 + 13) % (1u64 << 60)),
                    BFieldElement::new((i as u64 * 31 + 7) % (1u64 << 60)),
                    BFieldElement::new((i as u64 * 53 + 41) % (1u64 << 60)),
                    BFieldElement::new((i as u64 * 71 + 23) % (1u64 << 60)),
                    BFieldElement::new((i as u64 * 17 + 59) % (1u64 << 60)),
                ])
            })
            .collect();

        // CPU reference
        let cpu_tree = MerkleTree::par_new(&leaves).unwrap();

        // GPU
        let gpu_tree = accel.merkle_tree(&leaves);

        assert_eq!(
            cpu_tree.root(),
            gpu_tree.root(),
            "GPU and CPU Merkle tree roots disagree for n=2^{}",
            log_n
        );
    }
}

/// Test that GPU Tip5 hash_varlen_batch produces identical results to CPU.
#[cfg(feature = "gpu")]
#[test]
fn gpu_tip5_matches_cpu() {
    use triton_vm::gpu::GpuAccelerator;
    use twenty_first::prelude::*;

    // Create GPU accelerator
    let accel = match trisha::gpu::wgpu_backend::create_tip5_accelerator() {
        Some(a) => a,
        None => {
            eprintln!("No GPU available, skipping gpu_tip5_matches_cpu");
            return;
        }
    };

    // Test cases: various row lengths
    let test_cases: Vec<Vec<BFieldElement>> = vec![
        // Single element
        vec![BFieldElement::new(42)],
        // Exactly RATE (10) elements
        (0..10).map(|i| BFieldElement::new(i * 7 + 3)).collect(),
        // More than RATE, not aligned
        (0..17).map(|i| BFieldElement::new(i * 13 + 1)).collect(),
        // Multiple full chunks
        (0..30).map(|i| BFieldElement::new(i * 31 + 5)).collect(),
        // Large row (typical LDE table row)
        (0..200).map(|i| BFieldElement::new(i * 97 + 11)).collect(),
    ];

    // Test uniform batches (same row length — GPU path)
    for row in &test_cases {
        let cpu_digest = Tip5::hash_varlen(row);

        let rows: Vec<&[BFieldElement]> = vec![row.as_slice()];
        let gpu_digests = accel.hash_varlen_batch(&rows);

        assert_eq!(gpu_digests.len(), 1, "should return one digest per row");
        assert_eq!(
            cpu_digest,
            gpu_digests[0],
            "GPU and CPU Tip5 disagree for row_len={}",
            row.len()
        );
    }

    // Test batch of identical-length rows
    let batch_row_len = 30;
    let batch: Vec<Vec<BFieldElement>> = (0..16)
        .map(|batch_idx| {
            (0..batch_row_len)
                .map(|i| BFieldElement::new(batch_idx * 1000 + i * 7))
                .collect()
        })
        .collect();

    let cpu_digests: Vec<Digest> = batch.iter().map(|r| Tip5::hash_varlen(r)).collect();
    let row_refs: Vec<&[BFieldElement]> = batch.iter().map(|r| r.as_slice()).collect();
    let gpu_digests = accel.hash_varlen_batch(&row_refs);

    assert_eq!(cpu_digests.len(), gpu_digests.len());
    for (i, (cpu, gpu)) in cpu_digests.iter().zip(&gpu_digests).enumerate() {
        assert_eq!(cpu, gpu, "GPU and CPU Tip5 disagree at batch index {}", i);
    }
}
