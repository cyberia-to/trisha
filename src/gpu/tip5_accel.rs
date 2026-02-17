//! GPU-accelerated Tip5 batch hashing via wgpu.
//!
//! Implements `triton_vm::gpu::GpuAccelerator` to offload Tip5 hash_varlen
//! to the GPU during STARK proving. The prover calls `hash_varlen_batch`
//! to hash all LDE table rows into Merkle tree leaves — the dominant cost
//! in Merkle tree construction.
//!
//! Uses the `tip5.wgsl` compute shader with Goldilocks field arithmetic.

use wgpu;
use wgpu::util::DeviceExt;

use triton_vm::gpu::GpuAccelerator;
use twenty_first::prelude::*;

const DIGEST_LEN: usize = 5;
const WORKGROUP_SIZE: u32 = 64;

/// Tip5 constants for GPU upload.
struct Tip5Constants {
    /// 256-entry split-and-lookup S-box table (as u32 for GPU).
    lookup_table: [u32; 256],
    /// MDS first column as canonical Goldilocks field elements (lo, hi pairs).
    mds_column: [[u32; 2]; 16],
    /// Round constants as canonical Goldilocks field elements (lo, hi pairs).
    round_constants: [[u32; 2]; 80],
}

impl Tip5Constants {
    fn load() -> Self {
        use twenty_first::tip5::LOOKUP_TABLE;
        use twenty_first::tip5::MDS_MATRIX_FIRST_COLUMN;
        use twenty_first::tip5::ROUND_CONSTANTS;

        let lookup_table: [u32; 256] = {
            let mut table = [0u32; 256];
            for (i, &v) in LOOKUP_TABLE.iter().enumerate() {
                table[i] = v as u32;
            }
            table
        };

        let mds_column: [[u32; 2]; 16] = {
            let mut col = [[0u32; 2]; 16];
            for (i, &v) in MDS_MATRIX_FIRST_COLUMN.iter().enumerate() {
                // MDS coefficients are small positive i64 values.
                // Convert to Montgomery representation via BFieldElement::new().
                let bfe = BFieldElement::new(v as u64);
                let raw = bfe.raw_u64();
                col[i] = [raw as u32, (raw >> 32) as u32];
            }
            col
        };

        let round_constants: [[u32; 2]; 80] = {
            let mut rc = [[0u32; 2]; 80];
            for (i, &bfe) in ROUND_CONSTANTS.iter().enumerate() {
                // Round constants are already BFieldElements in Montgomery form.
                let raw = bfe.raw_u64();
                rc[i] = [raw as u32, (raw >> 32) as u32];
            }
            rc
        };

        Tip5Constants {
            lookup_table,
            mds_column,
            round_constants,
        }
    }
}

/// wgpu-based Tip5 batch hasher implementing triton-vm's GpuAccelerator.
pub struct WgpuTip5Accelerator {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::ComputePipeline,
    // Persistent constant buffers (uploaded once at init)
    lookup_buf: wgpu::Buffer,
    mds_buf: wgpu::Buffer,
    rc_buf: wgpu::Buffer,
}

impl WgpuTip5Accelerator {
    /// Create a new accelerator using an existing wgpu device and queue.
    pub fn new(device: wgpu::Device, queue: wgpu::Queue) -> Self {
        let goldilocks_src = include_str!("shaders/goldilocks.wgsl");
        let tip5_src = include_str!("shaders/tip5.wgsl");
        let full_src = format!("{}\n{}", goldilocks_src, tip5_src);

        let module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("tip5"),
            source: wgpu::ShaderSource::Wgsl(full_src.into()),
        });

        let pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: Some("tip5_hash_rows"),
            layout: None,
            module: &module,
            entry_point: Some("hash_rows"),
            compilation_options: Default::default(),
            cache: None,
        });

        // Upload Tip5 constants
        let constants = Tip5Constants::load();

        let lookup_buf = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("tip5_lookup"),
            contents: bytemuck::cast_slice(&constants.lookup_table),
            usage: wgpu::BufferUsages::STORAGE,
        });

        let mds_buf = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("tip5_mds"),
            contents: bytemuck::cast_slice(&constants.mds_column),
            usage: wgpu::BufferUsages::STORAGE,
        });

        let rc_buf = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("tip5_round_constants"),
            contents: bytemuck::cast_slice(&constants.round_constants),
            usage: wgpu::BufferUsages::STORAGE,
        });

        WgpuTip5Accelerator {
            device,
            queue,
            pipeline,
            lookup_buf,
            mds_buf,
            rc_buf,
        }
    }
}

