#[cfg(test)]
use crate::neural::model::vocab::Vocab;
pub use trident::neural::data::pairs::*;

#[cfg(test)]
mod tests {
    use super::*;
    use trident::tir::TIROp;

    #[test]
    fn split_tir_by_function_basic() {
        let ops = vec![
            TIROp::Entry("main".into()),
            TIROp::Call("foo".into()),
            TIROp::Halt,
            TIROp::FnStart("foo".into()),
            TIROp::Push(1),
            TIROp::Push(2),
            TIROp::Add,
            TIROp::Return,
            TIROp::FnEnd,
            TIROp::FnStart("bar".into()),
            TIROp::Push(3),
            TIROp::Return,
            TIROp::FnEnd,
        ];
        let functions = split_tir_by_function(&ops);
        assert_eq!(functions.len(), 3); // __entry, foo, bar
        assert_eq!(functions[0].0, "__entry");
        assert_eq!(functions[1].0, "foo");
        assert_eq!(functions[2].0, "bar");
        // foo has FnStart + Push + Push + Add + Return + FnEnd = 6 ops
        assert_eq!(functions[1].1.len(), 6);
        // bar has FnStart + Push + Return + FnEnd = 4 ops
        assert_eq!(functions[2].1.len(), 4);
    }

    #[test]
    fn extract_pairs_basic() {
        let vocab = Vocab::new();
        let blocks = vec![(
            vec![TIROp::Push(1), TIROp::Push(2), TIROp::Add],
            vec!["push 1".into(), "push 2".into(), "add".into()],
            "test:0..3".into(),
            3u64,
        )];
        let pairs = extract_pairs(&blocks, &vocab);
        assert_eq!(pairs.len(), 1);
        assert_eq!(pairs[0].source_id, "test:0..3");
        assert_eq!(pairs[0].baseline_cost, 3);
        // Target should end with EOS (0)
        assert_eq!(*pairs[0].target_tokens.last().unwrap(), 0);
    }

    #[test]
    fn extract_pairs_skips_empty() {
        let vocab = Vocab::new();
        let blocks: Vec<(Vec<TIROp>, Vec<String>, String, u64)> = vec![
            (vec![], vec!["push 1".into()], "empty_tir".into(), 0),
            (vec![TIROp::Push(1)], vec![], "empty_tasm".into(), 0),
        ];
        let pairs = extract_pairs(&blocks, &vocab);
        assert_eq!(pairs.len(), 0);
    }

    #[test]
    fn train_holdout_split_works() {
        let vocab = Vocab::new();
        let blocks: Vec<_> = (0..10)
            .map(|i| {
                (
                    vec![TIROp::Push(i as u64)],
                    vec![format!("push {}", i)],
                    format!("block:{}", i),
                    1u64,
                )
            })
            .collect();
        let pairs = extract_pairs(&blocks, &vocab);
        let (train, holdout) = train_holdout_split(pairs, 3);
        assert_eq!(train.len(), 7);
        assert_eq!(holdout.len(), 3);
    }
}
