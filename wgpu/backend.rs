//! wgpu device management and pipeline compilation.
//!
//! Provides the WgpuBackend (holds compiled WGSL pipelines) and the
//! create_tip5_accelerator helper that registers a GPU accelerator
//! with triton-vm's prover.

use wgpu;

/// Holds compiled WGSL compute pipelines for GPU operations.
///
/// Shaders are compiled at construction. The pipelines are scaffolded —
/// full integration into triton-vm's proving path is pending.
#[allow(dead_code)]
pub struct WgpuBackend {
    device: wgpu::Device,
    queue: wgpu::Queue,
    adapter_name: String,
    backend_type: String,
    _ntt_pipeline: wgpu::ComputePipeline,
    _poseidon2_pipeline: wgpu::ComputePipeline,
    _fri_pipeline: wgpu::ComputePipeline,
}

impl WgpuBackend {
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

        let goldilocks_src = include_str!("shaders/goldilocks.wgsl");
        let ntt_src = include_str!("shaders/ntt.wgsl");
        let poseidon2_src = include_str!("shaders/poseidon2.wgsl");
        let fri_src = include_str!("shaders/fri.wgsl");

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
            label: Some("fri_fold_round"),
            layout: None,
            module: &fri_module,
            entry_point: Some("fri_fold_round"),
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

    pub fn adapter_info(&self) -> String {
        format!("{} ({})", self.adapter_name, self.backend_type)
    }
}

/// Create a standalone Tip5 GPU accelerator for triton-vm's prover.
///
/// Requests its own wgpu device so it can be registered globally via
/// `triton_vm::gpu::set_gpu_accelerator` without sharing state with
/// the main WgpuBackend.
pub fn create_tip5_accelerator() -> Option<crate::accelerator::WgpuTip5Accelerator> {
    let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
        backends: wgpu::Backends::all(),
        ..Default::default()
    });

    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::HighPerformance,
        compatible_surface: None,
        force_fallback_adapter: false,
    }))?;

    let adapter_limits = adapter.limits();
    let mut required_limits = wgpu::Limits::default();
    required_limits.max_buffer_size = adapter_limits.max_buffer_size;
    required_limits.max_storage_buffer_binding_size =
        adapter_limits.max_storage_buffer_binding_size;

    let (device, queue) = pollster::block_on(adapter.request_device(
        &wgpu::DeviceDescriptor {
            label: Some("trisha-tip5"),
            required_features: wgpu::Features::empty(),
            required_limits,
            memory_hints: wgpu::MemoryHints::Performance,
        },
        None,
    ))
    .ok()?;

    Some(crate::accelerator::WgpuTip5Accelerator::new(device, queue))
}
