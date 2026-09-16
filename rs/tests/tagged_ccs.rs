//! Experimental integration only: this does not change any execution protocol.
use std::collections::BTreeMap;
use trisha_rs::ccs::Checker;
use triton_vm::prelude::*;
use zheng::execution::{relation::SubjectShape, tagged, ExecutionNoun as Noun};

fn atom(x: u64) -> Noun {
    Noun::Atom(x)
}
fn pair(a: Noun, b: Noun) -> Noun {
    Noun::Pair(Box::new(a), Box::new(b))
}
fn formula() -> Noun {
    // Native opcode4: zero selects atom7, one selects pair[8 9].
    pair(
        atom(4),
        pair(
            pair(atom(0), atom(1)),
            pair(
                pair(atom(1), atom(7)),
                pair(atom(1), pair(atom(8), atom(9))),
            ),
        ),
    )
}
fn checker(r: &tagged::TaggedRelation, input: u64, output: &Noun, cost: u64) -> Checker {
    let mut unique = BTreeMap::new();
    for (column, value) in r.public_coordinates(&[input], output, cost, cost).unwrap() {
        let value = value.canonicalize().as_u64();
        if column == 0 {
            assert_eq!(value, 1); // Checker enforces this independently.
        } else if let Some(previous) = unique.insert(column, value) {
            assert_eq!(previous, value);
        }
    }
    Checker::new(
        r.instance(),
        &unique.into_iter().collect::<Vec<_>>(),
        b"experimental-tagged-branch-v1;formula=if(axis1,quote7,quote[8,9]);shape=atom;budget=3",
    )
    .unwrap()
}
fn words(r: &tagged::TaggedRelation, input: u64) -> Vec<u64> {
    r.witness(&[input])
        .unwrap()
        .z
        .iter()
        .map(|v| v.canonicalize().as_u64())
        .collect()
}
fn executes(c: &Checker, w: &[u64], public: Vec<BFieldElement>) -> bool {
    VM::run(
        Program::from_code(c.assembly()).unwrap(),
        PublicInput::new(public),
        NonDeterminism::new(
            w.iter()
                .copied()
                .map(BFieldElement::new)
                .collect::<Vec<_>>(),
        ),
    )
    .is_ok()
}

#[test]
fn experimental_tagged_topologies_share_checker_program_and_bind_all_coordinates() {
    let r = tagged::compile(&formula(), &SubjectShape::Atom).unwrap();
    let atom_checker = checker(&r, 0, &atom(7), 3);
    let pair_checker = checker(&r, 1, &pair(atom(8), atom(9)), 3);
    assert_eq!(atom_checker.assembly(), pair_checker.assembly());
    for (input, output) in [(0, atom(7)), (1, pair(atom(8), atom(9)))] {
        let witness = r.witness(&[input]).unwrap();
        assert!(r.verify_witness(&[input], &output, 3, 3, &witness));
        let c = checker(&r, input, &output, 3);
        // Obtain the exact public coordinate order without creating a proof.
        let pins = r.public_coordinates(&[input], &output, 3, 3).unwrap();
        let public: BTreeMap<_, _> = pins
            .into_iter()
            .filter(|(i, _)| *i != 0)
            .map(|(i, v)| (i, BFieldElement::new(v.canonicalize().as_u64())))
            .collect();
        let public: Vec<_> = public.into_values().collect();
        assert!(executes(&c, &words(&r, input), public.clone()));
        assert!(!executes(&c, &words(&r, 1 - input), public));
    }
}

#[test]
#[ignore = "experimental genuine tagged CCS STARK; coordinate the heavy proof slot"]
fn genuine_tagged_ccs_proofs_bind_atom_pair_topology_under_same_matrices() {
    let r = tagged::compile(&formula(), &SubjectShape::Atom).unwrap();
    let atom_checker = checker(&r, 0, &atom(7), 3);
    let pair_checker = checker(&r, 1, &pair(atom(8), atom(9)), 3);
    assert_eq!(atom_checker.assembly(), pair_checker.assembly());
    for (input, output, other) in [
        (0, atom(7), &pair_checker),
        (1, pair(atom(8), atom(9)), &atom_checker),
    ] {
        let c = checker(&r, input, &output, 3);
        let proof = c.prove(&words(&r, input)).unwrap();
        let decoded =
            trisha_rs::ccs::decode_proof(&trisha_rs::ccs::encode_proof(&proof).unwrap()).unwrap();
        assert!(c.verify(&decoded).unwrap());
        assert!(!other.verify(&decoded).unwrap());
        // Replace the entire envelope input with the other valid statement.
        // The same checker program must reject at STARK verification as well.
        let other_output = if input == 0 {
            pair(atom(8), atom(9))
        } else {
            atom(7)
        };
        let pins = r
            .public_coordinates(&[1 - input], &other_output, 3, 3)
            .unwrap();
        let other_public: BTreeMap<_, _> = pins
            .into_iter()
            .filter(|(i, _)| *i != 0)
            .map(|(i, v)| (i, v.canonicalize().as_u64()))
            .collect();
        let mut rebound = decoded.clone();
        rebound.claim.public_input = other_public.into_values().collect();
        assert!(!other.verify(&rebound).unwrap());
        let wrong = checker(&r, input, &pair(atom(9), atom(8)), 3);
        assert!(!wrong.verify(&decoded).unwrap());
        let mut forged = decoded.clone();
        forged.claim.public_input[0] ^= 1;
        assert!(!c.verify(&forged).unwrap());
        let wrong_cost = checker(&r, input, &output, 2);
        assert!(!wrong_cost.verify(&decoded).unwrap());
        eprintln!(
            "experimental tagged input={input}: {} proof bytes",
            decoded.proof_bytes.len()
        );
    }
}
