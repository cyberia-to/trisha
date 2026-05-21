//! Real Neptune PoW mining — partial GuesserBuffer (32 GB) + rayon parallel search.
//!
//! Mirrors neptune-core's PoW protocol for TvmProofVersion1 / HardforkBeta.
//! All type layouts match neptune-cash v0.10.2.
//!
//! Memory layout of GuesserBuffer:
//!   leaves (all 2^29):          21.47 GB  (required)
//!   internal_nodes (top 28 lv): 10.74 GB  (1-indexed, levels 1–27)
//!   bottom internal level:      OMITTED    (computed on demand: 1 Tip5 per path)
//!   Total at rest:              32.21 GB
//!   Peak during build:         ~43    GB  (two leaf-sized butterfly buffers)

use rayon::prelude::*;
use triton_vm::prelude::*;

// ── neptune-core constants (neptune-cash v0.10.2) ─────────────────────────

pub const HEIGHT: usize = 29;
pub const NUM_LEAFS: usize = 1 << HEIGHT;

const NUM_BUD_LAYERS: usize = 5;
const NUM_INDEX_REPETITIONS: u32 = 63;

// MAST heights derived from neptune-core FieldEnum variant counts:
//   BlockHeaderField: 8 variants → next_power_of_two(8)=8, ilog2=3
//   BlockKernelField: 3 variants → next_power_of_two(3)=4, ilog2=2
//   BlockField:       2 variants → next_power_of_two(2)=2, ilog2=1
pub const POW_PATH_LEN: usize = 3;
pub const HEADER_PATH_LEN: usize = 2;
pub const KERNEL_PATH_LEN: usize = 1;

// ── types ─────────────────────────────────────────────────────────────────

/// Mirror of neptune-core's `PowMastPaths`.
/// Obtained from neptune-core RPC when a new block template arrives.
#[derive(Clone, Debug, Default)]
pub struct PowMastPaths {
    pub pow:    [Digest; POW_PATH_LEN],
    pub header: [Digest; HEADER_PATH_LEN],
    pub kernel: [Digest; KERNEL_PATH_LEN],
}

/// Mirror of neptune-core's `Pow<HEIGHT>`.
#[derive(Clone, Debug)]
pub struct NeptunePow {
    pub root:   Digest,
    pub path_a: [Digest; HEIGHT],
    pub path_b: [Digest; HEIGHT],
    pub nonce:  Digest,
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
    /// ~39 Tip5 permutations at HEIGHT = 29.
    pub fn fast_mast_hash(&self, pow: &NeptunePow) -> Digest {
        let header_hash = Tip5::hash_pair(Tip5::hash_varlen(&pow.encode()), self.pow[0]);
        let header_hash = Tip5::hash_pair(header_hash, self.pow[1]);
        let header_hash = Tip5::hash_pair(self.pow[2], header_hash);

        let kernel_hash = Tip5::hash_pair(
            Tip5::hash_varlen(&header_hash.values().to_vec()),
            self.header[0],
        );
        let kernel_hash = Tip5::hash_pair(kernel_hash, self.header[1]);

        Tip5::hash_pair(
            Tip5::hash_varlen(&kernel_hash.values().to_vec()),
            self.kernel[0],
        )
    }
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
    pub leafs:             Vec<Digest>,
    pub internal_nodes:    Vec<Digest>, // 2^28 entries, 1-indexed, levels 1–27
    pub prev_block_digest: Digest,
}

