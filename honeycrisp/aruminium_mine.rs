//! Apple Silicon GPU mining via aruminium + MSL Tip5 kernel.
//!
//! Buffers are allocated as `aruminium::Buffer` (MTLStorageModeShared) and
//! accessed via typed views over the same physical pages — no marshalling,
//! no `to_le_bytes()`. CPU and GPU literally read and write the same memory.

use aruminium::{Buffer, Dispatch, Gpu, GpuError, Pipeline, Queue};
use twenty_first::prelude::*;
use twenty_first::tip5::{MDS_MATRIX_FIRST_COLUMN, ROUND_CONSTANTS};

use crate::neptune_mine::{PowMastPaths, HEIGHT};
use crate::types::{BlockTemplate, MineState};

const THREADS_PER_GROUP: usize = 256;
const NUM_GROUPS: usize = 4096;
pub const THREADS_TOTAL: usize = THREADS_PER_GROUP * NUM_GROUPS; // 1 048 576 nonces/launch

/// Apple Silicon GPU miner. Compiled once, reused across block templates.
///
/// `template_buf` and `state_buf` are sized for `BlockTemplate` and `MineState`
/// respectively and are addressed by both CPU and GPU. The CPU writes the
/// template via `set_template`, the GPU reads it during dispatch; both can
/// race on `state.found` to claim a winning nonce.
///
/// Safety: Metal command queues, buffers and pipelines are thread-safe per
/// Apple's documentation. The constraint is that command-buffer encoding
/// (`dispatch_batch`) must be serialized — only ONE thread may call it at
/// a time. The shared `state()` view is atomic-safe for concurrent access.
pub struct AruMine {
    #[allow(dead_code)]
    gpu: Gpu,
    #[allow(dead_code)]
    queue: Queue,
    dispatch: Dispatch,
    pipeline: Pipeline,
    template_buf: Buffer,
    state_buf: Buffer,
    mds_buf: Buffer,
    rc_buf: Buffer,
}

// Safety: see doc comment on `AruMine` — Metal objects are thread-safe;
// the only constraint is single-threaded `dispatch_batch` calls.
unsafe impl Send for AruMine {}
unsafe impl Sync for AruMine {}

impl AruMine {
    /// Compile the MSL kernel and allocate GPU/CPU shared buffers.
    /// Returns `None` if Metal is unavailable.
    pub fn try_new() -> Option<Self> {
        let gpu = Gpu::open().ok()?;
        let queue = gpu.new_command_queue().ok()?;

        let msl_src = include_str!("tip5.metal").to_string();
        let lib = match gpu.compile(&msl_src) {
            Ok(l) => l,
            Err(GpuError::LibraryCompilationFailed(msg)) => {
                eprintln!("AruMine: MSL compile failed: {}", msg);
                return None;
            }
            Err(e) => {
                eprintln!("AruMine: GPU error: {}", e);
                return None;
            }
        };
        let func = lib.function("npt_mine").ok()?;
        let pipeline = gpu.pipeline(&func).ok()?;
        let dispatch = Dispatch::new(&queue);

        let template_buf = gpu.buffer(std::mem::size_of::<BlockTemplate>()).ok()?;
        let state_buf = gpu.buffer(std::mem::size_of::<MineState>()).ok()?;
        let mds_buf = gpu.buffer(16 * 8).ok()?;
        let rc_buf = gpu.buffer(80 * 8).ok()?;

        // Tip5 constants are immutable for the kernel's lifetime.
        upload_mds(&mds_buf);
        upload_rc(&rc_buf);

        // Zero-initialise the shared state.
        unsafe { state_view_mut(&state_buf) }.reset();

        Some(Self {
            gpu,
            queue,
            dispatch,
            pipeline,
            template_buf,
            state_buf,
            mds_buf,
            rc_buf,
        })
    }

    /// Borrow the shared `MineState` (atomic-friendly). CPU and GPU workers
    /// race on `state().found` to claim a winning nonce.
    pub fn state(&self) -> &MineState {
        unsafe { state_view(&self.state_buf) }
    }

    /// Borrow the shared `BlockTemplate` (read-only after `set_template`).
    pub fn template(&self) -> &BlockTemplate {
        unsafe { template_view(&self.template_buf) }
    }

