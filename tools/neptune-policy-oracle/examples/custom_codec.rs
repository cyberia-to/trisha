use neptune_consensus::transaction::{
    primitive_witness::SaltedUtxos,
    utxo::{Coin, Utxo},
};
use tasm_lib::triton_vm::prelude::*;
fn main() {
    let coin = Coin {
        type_script_hash: Digest::new([101, 102, 103, 104, 105].map(BFieldElement::new)),
        state: [9, 11, 22, 33, 44, 55].map(BFieldElement::new).to_vec(),
    };
    let utxo = Utxo::new(
        Digest::new([201, 202, 203, 204, 205].map(BFieldElement::new)),
        vec![coin.clone()],
    );
    let salted = SaltedUtxos {
        utxos: vec![utxo.clone()],
        salt: [bfe!(301), bfe!(302), bfe!(303)],
    };
    for (name, encoding) in [
        ("coin", coin.encode()),
        ("utxo", utxo.encode()),
        ("salted", salted.encode()),
    ] {
        println!(
            "{name}: {:?}",
            encoding.iter().map(|x| x.value()).collect::<Vec<_>>()
        );
    }
}
