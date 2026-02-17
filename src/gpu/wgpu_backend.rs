//! wgpu backend for GPU-accelerated operations.
//!
//! Uses custom WGSL shaders for Goldilocks field arithmetic.
//! Auto-selects the best native API: Metal (macOS), Vulkan (Linux/Windows),
//! DX12 (Windows). Single codebase for all platforms.
//!
//! Currently delegates full prove/verify to CPU via triton-vm, but
//! provides the GPU infrastructure for future acceleration of NTT,
//! Poseidon2 Merkle trees, and FRI evaluation.

use wgpu;

use triton_vm::prelude::*;
use triton_vm::proof::Proof;

use super::GpuBackend;

/// wgpu-based GPU backend.
#[allow(dead_code)]
pub struct WgpuBackend {
    device: wgpu::Device,
    queue: wgpu::Queue,
    adapter_name: String,
    backend_type: String,
    // Pipelines compiled at init from WGSL shaders
    _ntt_pipeline: wgpu::ComputePipeline,
    _poseidon2_pipeline: wgpu::ComputePipeline,
    _fri_pipeline: wgpu::ComputePipeline,
}

impl WgpuBackend {
    /// Try to create a wgpu backend. Returns None if no GPU is available.
    pub fn try_new() -> Option<Self> {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
            backends: wgpu::Backends::all(),
            ..Default::default()
        });

        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            compatible_surface: None,
            force_fallback_adapter: false,
        }))?;

        let adapter_name = adapter.get_info().name.clone();
        let backend_type = format!("{:?}", adapter.get_info().backend);

        let (device, queue) = pollster::block_on(adapter.request_device(
            &wgpu::DeviceDescriptor {
                label: Some("trisha-gpu"),
                required_features: wgpu::Features::empty(),
                required_limits: wgpu::Limits::default(),
                memory_hints: wgpu::MemoryHints::Performance,
            },
            None,
        ))
        .ok()?;

        // Compile shaders
        let goldilocks_src = include_str!("shaders/goldilocks.wgsl");
        let ntt_src = include_str!("shaders/ntt.wgsl");
        let poseidon2_src = include_str!("shaders/poseidon2.wgsl");
        let fri_src = include_str!("shaders/fri.wgsl");

        // Prepend goldilocks to each shader that depends on it
        let ntt_full = format!("{}\n{}", goldilocks_src, ntt_src);
        let poseidon2_full = format!("{}\n{}", goldilocks_src, poseidon2_src);
        let fri_full = format!("{}\n{}", goldilocks_src, fri_src);

        let ntt_module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("ntt"),
            source: wgpu::ShaderSource::Wgsl(ntt_full.into()),
        });

        let poseidon2_module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("poseidon2"),
            source: wgpu::ShaderSource::Wgsl(poseidon2_full.into()),
        });

        let fri_module = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("fri"),
            source: wgpu::ShaderSource::Wgsl(fri_full.into()),
        });

        let ntt_pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: Some("ntt_butterfly"),
            layout: None,
            module: &ntt_module,
            entry_point: Some("ntt_butterfly"),
            compilation_options: Default::default(),
            cache: None,
        });

        let poseidon2_pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: Some("hash_merkle_node"),
            layout: None,
            module: &poseidon2_module,
            entry_point: Some("hash_merkle_node"),
            compilation_options: Default::default(),
            cache: None,
        });

        let fri_pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: Some("fri_fold"),
            layout: None,
            module: &fri_module,
            entry_point: Some("fri_fold"),
            compilation_options: Default::default(),
            cache: None,
        });

        Some(WgpuBackend {
            device,
            queue,
            adapter_name,
            backend_type,
            _ntt_pipeline: ntt_pipeline,
            _poseidon2_pipeline: poseidon2_pipeline,
            _fri_pipeline: fri_pipeline,
        })
    }
}

impl GpuBackend for WgpuBackend {
    fn name(&self) -> &str {
        // Return a static str — use adapter info for display elsewhere
        "wgpu"
    }

    fn trace(
        &self,
        program: &Program,
        public_input: PublicInput,
        non_determinism: NonDeterminism,
    ) -> Result<(Vec<BFieldElement>, u64), String> {
        // GPU-accelerated trace generation is a future optimization.
        // Currently delegates to CPU for correctness.
        let output = VM::run(program.clone(), public_input, non_determinism)
            .map_err(|e| format!("execution error: {}", e))?;
        Ok((output, 0))
    }

    fn prove(
        &self,
        program: &Program,
        public_input: PublicInput,
        non_determinism: NonDeterminism,
    ) -> Result<(triton_vm::proof::Claim, Proof), String> {
        // Full proving pipeline integration pending.
        // NTT and Poseidon2 shaders are compiled and ready;
        // integration into triton-vm's proving flow requires
        // intercepting the NTT and Merkle tree construction calls.
        let (_stark, claim, proof) =
            triton_vm::prove_program(program.clone(), public_input, non_determinism)
                .map_err(|e| format!("proving error: {}", e))?;
        Ok((claim, proof))
    }

    fn verify(&self, claim: &triton_vm::proof::Claim, proof: &Proof) -> Result<bool, String> {
        let stark = Stark::default();
        Ok(triton_vm::verify(stark, claim, proof))
    }

    fn verify_batch(&self, jobs: &[(triton_vm::proof::Claim, Proof)]) -> Vec<Result<bool, String>> {
        // Batch verification on GPU pending FRI shader integration.
        // Currently verifies sequentially on CPU.
        jobs.iter()
            .map(|(claim, proof)| self.verify(claim, proof))
            .collect()
    }
}

impl WgpuBackend {
    /// Display adapter info for diagnostics.
    pub fn adapter_info(&self) -> String {
        format!("{} ({})", self.adapter_name, self.backend_type)
    }
}

/// Create a standalone Tip5 GPU accelerator for triton-vm's prover.
///
/// Requests its own wgpu device so it can be registered globally via
/// `triton_vm::gpu::set_gpu_accelerator` without sharing state with
/// the main WgpuBackend.
#[cfg(feature = "gpu")]
pub fn create_tip5_accelerator() -> Option<super::tip5_accel::WgpuTip5Accelerator> {
    let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
        backends: wgpu::Backends::all(),
        ..Default::default()
    });

    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::HighPerformance,
        compatible_surface: None,
        force_fallback_adapter: false,
    }))?;

    let (device, queue) = pollster::block_on(adapter.request_device(
        &wgpu::DeviceDescriptor {
            label: Some("trisha-tip5"),
            required_features: wgpu::Features::empty(),
            required_limits: wgpu::Limits::default(),
            memory_hints: wgpu::MemoryHints::Performance,
        },
        None,
    ))
    .ok()?;

    Some(super::tip5_accel::WgpuTip5Accelerator::new(device, queue))
}
