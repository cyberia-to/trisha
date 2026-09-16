//! Pinned independent upstream vectors; no node, proof, or GuesserBuffer.
use trisha_honeycrisp::{
    neptune_mine::{NeptunePow, PowMastPaths},
    BlockTemplate, MineState,
};
use triton_vm::prelude::*;
include!("fixtures/neptune_pow_v0151.rs");
fn digest(seed: u64) -> Digest {
    Digest::new(std::array::from_fn(|i| BFieldElement::new(seed + i as u64)))
}
#[test]
fn native_codec_and_fast_mast_hash_match_pinned_consensus() {
    for (seed, expected_hash) in [0, 1000, BFieldElement::P - 400].into_iter().zip(HASHES) {
        let pow = NeptunePow {
            root: digest(seed),
            nonce: digest(seed + 5),
            path_a: std::array::from_fn(|i| digest(seed + 10 + i as u64 * 5)),
            path_b: std::array::from_fn(|i| digest(seed + 155 + i as u64 * 5)),
        };
        let mast = PowMastPaths {
            pow: std::array::from_fn(|i| digest(seed + 300 + i as u64 * 5)),
            header: std::array::from_fn(|i| digest(seed + 315 + i as u64 * 5)),
            kernel: [digest(seed + 325)],
        };
        let expected: Vec<_> = (5..10)
            .chain(155..300)
            .chain(10..155)
            .chain(0..5)
            .map(|i| BFieldElement::new(seed + i))
            .collect();
        assert_eq!(pow.encode(), expected);
        let mut raw = [0u64; 300];
        pow.encode_into_u64(&mut raw);
        assert_eq!(raw.map(BFieldElement::from_raw_u64).as_slice(), expected);
        assert_eq!(
            mast.fast_mast_hash(&pow).values().map(|x| x.value()),
            expected_hash
        );
    }
}
#[test]
fn host_offsets_match_metal_buffer_bindings() {
    use std::mem::{align_of, offset_of, size_of};
    assert_eq!(size_of::<BlockTemplate>(), 1440);
    assert_eq!(align_of::<BlockTemplate>(), 8);
    assert_eq!(offset_of!(BlockTemplate, mast_pow), 1160);
    assert_eq!(offset_of!(BlockTemplate, mast_header), 1280);
    assert_eq!(offset_of!(BlockTemplate, mast_kernel), 1360);
    assert_eq!(offset_of!(BlockTemplate, target), 1400);
    assert_eq!(size_of::<MineState>(), 56);
    assert_eq!(align_of::<MineState>(), 8);
    assert_eq!(offset_of!(MineState, winning_attempt), 8);
    assert_eq!(offset_of!(MineState, winning_nonce), 16);
}