impl GpuAccelerator for WgpuTip5Accelerator {
    fn name(&self) -> &str {
        "wgpu-tip5"
    }

    fn hash_varlen_batch(&self, inputs: &[&[BFieldElement]]) -> Vec<Digest> {
        if inputs.is_empty() {
            return vec![];
        }

        // All rows in a single proving call have the same length (LDE table rows).
        // Verify this assumption and use uniform row length for GPU dispatch.
        let row_len = inputs[0].len();
        let uniform = inputs.iter().all(|r| r.len() == row_len);

        if !uniform || row_len == 0 {
            // Fall back to CPU for non-uniform or empty rows.
            return inputs
                .iter()
                .map(|input| Tip5::hash_varlen(input))
                .collect();
        }

        let num_rows = inputs.len() as u32;

        // Flatten input: convert BFieldElement → Montgomery u64 → [u32; 2]
        let input_data: Vec<[u32; 2]> = inputs
            .iter()
            .flat_map(|row| {
                row.iter().map(|bfe| {
                    let raw = bfe.raw_u64();
                    [raw as u32, (raw >> 32) as u32]
                })
            })
            .collect();

        // Create input buffer
        let input_buf = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("tip5_input"),
                contents: bytemuck::cast_slice(&input_data),
                usage: wgpu::BufferUsages::STORAGE,
            });

        // Create output buffer (num_rows * DIGEST_LEN elements)
        let output_size = (num_rows as usize * DIGEST_LEN * 8) as u64;
        let output_buf = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("tip5_output"),
            size: output_size,
            usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC,
            mapped_at_creation: false,
        });

        // Uniform params: num_rows, row_len, pad, pad
        let params = [num_rows, row_len as u32, 0u32, 0u32];
        let params_buf = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("tip5_params"),
                contents: bytemuck::cast_slice(&params),
                usage: wgpu::BufferUsages::UNIFORM,
            });

        // Create bind group
        let bind_group_layout = self.pipeline.get_bind_group_layout(0);
        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("tip5_bind_group"),
            layout: &bind_group_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: self.lookup_buf.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: self.mds_buf.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 2,
                    resource: self.rc_buf.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 3,
                    resource: input_buf.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 4,
                    resource: output_buf.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 5,
                    resource: params_buf.as_entire_binding(),
                },
            ],
        });

        // Dispatch compute shader
        let workgroups = (num_rows + WORKGROUP_SIZE - 1) / WORKGROUP_SIZE;
        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("tip5_encoder"),
            });
        {
            let mut pass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor {
                label: Some("tip5_pass"),
                timestamp_writes: None,
            });
            pass.set_pipeline(&self.pipeline);
            pass.set_bind_group(0, &bind_group, &[]);
            pass.dispatch_workgroups(workgroups, 1, 1);
        }

        // Copy output to staging buffer for CPU readback
        let staging_buf = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("tip5_staging"),
            size: output_size,
            usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });
        encoder.copy_buffer_to_buffer(&output_buf, 0, &staging_buf, 0, output_size);

        self.queue.submit(std::iter::once(encoder.finish()));

        // Map staging buffer and read results
        let slice = staging_buf.slice(..);
        let (tx, rx) = std::sync::mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |result| {
            tx.send(result).unwrap();
        });
        self.device.poll(wgpu::Maintain::Wait);
        rx.recv()
            .expect("GPU readback channel closed")
            .expect("GPU readback failed");

        let data = slice.get_mapped_range();
        let output_pairs: &[[u32; 2]] = bytemuck::cast_slice(&data);

        // Convert GPU output (Montgomery form) to Digest values
        let digests: Vec<Digest> = (0..num_rows as usize)
            .map(|i| {
                let base = i * DIGEST_LEN;
                let mut elements = [BFieldElement::new(0); DIGEST_LEN];
                for j in 0..DIGEST_LEN {
                    let [lo, hi] = output_pairs[base + j];
                    let raw = (hi as u64) << 32 | lo as u64;
                    elements[j] = BFieldElement::from_raw_u64(raw);
                }
                Digest::new(elements)
            })
            .collect();

        drop(data);
        staging_buf.unmap();

        digests
    }
}
