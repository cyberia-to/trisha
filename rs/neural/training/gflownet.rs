use crate::neural::model::{composite::NeuralCompilerV2, vocab::Vocab};
use burn::prelude::*;
pub use trident::neural::training::gflownet::{
    compute_reward, compute_shaped_reward, tb_loss, temperature_at_step, GFlowNetConfig,
};
pub fn sample_sequence<B: Backend>(
    model: &NeuralCompilerV2<B>,
    graph: &crate::neural::data::tir_graph::TirGraph,
    tau: f32,
    config: &GFlowNetConfig,
    device: &B::Device,
) -> (Vec<u32>, f32, Option<usize>) {
    trident::neural::training::gflownet::sample_sequence(
        &crate::neural::target::TritonTarget::default(),
        model,
        graph,
        tau,
        config,
        device,
    )
}
pub fn gflownet_step<B: burn::tensor::backend::AutodiffBackend>(
    model: &NeuralCompilerV2<B>,
    graph: &crate::neural::data::tir_graph::TirGraph,
    baseline_tasm: &[String],
    compiler_cycles: u64,
    log_z: Tensor<B, 1>,
    step: usize,
    config: &GFlowNetConfig,
    vocab: &Vocab,
    device: &B::Device,
) -> (Tensor<B, 1>, f32, bool) {
    trident::neural::training::gflownet::gflownet_step(
        model,
        graph,
        baseline_tasm,
        compiler_cycles,
        log_z,
        step,
        config,
        &crate::neural::target::TritonTarget::with_vocabulary(vocab),
        device,
    )
}
