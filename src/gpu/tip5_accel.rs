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
use twenty_first::math::traits::PrimitiveRootOfUnity;
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

/// wgpu-based GPU accelerator implementing triton-vm's GpuAccelerator.
///
/// Accelerates:
/// - Tip5 batch hashing (Merkle tree leaf construction)
/// - NTT/iNTT (polynomial interpolation during proving)
pub struct WgpuTip5Accelerator {
    device: wgpu::Device,
    queue: wgpu::Queue,
    // Tip5 pipeline + constants
    tip5_pipeline: wgpu::ComputePipeline,
    lookup_buf: wgpu::Buffer,
    mds_buf: wgpu::Buffer,
    rc_buf: wgpu::Buffer,
    // NTT pipelines
    ntt_butterfly_pipeline: wgpu::ComputePipeline,
    ntt_normalize_pipeline: wgpu::ComputePipeline,
}

impl WgpuTip5Accelerator {
    /// Create a new accelerator using an existing wgpu device and queue.
    pub fn new(device: wgpu::Device, queue: wgpu::Queue) -> Self {
        let goldilocks_src = include_str!("shaders/goldilocks.wgsl");

        // Compile Tip5 shader
        let tip5_src = include_str!("shaders/tip5.wgsl");
        let tip5_full = format!("{}\n{}", goldilocks_src, tip5_src);
        let tip5_module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("tip5"),
            source: wgpu::ShaderSource::Wgsl(tip5_full.into()),
        });
        let tip5_pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: Some("tip5_hash_rows"),
            layout: None,
            module: &tip5_module,
            entry_point: Some("hash_rows"),
            compilation_options: Default::default(),
            cache: None,
        });

        // Compile NTT shader
        let ntt_src = include_str!("shaders/ntt.wgsl");
        let ntt_full = format!("{}\n{}", goldilocks_src, ntt_src);
        let ntt_module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("ntt"),
            source: wgpu::ShaderSource::Wgsl(ntt_full.into()),
        });
        let ntt_butterfly_pipeline =
            device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
                label: Some("ntt_butterfly"),
                layout: None,
                module: &ntt_module,
                entry_point: Some("ntt_butterfly"),
                compilation_options: Default::default(),
                cache: None,
            });
        let ntt_normalize_pipeline =
            device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
                label: Some("ntt_normalize"),
                layout: None,
                module: &ntt_module,
                entry_point: Some("ntt_normalize"),
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
            tip5_pipeline,
            lookup_buf,
            mds_buf,
            rc_buf,
            ntt_butterfly_pipeline,
            ntt_normalize_pipeline,
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
        let bind_group_layout = self.tip5_pipeline.get_bind_group_layout(0);
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
            pass.set_pipeline(&self.tip5_pipeline);
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

    fn intt_bfe(&self, column: &mut [BFieldElement]) {
        let n = column.len();
        if n <= 1 || !n.is_power_of_two() {
            // Fallback to CPU for non-power-of-2 or trivial sizes
            twenty_first::math::ntt::intt(column);
            return;
        }

        // Small transforms: CPU is faster due to GPU dispatch overhead
        if n < 1024 {
            twenty_first::math::ntt::intt(column);
            return;
        }

        let n_u32 = n as u32;
        let log_n = n.trailing_zeros();

        // Compute inverse twiddle factors: omega_inv = primitive_root^(-1)
        let omega = BFieldElement::primitive_root_of_unity(n as u64).unwrap();
        let omega_inv = omega.inverse();

        // Build flat twiddle factor array: for each butterfly pair,
        // tw[k] = omega_inv^k for k = 0..n/2
        let mut twiddles = vec![[0u32; 2]; n / 2];
        let mut w = BFieldElement::new(1); // = omega_inv^0
        for tw in twiddles.iter_mut() {
            let raw = w.raw_u64();
            *tw = [raw as u32, (raw >> 32) as u32];
            w *= omega_inv;
        }

        // Bit-reversal permutation (must happen before butterfly passes)
        let log_n_u32 = log_n;
        for k in 0..n {
            let rev_k = (k as u32).reverse_bits() >> (32 - log_n_u32);
            let rev_k = rev_k as usize;
            if k < rev_k {
                column.swap(k, rev_k);
            }
        }

        // Upload column data (Montgomery form)
        let col_data: Vec<[u32; 2]> = column
            .iter()
            .map(|bfe| {
                let raw = bfe.raw_u64();
                [raw as u32, (raw >> 32) as u32]
            })
            .collect();

        let data_buf = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("ntt_data"),
                contents: bytemuck::cast_slice(&col_data),
                usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC,
            });

        let twiddle_buf = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("ntt_twiddles"),
                contents: bytemuck::cast_slice(&twiddles),
                usage: wgpu::BufferUsages::STORAGE,
            });

        // Run log2(n) butterfly passes
        for layer in 0..log_n {
            let params = [n_u32, layer, 0u32, 0u32];
            let params_buf = self
                .device
                .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("ntt_params"),
                    contents: bytemuck::cast_slice(&params),
                    usage: wgpu::BufferUsages::UNIFORM,
                });

            let bind_group_layout = self.ntt_butterfly_pipeline.get_bind_group_layout(0);
            let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("ntt_bg"),
                layout: &bind_group_layout,
                entries: &[
                    wgpu::BindGroupEntry {
                        binding: 0,
                        resource: data_buf.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 1,
                        resource: twiddle_buf.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 2,
                        resource: params_buf.as_entire_binding(),
                    },
                ],
            });

            let n_butterflies = n_u32 / 2;
            let workgroups = (n_butterflies + WORKGROUP_SIZE - 1) / WORKGROUP_SIZE;

            let mut encoder = self
                .device
                .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                    label: Some("ntt_encoder"),
                });
            {
                let mut pass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor {
                    label: Some("ntt_butterfly_pass"),
                    timestamp_writes: None,
                });
                pass.set_pipeline(&self.ntt_butterfly_pipeline);
                pass.set_bind_group(0, &bind_group, &[]);
                pass.dispatch_workgroups(workgroups, 1, 1);
            }
            self.queue.submit(std::iter::once(encoder.finish()));
            self.device.poll(wgpu::Maintain::Wait);
        }

        // Normalization pass: multiply all elements by n_inv
        {
            let n_inv = BFieldElement::new(n as u64).inverse();
            let n_inv_raw = n_inv.raw_u64();
            // Store n_inv as twiddles[0] for the normalize kernel
            let norm_twiddle = [[n_inv_raw as u32, (n_inv_raw >> 32) as u32]];
            let norm_tw_buf = self
                .device
                .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("ntt_norm_tw"),
                    contents: bytemuck::cast_slice(&norm_twiddle),
                    usage: wgpu::BufferUsages::STORAGE,
                });

            let params = [n_u32, 0u32, 0u32, 0u32];
            let params_buf = self
                .device
                .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("ntt_norm_params"),
                    contents: bytemuck::cast_slice(&params),
                    usage: wgpu::BufferUsages::UNIFORM,
                });

            let bind_group_layout = self.ntt_normalize_pipeline.get_bind_group_layout(0);
            let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("ntt_norm_bg"),
                layout: &bind_group_layout,
                entries: &[
                    wgpu::BindGroupEntry {
                        binding: 0,
                        resource: data_buf.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 1,
                        resource: norm_tw_buf.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 2,
                        resource: params_buf.as_entire_binding(),
                    },
                ],
            });

            let workgroups = (n_u32 + WORKGROUP_SIZE - 1) / WORKGROUP_SIZE;
            let mut encoder = self
                .device
                .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                    label: Some("ntt_norm_encoder"),
                });
            {
                let mut pass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor {
                    label: Some("ntt_normalize_pass"),
                    timestamp_writes: None,
                });
                pass.set_pipeline(&self.ntt_normalize_pipeline);
                pass.set_bind_group(0, &bind_group, &[]);
                pass.dispatch_workgroups(workgroups, 1, 1);
            }
            self.queue.submit(std::iter::once(encoder.finish()));
        }

        // Read back results
        let buf_size = (n * 8) as u64;
        let staging_buf = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("ntt_staging"),
            size: buf_size,
            usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });

        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("ntt_readback"),
            });
        encoder.copy_buffer_to_buffer(&data_buf, 0, &staging_buf, 0, buf_size);
        self.queue.submit(std::iter::once(encoder.finish()));

        let slice = staging_buf.slice(..);
        let (tx, rx) = std::sync::mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |result| {
            tx.send(result).unwrap();
        });
        self.device.poll(wgpu::Maintain::Wait);
        rx.recv()
            .expect("NTT readback channel closed")
            .expect("NTT readback failed");

        let data = slice.get_mapped_range();
        let result_pairs: &[[u32; 2]] = bytemuck::cast_slice(&data);

        for (i, &[lo, hi]) in result_pairs.iter().enumerate() {
            let raw = (hi as u64) << 32 | lo as u64;
            column[i] = BFieldElement::from_raw_u64(raw);
        }

        drop(data);
        staging_buf.unmap();
    }
}
