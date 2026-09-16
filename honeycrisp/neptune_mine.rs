//! Real Neptune PoW mining — partial GuesserBuffer (32 GB) + rayon parallel search.
//!
//! Mirrors pinned Neptune v0.15.1: Reboot, Alpha/TVM1, and fast Beta/Gamma.
//! See docs/reference/mining.md for session and ownership contracts.
//!
//! HardforkBeta hot path runs through honeycrisp `acpu` (Apple Silicon Tip5)
//! with std::thread workers pinned to P-cores via `acpu::sync::affinity`.
//! Other CPU hosts use portable twenty-first Tip5. Pre-HardforkBeta
//! GuesserBuffer code retains rayon + twenty-first (deprecated post-HFB).
//!
//! Memory layout of GuesserBuffer:
//!   leaves (all 2^29):          21.47 GB  (required)
//!   internal_nodes (top 28 lv): 10.74 GB  (1-indexed, levels 1–27)
//!   bottom internal level:      OMITTED    (computed on demand: 1 Tip5 per path)
//!   Total at rest:              32.21 GB
//!   Peak during build:         ~43    GB  (two leaf-sized butterfly buffers)

use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
#[path = "mining_session.rs"]
mod session;
use session::{Attempts, Winner};
use std::thread;

use rayon::prelude::*;
use triton_vm::prelude::*;

pub use crate::types::{HEADER_PATH_LEN, HEIGHT, KERNEL_PATH_LEN, POW_PATH_LEN};
pub use triton_vm::prelude::BFieldElement as Field;

// ── pinned Neptune v0.15.1 constants ─────────────────────────

pub const NUM_LEAFS: usize = 1 << HEIGHT;

const NUM_BUD_LAYERS: usize = 5;
const NUM_INDEX_REPETITIONS: u32 = 63;

// ── types ─────────────────────────────────────────────────────────────────

/// Mirror of neptune-core's `PowMastPaths`.
/// Obtained from neptune-core RPC when a new block template arrives.
#[derive(Clone, Debug, Default)]
pub struct PowMastPaths {
    pub pow: [Digest; POW_PATH_LEN],
    pub header: [Digest; HEADER_PATH_LEN],
    pub kernel: [Digest; KERNEL_PATH_LEN],
}

/// Mirror of neptune-core's `Pow<HEIGHT>`.
#[derive(Clone, Debug)]
pub struct NeptunePow {
    pub root: Digest,
    pub path_a: [Digest; HEIGHT],
    pub path_b: [Digest; HEIGHT],
    pub nonce: Digest,
}

impl PowMastPaths {
    /// Commitment to all MAST paths (used for index derivation and hash).
    pub fn commit(&self) -> Digest {
        let fields: Vec<BFieldElement> = self
            .pow
            .iter()
            .chain(self.header.iter())
            .chain(self.kernel.iter())
            .flat_map(|d| d.values())
            .collect();
        Tip5::hash_varlen(&fields)
    }

    /// Block hash from a Pow. Must be ≤ difficulty target to win.
    ///
    /// Replicates neptune-core's `PowMastPaths::fast_mast_hash()`.
    /// ~39 Tip5 permutations at HEIGHT = 29. Hot path: routes through
    /// `crate::cpu::tip5_*`, accelerated by acpu on Apple Silicon.
    pub fn fast_mast_hash(&self, pow: &NeptunePow) -> Digest {
        let mut encoded = [0u64; 300];
        pow.encode_into_u64(&mut encoded);

        let header_hash = crate::cpu::tip5_hash_pair(
            crate::cpu::tip5_hash_varlen(&encoded),
            digest_to_raw(&self.pow[0]),
        );
        let header_hash = crate::cpu::tip5_hash_pair(header_hash, digest_to_raw(&self.pow[1]));
        let header_hash = crate::cpu::tip5_hash_pair(digest_to_raw(&self.pow[2]), header_hash);

        let kernel_hash = crate::cpu::tip5_hash_pair(
            crate::cpu::tip5_hash_varlen(&header_hash),
            digest_to_raw(&self.header[0]),
        );
        let kernel_hash = crate::cpu::tip5_hash_pair(kernel_hash, digest_to_raw(&self.header[1]));

        raw_to_digest(crate::cpu::tip5_hash_pair(
            crate::cpu::tip5_hash_varlen(&kernel_hash),
            digest_to_raw(&self.kernel[0]),
        ))
    }
}

