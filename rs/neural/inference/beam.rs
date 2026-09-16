use crate::neural::model::{decoder::StackAwareDecoder, encoder::GnnEncoder};
use burn::prelude::*;
pub use trident::neural::inference::beam::{BeamConfig, BeamResult};
pub fn beam_search<B: Backend>(
    encoder: &GnnEncoder<B>,
    decoder: &StackAwareDecoder<B>,
    node_features: Tensor<B, 2>,
    edge_src: Tensor<B, 1, Int>,
    edge_dst: Tensor<B, 1, Int>,
    edge_types: Tensor<B, 1, Int>,
    config: &BeamConfig,
    initial_stack_depth: i32,
    device: &B::Device,
) -> BeamResult {
    trident::neural::inference::beam::beam_search(
        &crate::neural::target::TritonTarget::default(),
        encoder,
        decoder,
        node_features,
        edge_src,
        edge_dst,
        edge_types,
        config,
        initial_stack_depth,
        device,
    )
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::neural::model::decoder::DecoderConfig;
    use crate::neural::model::encoder::GnnEncoderConfig;
    use burn::backend::NdArray;

    type B = NdArray;

    #[test]
    fn beam_search_produces_k_sequences() {
        let device = Default::default();

        // Small model for testing
        let encoder = GnnEncoderConfig::new()
            .with_d_model(32)
            .with_d_edge(8)
            .with_num_layers(1)
            .init::<B>(&device);

        let decoder = DecoderConfig {
            vocab_size: crate::neural::model::vocab::VOCAB_SIZE,
            d_model: 32,
            num_layers: 1,
            n_heads: 4,
            d_ff: 64,
            max_seq: 64,
            max_stack_depth: 65,
            type_window: 8,
            dropout: 0.0,
        }
        .init::<B>(&device);

        // Tiny graph: 3 nodes, 2 edges
        let node_features = Tensor::<B, 2>::zeros([3, 59], &device);
        let edge_src = Tensor::<B, 1, Int>::from_data(TensorData::new(vec![0i32, 1], [2]), &device);
        let edge_dst = Tensor::<B, 1, Int>::from_data(TensorData::new(vec![1i32, 2], [2]), &device);
        let edge_types =
            Tensor::<B, 1, Int>::from_data(TensorData::new(vec![0i32, 1], [2]), &device);

        let config = BeamConfig {
            k: 4, // Small K for test speed
            max_steps: 5,
            min_tokens: 1,
            ..Default::default()
        };

        let result = beam_search(
            &encoder,
            &decoder,
            node_features,
            edge_src,
            edge_dst,
            edge_types,
            &config,
            0,
            &device,
        );

        assert_eq!(result.sequences.len(), 4);
        assert_eq!(result.log_probs.len(), 4);
        // Log probs should be sorted descending
        for i in 1..result.log_probs.len() {
            assert!(
                result.log_probs[i] <= result.log_probs[i - 1],
                "log_probs not sorted: {} > {}",
                result.log_probs[i],
                result.log_probs[i - 1]
            );
        }
    }
}
