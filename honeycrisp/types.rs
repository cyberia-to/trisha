//! Shared CPU/GPU mining state, laid out for direct IOSurface/MTLBuffer access.
//!
//! `BlockTemplate` and `MineState` are `#[repr(C)]` with field layouts that
//! match the corresponding MSL structs in `tip5.metal`. Both are allocated
//! via `aruminium::Buffer` with `MTLStorageModeShared` — CPU and GPU read
//! and write the same physical pages, no serialization, no staging copies.
//!
//! Conventions:
//! - `path_a`, `mast_*` digests are Montgomery-raw u64s (`BFieldElement::raw_u64()`)
//!   — matches the MSL Tip5 kernel and avoids a per-template conversion pass.
//! - `target` is canonical u64s (reverse-indexed for `Digest::cmp` order).
//! - `MineState::found` is the shared atomic flag used to coordinate
//!   CPU and GPU workers; first writer wins.

use std::sync::atomic::AtomicU32;

pub const HEIGHT: usize = 29;
pub const POW_PATH_LEN: usize = 3;
pub const HEADER_PATH_LEN: usize = 2;
pub const KERNEL_PATH_LEN: usize = 1;
pub const DIGEST_LEN: usize = 5;

/// Per-block-template inputs. Static for the duration of a mining session
/// against a single block template.
///
/// Layout (180 × u64 = 1440 bytes):
/// ```text
/// 0..145    path_a              (29 × 5 raw_u64)
/// 145..160  mast_pow            (3  × 5 raw_u64)
/// 160..170  mast_header         (2  × 5 raw_u64)
/// 170..175  mast_kernel         (1  × 5 raw_u64)
/// 175..180  target              (5 × canonical u64, reverse-indexed)
/// ```
#[repr(C)]
pub struct BlockTemplate {
    pub path_a: [[u64; DIGEST_LEN]; HEIGHT],
    pub mast_pow: [[u64; DIGEST_LEN]; POW_PATH_LEN],
    pub mast_header: [[u64; DIGEST_LEN]; HEADER_PATH_LEN],
    pub mast_kernel: [[u64; DIGEST_LEN]; KERNEL_PATH_LEN],
    pub target: [u64; DIGEST_LEN],
}

/// Shared mining result + coordination state. Both CPU and GPU workers
/// race to CAS `found` from 0 → 1; the winning worker writes the rest.
///
/// Layout (56 bytes, 8-byte aligned):
/// ```text
/// 0..4    found            (atomic u32: 0 = mining, 1 = won)
/// 4..8    _pad             (padding to 8-byte align next field)
/// 8..16   winning_attempt  (u64 nonce-attempt counter that won)
/// 16..56  winning_nonce    (5 × u64, raw Montgomery — matches MSL kernel)
/// ```
#[repr(C)]
pub struct MineState {
    pub found: AtomicU32,
    pub _pad: u32,
    pub winning_attempt: u64,
    pub winning_nonce: [u64; DIGEST_LEN],
}

impl MineState {
    /// Reset for a fresh mining run. Caller must ensure no workers are
    /// currently racing on this state.
    pub fn reset(&self) {
        self.found
            .store(0, std::sync::atomic::Ordering::Relaxed);
    }
}
