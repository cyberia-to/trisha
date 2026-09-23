//! Independent native-library vectors. Never executes either benchmark candidate.
use twenty_first::prelude::*;
fn main() {
    for (name, input) in [
        ("tip5_ascending", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
        ("tip5_descending", [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]),
        ("generation_17", [17, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        ("symmetric", [1, 2, 3, 4, 5, 0, 0, 0, 0, 0]),
    ] {
        let output = Tip5::hash_10(&input.map(BFieldElement::new));
        println!("{name}: {:?}", output.map(|x| x.value()));
    }
    let node = Digest::new([1, 2, 3, 4, 5].map(BFieldElement::new));
    let sibling = Digest::new([6, 7, 8, 9, 10].map(BFieldElement::new));
    println!(
        "merkle_even: {:?}",
        Tip5::hash_pair(node, sibling).values().map(|x| x.value())
    );
    println!(
        "merkle_odd: {:?}",
        Tip5::hash_pair(sibling, node).values().map(|x| x.value())
    );
    let inv = XFieldElement::new([2, 3, 4].map(BFieldElement::new)).inverse();
    println!("xfield_inverse: {:?}", inv.coefficients.map(|x| x.value()));
    let mut root = Digest::new([17, 0, 0, 0, 0].map(BFieldElement::new));
    let mut index = 5;
    for base in [1, 6, 11] {
        let sibling = Digest::new(std::array::from_fn(|i| BFieldElement::new(base + i as u64)));
        root = if index % 2 == 0 {
            Tip5::hash_pair(root, sibling)
        } else {
            Tip5::hash_pair(sibling, root)
        };
        index /= 2;
    }
    println!("timestamp_root: {:?}", root.values().map(|x| x.value()));
    for key in [18, 19] {
        let mut input = [BFieldElement::new(0); 10];
        input[0] = BFieldElement::new(key);
        println!("key{key}: {:?}", Tip5::hash_10(&input).map(|x| x.value()));
    }
}
