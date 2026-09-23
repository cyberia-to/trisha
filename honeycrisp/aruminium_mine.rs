//! Apple Silicon GPU mining via aruminium + MSL Tip5 kernel.
//!
//! Buffers are allocated as `aruminium::Buffer` (MTLStorageModeShared) and
//! accessed through exclusive typed views over the same physical pages.
//! Only the small nonce-range dispatch argument is serialized separately.

use aruminium::{Buffer, Dispatch, Gpu, GpuError, Pipeline, Queue};
use twenty_first::prelude::*;
use twenty_first::tip5::{MDS_MATRIX_FIRST_COLUMN, ROUND_CONSTANTS};

use crate::neptune_mine::{PowMastPaths, HEIGHT};
use crate::types::{BlockTemplate, MineState};

const THREADS_PER_GROUP: usize = 256;
const NUM_GROUPS: usize = 4096;
pub const THREADS_TOTAL: usize = THREADS_PER_GROUP * NUM_GROUPS; // 1 048 576 nonces/launch

/// Exclusively borrowed synchronous GPU miner. No mapped reference escapes.
/// CPU workers publish separately through the host winner slot.
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
    configured: bool,
}

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

        // Initialize every mapped byte before creating typed references.
        unsafe {
            std::ptr::write_bytes(
                template_buf.as_bytes().as_ptr() as *mut u8,
                0,
                template_buf.size(),
            );
            std::ptr::write_bytes(
                state_buf.as_bytes().as_ptr() as *mut u8,
                0,
                state_buf.size(),
            );
        }

        Some(Self {
            gpu,
            queue,
            dispatch,
            pipeline,
            template_buf,
            state_buf,
            mds_buf,
            rc_buf,
            configured: false,
        })
    }

    /// Configure only while exclusively borrowed and no dispatch is in flight.
    pub fn set_template(
        &mut self,
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

        unsafe { state_view_mut(&self.state_buf) }.reset();
        self.configured = true;
    }

    /// Execute exactly `count` nonce hashes, then copy the winning nonce.
    /// The command completes before any mapped result is read or returned.
    pub fn dispatch_batch(&mut self, nonce_base: u64, count: usize) -> Option<Digest> {
        assert!(self.configured, "configure mining template before dispatch");
        assert!(count <= THREADS_TOTAL);
        if count == 0 {
            return None;
        }
        nonce_base
            .checked_add(count as u64 - 1)
            .expect("nonce range overflow");
        unsafe { state_view_mut(&self.state_buf) }.reset();
        const OFF_PATH_A: usize = 0;
        const OFF_MAST: usize = OFF_PATH_A + 145 * 8; // 1160
        const OFF_TARGET: usize = OFF_MAST + 30 * 8; // 1400
        const OFF_FOUND: usize = 0;
        const OFF_RESULT: usize = 8; // skip past found + _pad

        let mut nonce_bytes = [0u8; 16];
        nonce_bytes[..8].copy_from_slice(&nonce_base.to_le_bytes());
        nonce_bytes[8..].copy_from_slice(&(count as u64).to_le_bytes());
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
                (count.div_ceil(THREADS_PER_GROUP) * THREADS_PER_GROUP, 1, 1),
                (THREADS_PER_GROUP, 1, 1),
            );
        }
        let state = unsafe { state_view(&self.state_buf) };
        if state.found.load(std::sync::atomic::Ordering::Acquire) == 0 {
            return None;
        }
        Some(Digest::new(
            state.winning_nonce.map(BFieldElement::from_raw_u64),
        ))
    }
}

// ── typed view helpers (shared CPU/GPU memory; aliasing checked by API) ──

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
    let view: &mut [u64; 16] = unsafe { &mut *(buf.as_bytes().as_ptr() as *mut [u64; 16]) };
    for (i, &v) in MDS_MATRIX_FIRST_COLUMN.iter().enumerate() {
        view[i] = BFieldElement::new(v as u64).raw_u64();
    }
}

fn upload_rc(buf: &Buffer) {
    let view: &mut [u64; 80] = unsafe { &mut *(buf.as_bytes().as_ptr() as *mut [u64; 80]) };
    for (i, &bfe) in ROUND_CONSTANTS.iter().enumerate() {
        view[i] = bfe.raw_u64();
    }
}
