//! Canonical library references are independent from VM instruction execution.
use trident::tir::TIROp;
use trisha_rs::lower::{StackLowering, TritonLowering};
use triton_vm::prelude::*;
use twenty_first::util_types::sponge::Sponge;

fn execute(ops: Vec<TIROp>, digests: Vec<Digest>) -> Vec<u64> {
    let code = TritonLowering::new().lower(&ops).join("\n") + "\nhalt";
    VM::run(
        Program::from_code(&code).expect("assembly"),
        PublicInput::default(),
        NonDeterminism::default().with_digests(digests),
    )
    .expect("execution")
    .into_iter()
    .map(|x| x.value())
    .collect()
}

#[test]
fn hash_and_sponge_match_canonical_native_library_vectors() {
    let values = std::array::from_fn::<_, 10, _>(|i| BFieldElement::new(i as u64));
    let mut ops: Vec<_> = (0..10).map(TIROp::Push).collect();
    ops.extend([TIROp::Hash { width: 5 }, TIROp::WriteIo(5)]);
    let expected: Vec<_> = Tip5::hash_10(&values)
        .into_iter()
        .rev()
        .map(|x| x.value())
        .collect();
    assert_eq!(execute(ops, vec![]), expected);
    let mut sponge = Tip5::init();
    sponge.absorb(values);
    let expected: Vec<_> = sponge
        .squeeze()
        .into_iter()
        .rev()
        .map(|x| x.value())
        .collect();
    let mut ops = vec![TIROp::Push(999), TIROp::SpongeInit];
    ops.extend((0..10).map(TIROp::Push));
    ops.extend([
        TIROp::SpongeAbsorb,
        TIROp::SpongeSqueeze,
        TIROp::WriteIo(10),
        TIROp::WriteIo(1),
    ]);
    let mut with_sentinel = expected.clone();
    with_sentinel.push(999);
    assert_eq!(execute(ops, vec![]), with_sentinel);
    let mut ops = vec![TIROp::Push(999), TIROp::SpongeInit];
    for i in 0..10 {
        ops.extend([
            TIROp::Push(i),
            TIROp::Push(100 + i),
            TIROp::WriteMem(1),
            TIROp::Pop(1),
        ]);
    }
    ops.extend([
        TIROp::Push(100),
        TIROp::SpongeLoad,
        TIROp::SpongeSqueeze,
        TIROp::WriteIo(10),
        TIROp::WriteIo(1),
    ]);
    assert_eq!(execute(ops, vec![]), with_sentinel);
}

#[test]
fn merkle_queue_and_memory_match_canonical_hash_pair() {
    let node = Digest::new([1, 2, 3, 4, 5].map(BFieldElement::new));
    let sibling = Digest::new([6, 7, 8, 9, 10].map(BFieldElement::new));
    for index in [2, 3] {
        let hash = if index == 2 {
            Tip5::hash_pair(node, sibling)
        } else {
            Tip5::hash_pair(sibling, node)
        };
        let mut expected: Vec<_> = hash.values().into_iter().rev().map(|x| x.value()).collect();
        expected.push(index / 2);
        let mut ops = vec![TIROp::Push(index)];
        ops.extend((1..=5).map(TIROp::Push));
        ops.extend([TIROp::MerkleStep, TIROp::WriteIo(6)]);
        assert_eq!(execute(ops, vec![sibling]), expected);
        let mut ops = vec![TIROp::Push(777)];
        for i in 0..5 {
            ops.extend([
                TIROp::Push(i + 6),
                TIROp::Push(i + 100),
                TIROp::WriteMem(1),
                TIROp::Pop(1),
            ]);
        }
        ops.push(TIROp::Push(index));
        ops.extend((1..=5).map(TIROp::Push));
        ops.extend([
            TIROp::Push(100),
            TIROp::MerkleLoad,
            TIROp::WriteIo(7),
            TIROp::WriteIo(1),
        ]);
        let mut memory_expected = vec![105];
        memory_expected.extend(expected);
        memory_expected.push(777);
        assert_eq!(execute(ops, vec![]), memory_expected);
    }
}

#[test]
fn digest_ram_blocks_use_ascending_base_addresses() {
    let mut ops = vec![TIROp::Push(777), TIROp::Push(100)];
    ops.extend((1..=5).map(TIROp::Push));
    ops.push(TIROp::RamWrite { width: 5 });
    for address in 100..105 {
        ops.extend([
            TIROp::Push(address),
            TIROp::RamRead { width: 1 },
            TIROp::WriteIo(1),
        ]);
    }
    ops.extend([
        TIROp::Push(100),
        TIROp::RamRead { width: 5 },
        TIROp::WriteIo(5),
        TIROp::WriteIo(1),
    ]);
    assert_eq!(
        execute(ops, vec![]),
        vec![1, 2, 3, 4, 5, 5, 4, 3, 2, 1, 777]
    );
}