impl GuesserBuffer {
    /// Build from the parent block digest. Allocates ~43 GB at peak.
    pub fn build(prev_block_digest: Digest) -> Self {
        eprintln!("GuesserBuffer: generating {NUM_LEAFS} leaves...");
        let t0 = std::time::Instant::now();
        let leafs = Self::compute_leafs(prev_block_digest);
        eprintln!("  leaves: {:.1}s", t0.elapsed().as_secs_f64());

        eprintln!("GuesserBuffer: building partial internal nodes (top 28 levels)...");
        let t1 = std::time::Instant::now();
        let internal_nodes = Self::build_internal_nodes(&leafs);
        eprintln!(
            "  internal: {:.1}s — root: {}",
            t1.elapsed().as_secs_f64(),
            internal_nodes[1]
        );

        Self { leafs, internal_nodes, prev_block_digest }
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
        let mut path = [Digest::default(); HEIGHT];

        // Element 0: sibling leaf.
        path[0] = self.leafs[idx ^ 1];

        // Element 1: bottom internal sibling (level 28, omitted from storage).
        // running_index = (idx + NUM_LEAFS) >> 1  is in [2^28, 2^29).
        // sibling_1     = running_index ^ 1        is in [2^28, 2^29).
        // For j = sibling_1 − 2^28:
        //   internal_nodes_full[sibling_1] = hash(leaf[2j], leaf[2j+1]).
        let mut running = (idx + NUM_LEAFS) >> 1;
        let sib1 = running ^ 1;
        let j = sib1 - (NUM_LEAFS >> 1);
        path[1] = Tip5::hash_pair(self.leafs[2 * j], self.leafs[2 * j + 1]);

        // Elements 2–28: from stored internal_nodes (levels 1–27).
        for k in 2..HEIGHT {
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
    fn compute_leafs(prev_block_digest: Digest) -> Vec<Digest> {
        // Initial buds.
        let mut buf0: Vec<Digest> = (0u64..NUM_LEAFS as u64)
            .into_par_iter()
            .map(|i| Self::bud(prev_block_digest, i))
            .collect();
        let mut buf1 = buf0.clone();

        // NUM_BUD_LAYERS = 5 butterfly rounds (odd → result ends in buf0).
        for round in 0..NUM_BUD_LAYERS {
            let stride = 1usize << round;
            buf1.par_iter_mut().enumerate().for_each(|(k, out)| {
                *out = Tip5::hash_pair(buf0[k], buf0[(k + stride) % NUM_LEAFS]);
            });
            std::mem::swap(&mut buf0, &mut buf1);
        }
        // buf1 is now the discarded intermediate; drop it to reclaim memory.
        drop(buf1);

        // Bit-reversal permutation (for HardforkAlpha and later).
        let bits = NUM_LEAFS.ilog2();
        for k in 0..NUM_LEAFS {
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
        let size = NUM_LEAFS >> 1; // 2^28
        let mut nodes = vec![Digest::default(); size];

        // Level 27: each node covers 4 leaves.
        // For index j in [2^27, 2^28), offset = j − 2^27:
        //   nodes[j] = hash(hash(leaf[4o], leaf[4o+1]), hash(leaf[4o+2], leaf[4o+3]))
        let lv27 = size >> 1; // 2^27
        nodes[lv27..].par_iter_mut().enumerate().for_each(|(o, node)| {
            let b = o * 4;
            let left  = Tip5::hash_pair(leafs[b],     leafs[b + 1]);
            let right = Tip5::hash_pair(leafs[b + 2], leafs[b + 3]);
            *node = Tip5::hash_pair(left, right);
        });

        // Levels 26 down to 1: standard bottom-up Merkle.
        let mut child_start = lv27;
        while child_start > 1 {
            let parent_start = child_start >> 1;
            let (parent_half, child_half) = nodes.split_at_mut(child_start);
            parent_half[parent_start..].par_iter_mut().enumerate().for_each(|(o, node)| {
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
/// Uses Tip5 so diversity is hash-quality without a rand dependency.
fn random_nonce(attempt: u64) -> Digest {
    // Mix attempt with a per-thread seed to avoid all threads searching
    // the same nonces.
    let tid = rayon::current_thread_index().unwrap_or(0) as u64;
    Tip5::hash_pair(
        Digest::new([
            BFieldElement::new(attempt),
            BFieldElement::new(tid),
            BFieldElement::new(attempt.wrapping_mul(6_364_136_223_846_793_005)),
            BFieldElement::new(attempt.rotate_left(32) ^ tid),
            BFieldElement::new(attempt.wrapping_add(tid.wrapping_mul(1_442_695_040_888_963_407))),
        ]),
        Digest::default(),
    )
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
    let root = Digest::default();
    let path_b = [Digest::default(); HEIGHT];
    let threads = rayon::current_num_threads();
    eprintln!("Neptune HardforkBeta mining: {threads} threads, target={target}");
    let t0 = std::time::Instant::now();

    let result = (0u64..max_attempts).into_par_iter().find_map_any(|attempt| {
        let nonce = random_nonce(attempt);
        let pow = NeptunePow { root, path_a, path_b, nonce };
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
            max_attempts as f64 / elapsed
        );
    }

    result
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
    let root = buffer.root();
    let index_preimage = Tip5::hash_pair(root, mast_paths.commit());
    let threads = rayon::current_num_threads();
    eprintln!("Neptune memory-hard mining: {threads} threads, target={target}");
    let t0 = std::time::Instant::now();

    let result = (0u64..max_attempts).into_par_iter().find_map_any(|attempt| {
        let nonce = random_nonce(attempt);
        let (ia, ib) = indices(index_preimage, nonce);
        let path_a = buffer.path(ia);
        let path_b = buffer.path(ib);
        let pow = NeptunePow { root, path_a, path_b, nonce };
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
            max_attempts as f64 / elapsed
        );
    }

    result
}
