#![cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
use trisha_honeycrisp::{
    aruminium_mine::AruMine,
    neptune_mine::{NeptunePow, PowMastPaths, HEIGHT},
};
use triton_vm::prelude::*;
fn nonce(attempt: u64) -> Digest {
    Digest::new(
        [
            attempt,
            attempt ^ 0xA5A5A5A5A5A5A5A5,
            attempt.wrapping_mul(6364136223846793005),
            attempt.rotate_left(32),
            attempt.wrapping_add(1442695040888963407),
        ]
        .map(BFieldElement::new),
    )
}
#[test]
fn metal_matches_native_hash_threshold_and_exact_partial_batch() {
    let mut miner = AruMine::try_new().expect("real Metal device required for this gate");
    let path = std::array::from_fn(|i| {
        Digest::new(std::array::from_fn(|j| {
            BFieldElement::new((i * 5 + j + 1) as u64)
        }))
    });
    let mast = PowMastPaths {
        pow: [Digest::new([BFieldElement::new(17); 5]); 3],
        header: [Digest::new([BFieldElement::new(31); 5]); 2],
        kernel: [Digest::new([BFieldElement::new(47); 5])],
    };
    for attempt in [0, 1, 255, u64::MAX] {
        let pow = NeptunePow {
            root: Digest::default(),
            path_a: path,
            path_b: [Digest::default(); HEIGHT],
            nonce: nonce(attempt),
        };
        let hash = mast.fast_mast_hash(&pow);
        miner.set_template(&path, &mast, &hash);
        assert_eq!(
            miner.dispatch_batch(attempt, 1),
            Some(pow.nonce),
            "equality must accept attempt {attempt}"
        );
        let mut below = hash.values();
        for x in &mut below {
            if x.value() > 0 {
                *x = BFieldElement::new(x.value() - 1);
                break;
            }
            *x = BFieldElement::new(BFieldElement::P - 1);
        }
        miner.set_template(&path, &mast, &Digest::new(below));
        assert_eq!(
            miner.dispatch_batch(attempt, 1),
            None,
            "below threshold must reject attempt {attempt}"
        );
    }
    let max = Digest::new([BFieldElement::new(BFieldElement::P - 1); 5]);
    miner.set_template(&path, &mast, &max);
    assert_eq!(miner.dispatch_batch(0, 0), None);
    for count in [1, 255, 256, 257] {
        let found = miner
            .dispatch_batch(700, count)
            .expect("easy target must win");
        assert!((700..700 + count as u64).any(|a| nonce(a) == found));
    }
}