#[inline(always)]
fn digest_to_raw(d: &Digest) -> [u64; 5] {
    let v = d.values();
    [
        v[0].raw_u64(),
        v[1].raw_u64(),
        v[2].raw_u64(),
        v[3].raw_u64(),
        v[4].raw_u64(),
    ]
}

#[inline(always)]
fn raw_to_digest(arr: [u64; 5]) -> Digest {
    Digest::new([
        BFieldElement::from_raw_u64(arr[0]),
        BFieldElement::from_raw_u64(arr[1]),
        BFieldElement::from_raw_u64(arr[2]),
        BFieldElement::from_raw_u64(arr[3]),
        BFieldElement::from_raw_u64(arr[4]),
    ])
}

impl NeptunePow {
    /// BFieldCodec serialisation: struct fields in reverse declaration order.
    /// Layout: nonce (5) | path_b (145) | path_a (145) | root (5) = 300 BFEs.
    pub fn encode(&self) -> Vec<BFieldElement> {
        let mut out = Vec::with_capacity(300);
        out.extend_from_slice(&self.nonce.values());
        for d in &self.path_b {
            out.extend_from_slice(&d.values());
        }
        for d in &self.path_a {
            out.extend_from_slice(&d.values());
        }
        out.extend_from_slice(&self.root.values());
        out
    }

    /// Same layout as [`encode`] but writes raw-Montgomery u64s into a
    /// stack buffer — zero heap allocation, free cast from `BFieldElement`,
    /// suitable for the `crate::cpu::tip5_*` hot path.
    #[inline(always)]
    pub fn encode_into_u64(&self, out: &mut [u64; 300]) {
        let n = self.nonce.values();
        for i in 0..5 {
            out[i] = n[i].raw_u64();
        }
        for (di, d) in self.path_b.iter().enumerate() {
            let off = 5 + di * 5;
            let v = d.values();
            for j in 0..5 {
                out[off + j] = v[j].raw_u64();
            }
        }
        for (di, d) in self.path_a.iter().enumerate() {
            let off = 5 + 145 + di * 5;
            let v = d.values();
            for j in 0..5 {
                out[off + j] = v[j].raw_u64();
            }
        }
        let r = self.root.values();
        for i in 0..5 {
            out[295 + i] = r[i].raw_u64();
        }
    }
}

// ── GuesserBuffer ─────────────────────────────────────────────────────────

/// Partial PoW Merkle tree for Neptune mining.
///
/// Stores all 2^29 leaves (21.47 GB) and internal nodes for levels 1–27
/// (10.74 GB, 1-indexed). Level 28 (the bottom internal level, normally
/// another 10.74 GB) is omitted and reconstructed on demand at cost of
/// one extra Tip5 call per auth-path query per guess.
///
/// Peak allocation during [`GuesserBuffer::build`]: ~43 GB (two butterfly
/// buffers). Ensure ≥ 44 GB of unified memory is available before calling.
pub struct GuesserBuffer {
    pub leafs: Vec<Digest>,
    pub internal_nodes: Vec<Digest>, // 2^28 entries, 1-indexed, levels 1–27
    pub prev_block_digest: Digest,
}

impl GuesserBuffer {
    /// Build from the parent block digest. Allocates ~43 GB at peak.
    pub fn build(prev_block_digest: Digest) -> Self {
        Self::build_legacy(prev_block_digest, true)
    }

    /// Reboot uses MAST commitment without bit reversal; Alpha/TVM1 use parent digest.
    pub fn build_legacy(prev_block_digest: Digest, bit_reverse: bool) -> Self {
        eprintln!("GuesserBuffer: generating {NUM_LEAFS} leaves...");
        let t0 = std::time::Instant::now();
        let leafs = Self::compute_leafs(prev_block_digest, bit_reverse);
        eprintln!("  leaves: {:.1}s", t0.elapsed().as_secs_f64());

        eprintln!("GuesserBuffer: building partial internal nodes (top 28 levels)...");
        let t1 = std::time::Instant::now();
        let internal_nodes = Self::build_internal_nodes(&leafs);
        eprintln!(
            "  internal: {:.1}s — root: {}",
            t1.elapsed().as_secs_f64(),
            internal_nodes[1]
        );

        Self {
            leafs,
            internal_nodes,
            prev_block_digest,
        }
    }

