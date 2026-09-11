//! Triton vocabulary, abstract execution and cost adapter for Trident's model.
use super::model::{grammar::StackStateMachine, vocab::Vocab};
use trident::neural::{GrammarState, Target, Vocabulary};

#[derive(Default)]
pub struct TritonTarget {
    vocab: Vocab,
}

impl TritonTarget {
    pub fn with_vocabulary(vocab: &Vocab) -> Self {
        Self {
            vocab: vocab.clone(),
        }
    }
}

impl Vocabulary for Vocab {
    fn size(&self) -> usize {
        Vocab::size(self)
    }
    fn encode(&self, line: &str) -> Option<u32> {
        Vocab::encode(self, line)
    }
    fn decode(&self, token: u32) -> Option<&str> {
        Vocab::decode(self, token)
    }
}

impl GrammarState for StackStateMachine {
    fn step(&mut self, token: u32) {
        StackStateMachine::step(self, token)
    }
    fn valid_mask(&self) -> Vec<f32> {
        StackStateMachine::valid_mask(self)
    }
    fn type_encoding(&self) -> Vec<f32> {
        StackStateMachine::type_encoding(self)
    }
    fn depth_for_embedding(&self, max_depth: usize) -> u32 {
        StackStateMachine::depth_for_embedding(self, max_depth)
    }
}

impl Target for TritonTarget {
    fn vocabulary(&self) -> &dyn Vocabulary {
        &self.vocab
    }
    fn grammar(&self, initial_depth: i32) -> Box<dyn GrammarState> {
        Box::new(StackStateMachine::new(initial_depth))
    }
    fn verify_block(&self, baseline: &[String], candidate: &[String], seed: u64) -> bool {
        crate::cost::stack_verifier::verify_equivalent(baseline, candidate, seed)
    }
    fn cost(&self, assembly: &[String]) -> u64 {
        let lines: Vec<_> = assembly.iter().map(String::as_str).collect();
        crate::cost::scorer::profile_tasm(&lines).cost()
    }
    fn checkpoint_dir(&self) -> std::path::PathBuf {
        std::path::PathBuf::from("model/triton/v2")
    }
    fn augment(
        &self,
        assembly: &[String],
        seed: u64,
        variants: usize,
        max_swaps: usize,
    ) -> Vec<Vec<String>> {
        super::augment_target::candidates(assembly, seed, variants, max_swaps)
    }
}
