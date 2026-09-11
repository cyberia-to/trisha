//! Triton adapter for Trident's shared neural compilation harness.
mod augment_target;
pub mod checkpoint;
pub mod data;
pub mod inference;
pub mod model;
pub mod target;
pub mod training;
use target::TritonTarget;
use trident::tir::TIROp;
pub struct CompileResult {
    pub tasm_lines: Vec<String>,
    pub cost: u64,
    pub valid_count: usize,
    pub total_count: usize,
    pub neural: bool,
}
fn result(r: trident::neural::CompileResult) -> CompileResult {
    CompileResult {
        tasm_lines: r.assembly,
        cost: r.cost,
        valid_count: r.valid_count,
        total_count: r.total_count,
        neural: r.neural,
    }
}
pub fn compile(tir_ops: &[TIROp], baseline_tasm: &[String]) -> Result<CompileResult, String> {
    trident::neural::compile(&TritonTarget::default(), tir_ops, baseline_tasm).map(result)
}
pub fn compile_with_device<B: burn::prelude::Backend>(
    tir_ops: &[TIROp],
    baseline_tasm: &[String],
    device: &B::Device,
) -> Result<CompileResult, String> {
    trident::neural::compile_with_device::<B>(
        &TritonTarget::default(),
        tir_ops,
        baseline_tasm,
        device,
    )
    .map(result)
}
pub fn load_model<B: burn::prelude::Backend>(
    device: &B::Device,
) -> Option<model::composite::NeuralCompilerV2<B>> {
    trident::neural::load_model(&TritonTarget::default(), device)
}
pub fn compile_with_model<B: burn::prelude::Backend>(
    tir_ops: &[TIROp],
    baseline_tasm: &[String],
    model: &model::composite::NeuralCompilerV2<B>,
    device: &B::Device,
) -> Result<CompileResult, String> {
    trident::neural::compile_with_model(
        &TritonTarget::default(),
        tir_ops,
        baseline_tasm,
        model,
        device,
    )
    .map(result)
}