    pub fn root(&self) -> Digest {
        self.internal_nodes[1]
    }

    /// Auth path for the leaf at `idx` (HEIGHT = 29 elements).
    ///
    /// Matches neptune-core's `MTree::path()` except the first loop iteration
    /// (which would access the omitted level-28 internal nodes) is computed
    /// from stored leaves instead — cost: 1 extra Tip5 per call.
    pub fn path(&self, idx: usize) -> [Digest; HEIGHT] {
        self.path_at_height::<HEIGHT>(idx)
    }

    fn path_at_height<const H: usize>(&self, idx: usize) -> [Digest; H] {
        assert_eq!(self.leafs.len(), 1usize << H);
        assert!(idx < self.leafs.len());
        let num_leafs = self.leafs.len();
        let mut path = [Digest::default(); H];

        // Element 0: sibling leaf.
        path[0] = self.leafs[idx ^ 1];

        // Element 1: bottom internal sibling (level 28, omitted from storage).
        // running_index = (idx + num_leafs) >> 1  is in [2^28, 2^29).
        // sibling_1     = running_index ^ 1        is in [2^28, 2^29).
        // For j = sibling_1 − 2^28:
        //   internal_nodes_full[sibling_1] = hash(leaf[2j], leaf[2j+1]).
        let mut running = (idx + num_leafs) >> 1;
        let sib1 = running ^ 1;
        let j = sib1 - (num_leafs >> 1);
        path[1] = Tip5::hash_pair(self.leafs[2 * j], self.leafs[2 * j + 1]);

        // Elements 2–28: from stored internal_nodes (levels 1–27).
        for k in 2..H {
            running >>= 1; // descends from level 28 toward root
            path[k] = self.internal_nodes[running ^ 1];
        }

        path
    }

    // ── private helpers ───────────────────────────────────────────────────

    fn bud(commitment: Digest, index: u64) -> Digest {
        Tip5::hash_pair(
            commitment,
            Digest::new([
                BFieldElement::new(index),
                BFieldElement::new(0),
                BFieldElement::new(0),
                BFieldElement::new(0),
                BFieldElement::new(0),
            ]),
        )
    }

    /// Bit-reversal of a k-bit integer.
    fn bitreverse(mut n: u32, bits: u32) -> u32 {
        n = ((n & 0x5555_5555) << 1) | ((n & 0xaaaa_aaaa) >> 1);
        n = ((n & 0x3333_3333) << 2) | ((n & 0xcccc_cccc) >> 2);
        n = ((n & 0x0f0f_0f0f) << 4) | ((n & 0xf0f0_f0f0) >> 4);
        n = ((n & 0x00ff_00ff) << 8) | ((n & 0xff00_ff00) >> 8);
        n = n.rotate_right(16);
        n >> ((32 - bits) & 0x1f)
    }

    /// 5-round butterfly computation from buds to leaves + bit-reversal.
    /// Uses two NUM_LEAFS-sized buffers; drops one after completion.
    fn compute_leafs(prev_block_digest: Digest, bit_reverse: bool) -> Vec<Digest> {
        Self::leafs_at_height(prev_block_digest, bit_reverse, HEIGHT)
    }

    fn leafs_at_height(prev_block_digest: Digest, bit_reverse: bool, height: usize) -> Vec<Digest> {
        assert!((NUM_BUD_LAYERS..=HEIGHT).contains(&height));
        let num_leafs = 1usize << height;
        // Initial buds.
        let mut buf0: Vec<Digest> = (0u64..num_leafs as u64)
            .into_par_iter()
            .map(|i| Self::bud(prev_block_digest, i))
            .collect();
        let mut buf1 = buf0.clone();

        // NUM_BUD_LAYERS = 5 butterfly rounds (odd → result ends in buf0).
        for round in 0..NUM_BUD_LAYERS {
            let stride = 1usize << round;
            buf1.par_iter_mut().enumerate().for_each(|(k, out)| {
                *out = Tip5::hash_pair(buf0[k], buf0[(k + stride) % num_leafs]);
            });
            std::mem::swap(&mut buf0, &mut buf1);
        }
        // buf1 is now the discarded intermediate; drop it to reclaim memory.
        drop(buf1);

        // Bit-reversal permutation (for HardforkAlpha and later).
        if !bit_reverse {
            return buf0;
        }
        let bits = height as u32;
        for k in 0..num_leafs {
            let r = Self::bitreverse(k as u32, bits) as usize;
            if r > k {
                buf0.swap(k, r);
            }
        }

        buf0
    }

