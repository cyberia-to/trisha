//! CPU mining hashes use raw Montgomery words on every platform.
//!
//! `BFieldElement::new` would interpret these words as canonical integers and
//! silently change every hash. Keep this representation boundary explicit.

#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
pub(crate) use acpu::field::{tip5_hash_pair, tip5_hash_varlen};

#[cfg(not(all(target_os = "macos", target_arch = "aarch64")))]
pub(crate) use portable::{tip5_hash_pair, tip5_hash_varlen};

#[inline]
pub(crate) fn pin_worker() {
    #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
    let _ = acpu::sync::affinity::pin_p_core();
}

#[cfg(any(test, not(all(target_os = "macos", target_arch = "aarch64"))))]
mod portable {
    use triton_vm::prelude::{BFieldElement, Digest, Tip5};
    use twenty_first::prelude::Sponge;

    pub(crate) fn tip5_hash_pair(left: [u64; 5], right: [u64; 5]) -> [u64; 5] {
        let left = Digest::new(left.map(BFieldElement::from_raw_u64));
        let right = Digest::new(right.map(BFieldElement::from_raw_u64));
        Tip5::hash_pair(left, right).values().map(|v| v.raw_u64())
    }

    pub(crate) fn tip5_hash_varlen(input: &[u64]) -> [u64; 5] {
        let mut sponge = Tip5::init();
        let mut chunks = input.chunks_exact(Tip5::RATE);
        for chunk in chunks.by_ref() {
            sponge.absorb(std::array::from_fn(|i| {
                BFieldElement::from_raw_u64(chunk[i])
            }));
        }
        let remainder = chunks.remainder();
        let mut last = [BFieldElement::new(0); Tip5::RATE];
        for (out, &word) in last.iter_mut().zip(remainder) {
            *out = BFieldElement::from_raw_u64(word);
        }
        last[remainder.len()] = BFieldElement::new(1);
        sponge.absorb(last);
        std::array::from_fn(|i| sponge.state[i].raw_u64())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use triton_vm::prelude::{BFieldElement, Digest, Tip5};

    fn fields(len: usize) -> Vec<BFieldElement> {
        let boundary = [0, 1, 2, u32::MAX as u64, BFieldElement::P - 1];
        (0..len)
            .map(|i| BFieldElement::new(boundary[i % boundary.len()]))
            .collect()
    }

    #[test]
    fn cpu_pair_preserves_raw_montgomery_hash_abi() {
        let values = fields(10);
        let left = Digest::new(values[..5].try_into().unwrap());
        let right = Digest::new(values[5..].try_into().unwrap());
        for (left, right) in [
            (left, right),
            (left, Digest::default()),
            (Digest::default(), right),
            (Digest::default(), Digest::default()),
        ] {
            let expected = Tip5::hash_pair(left, right).values().map(|v| v.raw_u64());
            let left = left.values().map(|v| v.raw_u64());
            let right = right.values().map(|v| v.raw_u64());
            assert_eq!(portable::tip5_hash_pair(left, right), expected);
            assert_eq!(tip5_hash_pair(left, right), expected);
        }
    }

    #[test]
    fn cpu_varlen_preserves_padding_and_raw_montgomery_hash_abi() {
        // Around the Tip5 rate boundary and the complete encoded PoW length.
        for len in [0, 1, 5, 9, 10, 11, 19, 20, 21, 300] {
            let values = fields(len);
            let raw: Vec<_> = values.iter().map(|v| v.raw_u64()).collect();
            let expected = Tip5::hash_varlen(&values).values().map(|v| v.raw_u64());
            assert_eq!(portable::tip5_hash_varlen(&raw), expected, "length {len}");
            assert_eq!(tip5_hash_varlen(&raw), expected, "length {len}");
        }
    }
}
