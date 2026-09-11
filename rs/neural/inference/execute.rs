use crate::neural::model::vocab::Vocab;
pub struct RankedResult {
    pub tasm_lines: Vec<String>,
    pub cost: u64,
    pub valid_count: usize,
    pub total_count: usize,
}
pub fn validate_and_rank(
    candidates: &[Vec<u32>],
    vocab: &Vocab,
    baseline_tasm: &[String],
    seed: u64,
) -> Option<RankedResult> {
    let target = crate::neural::target::TritonTarget::with_vocabulary(vocab);
    trident::neural::inference::execute::validate_and_rank(candidates, &target, baseline_tasm, seed)
        .map(|r| RankedResult {
            tasm_lines: r.assembly,
            cost: r.cost,
            valid_count: r.valid_count,
            total_count: r.total_count,
        })
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validate_empty_candidates() {
        let vocab = Vocab::new();
        let result = validate_and_rank(&[], &vocab, &["push 1".into()], 42);
        assert!(result.is_none());
    }

    #[test]
    fn validate_empty_baseline() {
        let vocab = Vocab::new();
        let result = validate_and_rank(&[vec![3, 0]], &vocab, &[], 42);
        assert!(result.is_none());
    }

    #[test]
    fn validate_equivalent_candidate() {
        let vocab = Vocab::new();
        // Baseline: push 1, push 2, add → result 3
        let baseline: Vec<String> = vec!["push 1".into(), "push 2".into(), "add".into()];
        // Candidate: push 3 (token 5) → same result
        let candidates = vec![vec![5]]; // push 3
        let result = validate_and_rank(&candidates, &vocab, &baseline, 42);
        assert!(result.is_some());
        let r = result.unwrap();
        assert_eq!(r.valid_count, 1);
        assert_eq!(r.tasm_lines, vec!["push 3"]);
    }

    #[test]
    fn validate_picks_cheapest() {
        let vocab = Vocab::new();
        // Baseline: push 3
        let baseline: Vec<String> = vec!["push 3".into()];
        // Two equivalent candidates:
        //   push 3 (1 instruction) — token 5
        //   push 3, nop (2 instructions) — tokens 5, 96
        let candidates = vec![
            vec![5, 96], // push 3, nop
            vec![5],     // push 3
        ];
        let result = validate_and_rank(&candidates, &vocab, &baseline, 42);
        assert!(result.is_some());
        let r = result.unwrap();
        assert_eq!(r.valid_count, 2);
        // Cheapest should be the 1-instruction version
        assert_eq!(r.tasm_lines, vec!["push 3"]);
    }

    #[test]
    fn validate_rejects_invalid() {
        let vocab = Vocab::new();
        let baseline: Vec<String> = vec!["push 1".into(), "push 2".into(), "add".into()];
        // Candidate: push 4 (wrong result)
        let candidates = vec![vec![6]]; // push 4
        let result = validate_and_rank(&candidates, &vocab, &baseline, 42);
        assert!(result.is_none());
    }
}