    /// Build top-28 internal node levels (1-indexed, 2^28 entries).
    ///
    /// Level 27 (indices [2^27, 2^28)) is computed directly from leaves.
    /// Levels 26–1 are built bottom-up from the level below.
    fn build_internal_nodes(leafs: &[Digest]) -> Vec<Digest> {
        let size = leafs.len() >> 1; // 2^28 for the production height
        let mut nodes = vec![Digest::default(); size];

        // Level 27: each node covers 4 leaves.
        // For index j in [2^27, 2^28), offset = j − 2^27:
        //   nodes[j] = hash(hash(leaf[4o], leaf[4o+1]), hash(leaf[4o+2], leaf[4o+3]))
        let lv27 = size >> 1; // 2^27
        nodes[lv27..]
            .par_iter_mut()
            .enumerate()
            .for_each(|(o, node)| {
                let b = o * 4;
                let left = Tip5::hash_pair(leafs[b], leafs[b + 1]);
                let right = Tip5::hash_pair(leafs[b + 2], leafs[b + 3]);
                *node = Tip5::hash_pair(left, right);
            });

        // Levels 26 down to 1: standard bottom-up Merkle.
        let mut child_start = lv27;
        while child_start > 1 {
            let parent_start = child_start >> 1;
            let (parent_half, child_half) = nodes.split_at_mut(child_start);
            parent_half[parent_start..]
                .par_iter_mut()
                .enumerate()
                .for_each(|(o, node)| {
                    *node = Tip5::hash_pair(child_half[o * 2], child_half[o * 2 + 1]);
                });
            child_start = parent_start;
        }

        nodes
    }
}

// ── helpers ────────────────────────────────────────────────────────────────

/// 63-Tip5 index derivation (matches neptune-core's `Pow::indices()`).
fn indices(index_preimage: Digest, nonce: Digest) -> (usize, usize) {
    let mut h = Tip5::hash_pair(index_preimage, nonce);
    for _ in 1..NUM_INDEX_REPETITIONS {
        h = Tip5::hash_pair(h, Digest::default());
    }
    let a = h.values()[0].value() as usize % NUM_LEAFS;
    let b = h.values()[1].value() as usize % NUM_LEAFS;
    (a, b)
}

/// Thread-local pseudo-random Digest from a counter + thread seed.
/// Uses Tip5 (acpu) so diversity is hash-quality without a rand dependency.
#[inline(always)]
fn random_nonce(attempt: u64, tid: u64) -> Digest {
    let left = [
        BFieldElement::new(attempt).raw_u64(),
        BFieldElement::new(tid).raw_u64(),
        BFieldElement::new(attempt.wrapping_mul(6_364_136_223_846_793_005)).raw_u64(),
        BFieldElement::new(attempt.rotate_left(32) ^ tid).raw_u64(),
        BFieldElement::new(attempt.wrapping_add(tid.wrapping_mul(1_442_695_040_888_963_407)))
            .raw_u64(),
    ];
    raw_to_digest(crate::cpu::tip5_hash_pair(left, [0u64; 5]))
}

// ── mining entry points ───────────────────────────────────────────────────

/// HardforkBeta mining: no GuesserBuffer. Consensus rule validation only
/// checks `fast_mast_hash(pow) ≤ target`; paths are not Merkle-verified.
///
/// `path_a` must come from the block template's header.pow.pathA (the
/// composer pre-encodes lustration_status at path_a[27..28] and version
/// at path_a[26]). `root` and `path_b` are all zeros.
///
/// Returns `None` if no winning nonce is found within `max_attempts`.
pub fn mine_hardfork_beta(
    path_a: [Digest; HEIGHT],
    mast_paths: &PowMastPaths,
    target: Digest,
    max_attempts: u64,
) -> Option<NeptunePow> {
    mine_cpu_range(path_a, mast_paths, target, 0, max_attempts)
}

