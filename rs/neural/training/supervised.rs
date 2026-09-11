use crate::neural::data::pairs::TrainingPair;
use crate::neural::model::composite::NeuralCompilerV2;
use burn::optim::Optimizer;
pub use trident::neural::training::supervised::{
    cosine_lr, create_optimizer, graph_to_edges, graph_to_features, EpochResult, SupervisedConfig,
};
pub fn train_epoch<B: burn::tensor::backend::AutodiffBackend>(
    model: NeuralCompilerV2<B>,
    pairs: &[TrainingPair],
    optimizer: &mut impl Optimizer<NeuralCompilerV2<B>, B>,
    lr: f64,
    device: &B::Device,
) -> (NeuralCompilerV2<B>, EpochResult) {
    trident::neural::training::supervised::train_epoch(
        &crate::neural::target::TritonTarget::default(),
        model,
        pairs,
        optimizer,
        lr,
        device,
    )
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::neural::data::pairs::extract_pairs;
    use crate::neural::model::composite::NeuralCompilerConfig;
    use crate::neural::model::vocab::Vocab;
    use burn::backend::Autodiff;
    use burn::backend::NdArray;
    use trident::tir::TIROp;

    type B = Autodiff<NdArray>;

    #[test]
    fn train_epoch_runs() {
        let device = Default::default();

        let config = NeuralCompilerConfig {
            vocab_size: crate::neural::model::vocab::VOCAB_SIZE,
            d_model: 32,
            d_edge: 8,
            gnn_layers: 1,
            decoder_layers: 1,
            n_heads: 4,
            d_ff: 64,
            max_seq: 32,
            dropout: 0.0,
        };
        let model = config.init::<B>(&device);

        let vocab = Vocab::new();
        let blocks = vec![(
            vec![TIROp::Push(1), TIROp::Push(2), TIROp::Add],
            vec!["push 1".into(), "push 2".into(), "add".into()],
            "test:0..3".into(),
            3u64,
        )];
        let pairs = extract_pairs(&blocks, &vocab);

        let supervised_config = SupervisedConfig::default();
        let mut optimizer = create_optimizer::<B>(&supervised_config);

        let lr = supervised_config.lr;
        let (model, result) = train_epoch(model, &pairs, &mut optimizer, lr, &device);
        assert_eq!(result.num_pairs, 1);
        assert!(result.avg_loss > 0.0, "loss should be positive");
        assert!(result.avg_loss.is_finite(), "loss should be finite");

        // Train a second epoch — loss should change
        let (_model2, result2) = train_epoch(model, &pairs, &mut optimizer, lr, &device);
        assert!(result2.avg_loss.is_finite());
    }
}
