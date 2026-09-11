use burn::module::Module;
use burn::prelude::*;
use std::path::PathBuf;
pub use trident::neural::checkpoint::{CheckpointTag, TrainingStage};
use trident::neural::Target;
fn directory() -> PathBuf {
    crate::neural::target::TritonTarget::default().checkpoint_dir()
}
pub fn save_checkpoint<B: Backend, M: Module<B> + Clone>(
    model: &M,
    tag: CheckpointTag,
    _device: &B::Device,
) -> Result<PathBuf, String> {
    trident::neural::checkpoint::save_checkpoint(&directory(), model, tag, _device)
}
pub fn load_checkpoint<B: Backend, M: Module<B>>(
    model: M,
    tag: CheckpointTag,
    device: &B::Device,
) -> Result<Option<M>, String> {
    trident::neural::checkpoint::load_checkpoint(&directory(), model, tag, device)
}
pub fn available_checkpoints() -> Vec<(CheckpointTag, PathBuf)> {
    trident::neural::checkpoint::available_checkpoints(&directory())
}
pub fn detect_stage(replay_count: usize, replay_threshold: usize) -> TrainingStage {
    trident::neural::checkpoint::detect_stage(&directory(), replay_count, replay_threshold)
}
pub fn promote_to_production(source: CheckpointTag) -> Result<(), String> {
    trident::neural::checkpoint::promote_to_production(&directory(), source)
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detect_stage_returns_valid_stage() {
        // detect_stage examines real filesystem; just verify it returns a valid stage
        let stage = detect_stage(0, 100);
        match stage {
            TrainingStage::Stage1Supervised
            | TrainingStage::Stage2GFlowNet
            | TrainingStage::Stage3Online => {} // all valid
        }
    }
}