/// Mine a disjoint nonce range, allowing a session to refresh between batches.
pub fn mine_cpu_range(
    path_a: [Digest; HEIGHT],
    mast_paths: &PowMastPaths,
    target: Digest,
    start: u64,
    max_attempts: u64,
) -> Option<NeptunePow> {
    let root = Digest::default();
    let path_b = [Digest::default(); HEIGHT];
    let num_threads = thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(12);
    eprintln!("Neptune HardforkBeta mining: {num_threads} P-core threads, target={target}");
    let t0 = std::time::Instant::now();

    let attempts = Attempts::new(start, max_attempts);
    let winner = Winner::new();
    let actual = AtomicU64::new(0);
    thread::scope(|s| {
        for tid in 0..num_threads as u64 {
            let attempts = &attempts;
            let winner = &winner;
            let actual = &actual;
            s.spawn(move || {
                crate::cpu::pin_worker();
                while !winner.found() {
                    let Some(range) = attempts.reserve(1) else {
                        break;
                    };
                    let pow = NeptunePow {
                        root,
                        path_a,
                        path_b,
                        nonce: random_nonce(range.start, tid),
                    };
                    actual.fetch_add(1, Ordering::Relaxed);
                    if mast_paths.fast_mast_hash(&pow) <= target {
                        winner.publish(pow);
                    }
                }
            });
        }
    });
    let result = winner.take();
    if result.is_some() {
        eprintln!(
            "Found nonce: {} hashes in {:.3}s",
            actual.load(Ordering::Relaxed),
            t0.elapsed().as_secs_f64()
        );
    }
    result
}

/// Benchmark hashrate for HardforkBeta PoW (no GuesserBuffer).
/// Runs for `duration_secs` seconds using P-core-pinned std::thread workers.
pub fn benchmark_hardfork_beta(duration_secs: f64) {
    if !duration_secs.is_finite() || !(0.0..=86400.0).contains(&duration_secs) {
        eprintln!("benchmark duration must be finite and at most one day");
        return;
    }
    let root = Digest::default();
    let path_a = [Digest::default(); HEIGHT];
    let path_b = [Digest::default(); HEIGHT];
    let mast_paths = PowMastPaths::default();

    let num_threads = thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(12);
    eprintln!(
        "Benchmarking HardforkBeta PoW ({num_threads} P-core threads, {duration_secs:.0}s)..."
    );

    let counter = AtomicU64::new(0);
    let stop = AtomicU32::new(0);
    let t0 = std::time::Instant::now();

    thread::scope(|s| {
        for tid in 0..num_threads as u64 {
            let counter = &counter;
            let stop = &stop;
            let mast_paths = &mast_paths;
            s.spawn(move || {
                crate::cpu::pin_worker();
                while stop.load(Ordering::Relaxed) == 0 {
                    let attempt = counter.fetch_add(1, Ordering::Relaxed);
                    let nonce = random_nonce(attempt, tid);
                    let pow = NeptunePow {
                        root,
                        path_a,
                        path_b,
                        nonce,
                    };
                    let _ = mast_paths.fast_mast_hash(&pow);
                }
            });
        }
        thread::sleep(std::time::Duration::from_secs_f64(duration_secs));
        stop.store(1, Ordering::Release);
    });

    let total = counter.load(Ordering::Relaxed);
    let elapsed = t0.elapsed().as_secs_f64();
    let hps = total as f64 / elapsed;
    eprintln!(
        "Result: {} attempts in {:.2}s = {:.0} H/s ({:.2} MH/s)",
        total,
        elapsed,
        hps,
        hps / 1e6
    );
}

/// GPU mining for HardforkBeta using the aruminium MSL kernel.
///
/// Uploads block template once, then loops GPU batches until `max_attempts`
/// is exhausted or a winning nonce is found.
/// Returns `None` on GPU unavailability as well.
#[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
pub fn mine_hardfork_beta_gpu(
    path_a: [Digest; HEIGHT],
    mast_paths: &PowMastPaths,
    target: Digest,
    max_attempts: u64,
) -> Option<NeptunePow> {
    let mut miner = crate::aruminium_mine::AruMine::try_new()?;
    mine_with_gpu(&mut miner, path_a, mast_paths, target, max_attempts, true)
}

