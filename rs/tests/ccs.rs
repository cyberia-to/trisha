use nebu::Goldilocks as F;
use trisha_rs::ccs::Checker;
use triton_vm::prelude::*;
use zheng::types::{CCSInstance, SparseMatrix};

// z[1]^2 = z[2], with z[0]=1 separately enforced by the checker.
fn square() -> CCSInstance {
    let mut a = SparseMatrix::new(1, 3);
    a.set(0, 1, F::ONE);
    let mut b = SparseMatrix::new(1, 3);
    b.set(0, 2, F::ONE);
    CCSInstance {
        matrices: vec![a, b],
        multisets: vec![vec![0, 0], vec![1]],
        coeffs: vec![F::ONE, F::NEG_ONE],
        num_rows: 1,
        num_cols: 3,
    }
}
fn executes(checker: &Checker, witness: &[u64], public: &[u64]) -> bool {
    VM::run(
        Program::from_code(checker.assembly()).unwrap(),
        PublicInput::new(public.iter().map(|&v| BFieldElement::new(v)).collect()),
        NonDeterminism::new(
            witness
                .iter()
                .map(|&v| BFieldElement::new(v))
                .collect::<Vec<_>>(),
        ),
    )
    .is_ok()
}

#[test]
fn generated_program_checks_private_columns_constant_and_public_coordinates() {
    let checker = Checker::new(&square(), &[(2, 49)], b"square-v1").unwrap();
    assert!(executes(&checker, &[1, 7, 49], &[49]));
    assert!(!executes(&checker, &[1, 8, 49], &[49]));
    assert!(!executes(&checker, &[0, 7, 49], &[49]));
    assert!(!executes(&checker, &[1, 7, 49], &[64]));
    assert!(!executes(&checker, &[1, 7], &[49]));
    assert!(checker.prove(&[1, 8, 49]).is_err());
    assert!(checker.prove(&[1, BFieldElement::P, 49]).is_err());
}

#[test]
fn sparse_duplicates_empty_product_and_every_row_are_checked() {
    let mut a = SparseMatrix::new(2, 2);
    a.set(0, 1, F::ONE);
    a.set(0, 1, F::ONE);
    a.set(1, 1, F::new(2));
    let mut relation = CCSInstance {
        matrices: vec![a],
        multisets: vec![vec![0], vec![]],
        coeffs: vec![F::ONE, -F::new(6)],
        num_rows: 2,
        num_cols: 2,
    };
    let checker = Checker::new(&relation, &[], b"duplicate-v1").unwrap();
    assert!(executes(&checker, &[1, 3], &[]));
    relation.matrices[0].set(1, 0, F::ONE);
    let changed = Checker::new(&relation, &[], b"duplicate-v1").unwrap();
    assert!(!executes(&changed, &[1, 3], &[]));
}

#[test]
fn malformed_and_excessive_relations_fail_before_execution() {
    let relation = square();
    for public in [
        vec![(0, 1)],
        vec![(3, 1)],
        vec![(2, 49), (2, 49)],
        vec![(2, BFieldElement::P)],
    ] {
        assert!(Checker::new(&relation, &public, b"id").is_err());
    }
    assert!(Checker::new(&relation, &[], &[]).is_err());
    let mut bad = relation.clone();
    bad.matrices[0].entries[0][0].0 = 3;
    assert!(Checker::new(&bad, &[], b"id").is_err());
    let mut bad = relation.clone();
    bad.multisets[0].push(2);
    assert!(Checker::new(&bad, &[], b"id").is_err());
    let mut bad = relation.clone();
    bad.num_cols = usize::MAX;
    assert!(Checker::new(&bad, &[], b"id").is_err());
    let mut bad = relation;
    bad.coeffs.clear();
    assert!(Checker::new(&bad, &[], b"id").is_err());
}

#[test]
fn genuine_zk_roundtrip_pins_regenerated_relation_and_statement() {
    let relation = square();
    let checker = Checker::new(&relation, &[(2, 49)], b"square-v1").unwrap();
    let started = std::time::Instant::now();
    let proof = checker.prove(&[1, 7, 49]).unwrap();
    eprintln!(
        "CCS Triton proof: {} bytes, prove {:?}, checker {} instructions",
        proof.proof_bytes.len(),
        started.elapsed(),
        checker.assembly().lines().count()
    );
    assert_eq!(proof.claim.public_input, vec![49]);
    assert!(proof.claim.public_output.is_empty());
    let wire = trisha_rs::ccs::encode_proof(&proof).unwrap();
    let decoded = trisha_rs::ccs::decode_proof(&wire).unwrap();
    let mut trailing = wire.clone();
    trailing.push(0);
    assert!(trisha_rs::ccs::decode_proof(&trailing).is_err());
    assert!(checker.verify(&decoded).unwrap());
    let mut alias = decoded.clone();
    let (index, value) = alias
        .proof_bytes
        .chunks_exact(8)
        .enumerate()
        .skip(1)
        .map(|(index, word)| (index, u64::from_le_bytes(word.try_into().unwrap())))
        .find(|(_, value)| *value <= u64::MAX - BFieldElement::P)
        .unwrap();
    alias.proof_bytes[index * 8..index * 8 + 8]
        .copy_from_slice(&(value + BFieldElement::P).to_le_bytes());
    assert!(
        checker.verify(&alias).is_err(),
        "CCS accepted noncanonical raw field alias"
    );
    let mut stream = triton_vm::proof_stream::ProofStream::try_from(
        &trisha_rs::convert::bytes_to_proof(&decoded.proof_bytes).unwrap(),
    )
    .unwrap();
    stream.enqueue(triton_vm::proof_item::ProofItem::MerkleRoot(
        Digest::default(),
    ));
    let extended: Proof = stream.into();
    let mut extra = decoded.clone();
    extra.proof_bytes = trisha_rs::convert::proof_to_bytes(&extended);
    assert!(
        !checker.verify(&extra).unwrap(),
        "CCS accepted superfluous proof item"
    );
    let mut legacy = decoded.clone();
    legacy.format = "zheng-ccs-triton-zk-v1".into();
    assert!(checker.verify(&legacy).is_err());
    assert!(!Checker::new(&relation, &[(2, 64)], b"square-v1")
        .unwrap()
        .verify(&decoded)
        .unwrap());
    assert!(!Checker::new(&relation, &[(2, 49)], b"square-v2")
        .unwrap()
        .verify(&decoded)
        .unwrap());
    let mut changed = relation;
    changed.coeffs[0] = F::new(2);
    let changed_checker = Checker::new(&changed, &[(2, 49)], b"square-v1").unwrap();
    assert!(!changed_checker.verify(&decoded).unwrap());
    // Rewrite envelope metadata to the expected forged relation. The STARK,
    // rather than only the envelope comparison, must still reject it.
    let mut forged = decoded.clone();
    forged.claim.program_hash = Program::from_code(changed_checker.assembly())
        .unwrap()
        .hash()
        .values()
        .iter()
        .map(|v| v.value())
        .collect();
    assert!(!changed_checker.verify(&forged).unwrap());
    let mut tampered = decoded;
    tampered.claim.public_input[0] = 64;
    assert!(!checker.verify(&tampered).unwrap());
    assert!(!Checker::new(&square(), &[(2, 64)], b"square-v1")
        .unwrap()
        .verify(&tampered)
        .unwrap());
}
