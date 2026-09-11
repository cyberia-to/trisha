use crate::neural::data::pairs::TrainingPair;
use crate::neural::model::vocab::Vocab;
pub use trident::neural::training::augment::AugmentConfig;
pub fn augment_pairs(
    pairs: &[TrainingPair],
    vocab: &Vocab,
    config: &AugmentConfig,
) -> Vec<TrainingPair> {
    trident::neural::training::augment::augment_pairs(
        pairs,
        &crate::neural::target::TritonTarget::with_vocabulary(vocab),
        config,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::neural::data::tir_graph::TirGraph;
    use trident::tir::TIROp;
    #[test]
    fn augment_pairs_multiplies_dataset() {
        let vocab = Vocab::new();
        let graph = TirGraph::from_tir_ops(&[TIROp::Push(1), TIROp::Push(2), TIROp::Add]);
        let tokens = vocab.encode_sequence(&[
            "push 1".to_string(),
            "push 2".to_string(),
            "add".to_string(),
        ]);

        let pairs = vec![TrainingPair {
            graph,
            target_tokens: tokens,
            source_id: "test:0".into(),
            baseline_cost: 3,
        }];

        let config = AugmentConfig {
            tir_reorder_variants: 2,
            assembly_walk_variants: 3,
            max_swap_attempts: 5,
            seed: 42,
        };

        let augmented = augment_pairs(&pairs, &vocab, &config);
        assert!(
            augmented.len() > 1,
            "augmentation should produce more than original",
        );
    }
}