/// Reuse an initialized GPU; exhaustion is distinct from initialization failure.
#[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
pub fn mine_with_gpu(
    miner: &mut crate::aruminium_mine::AruMine,
    path_a: [Digest; HEIGHT],
    mast_paths: &PowMastPaths,
    target: Digest,
    max_attempts: u64,
    with_cpu: bool,
) -> Option<NeptunePow> {
    mine_gpu_range(miner, path_a, mast_paths, target, 0, max_attempts, with_cpu)
}

#[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
pub fn mine_gpu_range(
    miner: &mut crate::aruminium_mine::AruMine,
    path_a: [Digest; HEIGHT],
    mast_paths: &PowMastPaths,
    target: Digest,
    start: u64,
    max_attempts: u64,
    with_cpu: bool,
) -> Option<NeptunePow> {
    use crate::aruminium_mine::THREADS_TOTAL;
    miner.set_template(&path_a, mast_paths, &target);
    let attempts = Attempts::new(start, max_attempts);
    let winner = Winner::new();
    let cpu_threads = if with_cpu {
        thread::available_parallelism()
            .map(|n| n.get())
            .unwrap_or(1)
            .saturating_sub(1)
    } else {
        0
    };
    thread::scope(|s| {
        for tid in 0..cpu_threads as u64 {
            let attempts = &attempts;
            let winner = &winner;
            s.spawn(move || {
                crate::cpu::pin_worker();
                while !winner.found() {
                    let Some(range) = attempts.reserve(1) else {
                        break;
                    };
                    let pow = NeptunePow {
                        root: Digest::default(),
                        path_a,
                        path_b: [Digest::default(); HEIGHT],
                        nonce: random_nonce(range.start, tid),
                    };
                    if mast_paths.fast_mast_hash(&pow) <= target {
                        winner.publish(pow);
                    }
                }
            });
        }
        // GPU stays on this thread; no mapped buffers or flags reach CPU workers.
        while !winner.found() {
            let Some(range) = attempts.reserve(THREADS_TOTAL as u64) else {
                break;
            };
            if let Some(nonce) =
                miner.dispatch_batch(range.start, (range.end - range.start) as usize)
            {
                let pow = NeptunePow {
                    root: Digest::default(),
                    path_a,
                    path_b: [Digest::default(); HEIGHT],
                    nonce,
                };
                if mast_paths.fast_mast_hash(&pow) <= target {
                    winner.publish(pow);
                } else {
                    panic!("GPU returned an invalid mining result");
                }
            }
        }
    });
    winner.take()
}

/// Benchmark GPU Tip5 throughput using the aruminium MSL kernel.
/// Runs for `duration_secs` seconds and prints MH/s.
#[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
pub fn benchmark_gpu(duration_secs: f64) {
    if !duration_secs.is_finite() || !(0.0..=86400.0).contains(&duration_secs) {
        eprintln!("benchmark duration must be finite and at most one day");
        return;
    }
    use crate::aruminium_mine::{AruMine, THREADS_TOTAL};
    let mut miner = match AruMine::try_new() {
        Some(m) => m,
        None => {
            eprintln!("AruMine: no Metal GPU available");
            return;
        }
    };
    let path_a = [Digest::default(); HEIGHT];
    let mast = PowMastPaths::default();
    // Target always-fail: benchmark pure hash throughput, no winners expected.
    let target = Digest::new([BFieldElement::new(0); 5]);
    miner.set_template(&path_a, &mast, &target);
    eprintln!("Benchmarking GPU (AruMine) for {duration_secs:.0}s...");
    let t0 = std::time::Instant::now();
    let deadline = t0 + std::time::Duration::from_secs_f64(duration_secs);
    let mut total = 0u64;
    let mut batch = 0u64;
    loop {
        if std::time::Instant::now() >= deadline {
            break;
        }
        miner.dispatch_batch(batch * THREADS_TOTAL as u64, THREADS_TOTAL);
        total += THREADS_TOTAL as u64;
        batch += 1;
    }
    let elapsed = t0.elapsed().as_secs_f64();
    let hps = total as f64 / elapsed;
    eprintln!(
        "GPU: {total} attempts in {elapsed:.2}s = {hps:.0} H/s ({:.3} MH/s)",
        hps / 1e6
    );
}