    /// Write a fresh template into the shared buffer and reset mining state.
    /// CPU and GPU both see the new template on the next read.
    pub fn set_template(
        &self,
        path_a: &[Digest; HEIGHT],
        mast_paths: &PowMastPaths,
        target: &Digest,
    ) {
        let tmpl = unsafe { template_view_mut(&self.template_buf) };

        for (i, d) in path_a.iter().enumerate() {
            let v = d.values();
            for j in 0..5 {
                tmpl.path_a[i][j] = v[j].raw_u64();
            }
        }
        for (i, d) in mast_paths.pow.iter().enumerate() {
            let v = d.values();
            for j in 0..5 {
                tmpl.mast_pow[i][j] = v[j].raw_u64();
            }
        }
        for (i, d) in mast_paths.header.iter().enumerate() {
            let v = d.values();
            for j in 0..5 {
                tmpl.mast_header[i][j] = v[j].raw_u64();
            }
        }
        for (i, d) in mast_paths.kernel.iter().enumerate() {
            let v = d.values();
            for j in 0..5 {
                tmpl.mast_kernel[i][j] = v[j].raw_u64();
            }
        }
        for (i, bfe) in target.values().iter().enumerate() {
            tmpl.target[i] = bfe.value();
        }

        self.state().reset();
    }

    /// Dispatch one batch of [`THREADS_TOTAL`] nonces starting at `nonce_base`.
    ///
    /// Coordination is via the shared [`MineState::found`] atomic — callers
    /// read `state()` after dispatch (or concurrently from CPU workers) to
    /// observe wins. This call does NOT reset `found`; the session-level
    /// reset happens in [`Self::set_template`].
    ///
    /// The kernel sees 7 separate `constant ulong*` views into the merged
    /// `template_buf` (path_a / mast / target) and `state_buf` (found /
    /// result) at the offsets defined by `BlockTemplate` and `MineState`.
    /// Passing struct pointers directly was ~3-4× slower in measurement —
    /// MSL generates better code for direct `constant ulong*` arguments.
    pub fn dispatch_batch(&self, nonce_base: u64) {
        const OFF_PATH_A: usize = 0;
        const OFF_MAST: usize = OFF_PATH_A + 145 * 8; // 1160
        const OFF_TARGET: usize = OFF_MAST + 30 * 8; // 1400
        const OFF_FOUND: usize = 0;
        const OFF_RESULT: usize = 8; // skip past found + _pad

        let nonce_bytes = nonce_base.to_le_bytes();
        unsafe {
            self.dispatch.dispatch_with_bytes(
                &self.pipeline,
                &[
                    (&self.template_buf, OFF_PATH_A, 0),
                    (&self.template_buf, OFF_MAST, 1),
                    (&self.template_buf, OFF_TARGET, 2),
                    (&self.state_buf, OFF_FOUND, 3),
                    (&self.state_buf, OFF_RESULT, 4),
                    (&self.mds_buf, 0, 5),
                    (&self.rc_buf, 0, 6),
                ],
                &nonce_bytes,
                7,
                (THREADS_TOTAL, 1, 1),
                (THREADS_PER_GROUP, 1, 1),
            );
        }
    }
}

// ── typed view helpers (shared CPU/GPU memory; aliasing checked by API) ──

unsafe fn template_view(buf: &Buffer) -> &BlockTemplate {
    debug_assert!(buf.size() >= std::mem::size_of::<BlockTemplate>());
    &*(buf.as_bytes().as_ptr() as *const BlockTemplate)
}

#[allow(clippy::mut_from_ref)]
unsafe fn template_view_mut(buf: &Buffer) -> &mut BlockTemplate {
    debug_assert!(buf.size() >= std::mem::size_of::<BlockTemplate>());
    &mut *(buf.as_bytes().as_ptr() as *mut BlockTemplate)
}

unsafe fn state_view(buf: &Buffer) -> &MineState {
    debug_assert!(buf.size() >= std::mem::size_of::<MineState>());
    &*(buf.as_bytes().as_ptr() as *const MineState)
}

#[allow(clippy::mut_from_ref)]
unsafe fn state_view_mut(buf: &Buffer) -> &mut MineState {
    debug_assert!(buf.size() >= std::mem::size_of::<MineState>());
    &mut *(buf.as_bytes().as_ptr() as *mut MineState)
}

// ── Constant upload helpers ───────────────────────────────────────────────────

fn upload_mds(buf: &Buffer) {
    let view: &mut [u64; 16] =
        unsafe { &mut *(buf.as_bytes().as_ptr() as *mut [u64; 16]) };
    for (i, &v) in MDS_MATRIX_FIRST_COLUMN.iter().enumerate() {
        view[i] = BFieldElement::new(v as u64).raw_u64();
    }
}

fn upload_rc(buf: &Buffer) {
    let view: &mut [u64; 80] =
        unsafe { &mut *(buf.as_bytes().as_ptr() as *mut [u64; 80]) };
    for (i, &bfe) in ROUND_CONSTANTS.iter().enumerate() {
        view[i] = bfe.raw_u64();
    }
}
