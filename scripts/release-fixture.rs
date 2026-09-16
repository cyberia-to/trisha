//! Generate public smoke fixtures from the exact BBG source in a release snapshot.
use std::{fs, path::PathBuf};
fn main() {
    let output = PathBuf::from(
        std::env::args_os()
            .nth(1)
            .expect("fixture output directory"),
    );
    fs::create_dir_all(&output).unwrap();
    let mut state = bbg::BbgState::new();
    let mut record = bbg::types::ParticleRecord::zero();
    record.energy = 77;
    state.particles.insert([1; 32], record);
    let certificate = bbg::certificate::StateCertificate::from_state(&state, &[0]).unwrap();
    fs::write(
        output.join("state.json"),
        serde_json::to_vec_pretty(&certificate).unwrap(),
    )
    .unwrap();
    let all = bbg::certificate::StateCertificate::from_state(&state, &(0..10).collect::<Vec<_>>())
        .unwrap();
    fs::write(
        output.join("state-all.json"),
        serde_json::to_vec_pretty(&all).unwrap(),
    )
    .unwrap();
    state.particles.get_mut(&[1; 32]).unwrap().energy = 88;
    state.refresh_root();
    let changed = bbg::certificate::StateCertificate::from_state(&state, &[0]).unwrap();
    fs::write(
        output.join("other-state.json"),
        serde_json::to_vec_pretty(&changed).unwrap(),
    )
    .unwrap();
}