/// Memory-hard mining (pre-HardforkBeta): uses the full 32 GB GuesserBuffer.
///
/// Returns `None` if no winning nonce is found within `max_attempts`.
pub fn mine(
    buffer: &GuesserBuffer,
    mast_paths: &PowMastPaths,
    target: Digest,
    max_attempts: u64,
) -> Option<NeptunePow> {
    mine_legacy_range(buffer, mast_paths, target, 0, max_attempts)
}

pub fn mine_legacy_range(
    buffer: &GuesserBuffer,
    mast_paths: &PowMastPaths,
    target: Digest,
    start: u64,
    max_attempts: u64,
) -> Option<NeptunePow> {
    let root = buffer.root();
    let index_preimage = Tip5::hash_pair(root, mast_paths.commit());
    let threads = rayon::current_num_threads();
    eprintln!("Neptune memory-hard mining: {threads} threads, target={target}");
    let t0 = std::time::Instant::now();

    let actual = AtomicU64::new(0);
    let result = (start
        ..start
            .checked_add(max_attempts)
            .expect("attempt range overflow"))
        .into_par_iter()
        .find_map_any(|attempt| {
            actual.fetch_add(1, Ordering::Relaxed);
            let tid = rayon::current_thread_index().unwrap_or(0) as u64;
            let nonce = random_nonce(attempt, tid);
            let (ia, ib) = indices(index_preimage, nonce);
            let path_a = buffer.path(ia);
            let path_b = buffer.path(ib);
            let pow = NeptunePow {
                root,
                path_a,
                path_b,
                nonce,
            };
            if mast_paths.fast_mast_hash(&pow) <= target {
                Some(pow)
            } else {
                None
            }
        });

    if result.is_some() {
        let elapsed = t0.elapsed().as_secs_f64();
        eprintln!(
            "Found nonce in {:.1}s ({:.0} H/s)",
            elapsed,
            actual.load(Ordering::Relaxed) as f64 / elapsed
        );
    }

    result
}

#[cfg(test)]
mod legacy_layout_tests {
    use super::*;
    #[test]
    fn reboot_and_alpha_leaf_order_match_independent_pairwise_construction() {
        let parent = Digest::new([BFieldElement::new(7); 5]);
        let mast = PowMastPaths::default().commit();
        for (prefix, reverse) in [(mast, false), (parent, true)] {
            let actual = GuesserBuffer::leafs_at_height(prefix, reverse, 6);
            let buffer = GuesserBuffer {
                internal_nodes: GuesserBuffer::build_internal_nodes(&actual),
                leafs: actual.clone(),
                prev_block_digest: prefix,
            };
            let mut direct_tree = actual.clone();
            while direct_tree.len() > 1 {
                direct_tree = direct_tree
                    .chunks_exact(2)
                    .map(|p| Tip5::hash_pair(p[0], p[1]))
                    .collect();
            }
            assert_eq!(buffer.root(), direct_tree[0]);
            for index in 0..64 {
                let mut node = actual[index];
                for (level, sibling) in buffer.path_at_height::<6>(index).iter().enumerate() {
                    node = if (index >> level) & 1 == 0 {
                        Tip5::hash_pair(node, *sibling)
                    } else {
                        Tip5::hash_pair(*sibling, node)
                    };
                }
                assert_eq!(node, direct_tree[0], "authentication path {index}");
            }
            for (index, leaf) in actual.iter().enumerate() {
                let start = if reverse {
                    (index as u32).reverse_bits() >> 26
                } else {
                    index as u32
                };
                // Independent native verification algorithm: 32 consecutive buds,
                // bottom-up pairs. It does not use the all-leaf butterfly implementation.
                let mut layer: Vec<_> = (0..32)
                    .map(|i| {
                        Tip5::hash_pair(
                            prefix,
                            Digest::new([
                                BFieldElement::new(((start + i) % 64) as u64),
                                BFieldElement::new(0),
                                BFieldElement::new(0),
                                BFieldElement::new(0),
                                BFieldElement::new(0),
                            ]),
                        )
                    })
                    .collect();
                while layer.len() > 1 {
                    layer = layer
                        .chunks_exact(2)
                        .map(|pair| Tip5::hash_pair(pair[0], pair[1]))
                        .collect();
                }
                assert_eq!(*leaf, layer[0]);
            }
        }
    }
}
