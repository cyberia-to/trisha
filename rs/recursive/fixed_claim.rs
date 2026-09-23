//! Claim binding for fixed, versioned protocol programs.
//!
//! The program digest is owner configuration, never witness input. Each public
//! digest is reversed exactly as Neptune's claim constructors specify. Output is
//! empty and the native version is pinned by the linked Triton dependency.
use tasm_lib::hashing::algebraic_hasher::hash_varlen::HashVarlen;
use tasm_lib::library::Library;
use triton_vm::prelude::*;

const ADDRESS: u64 = super::witness::CONTROL_ADDRESS + 256;

/// Expected claim for a pinned protocol program and caller-authenticated digests.
pub fn expected_claim(program: Digest, inputs: &[Digest]) -> Claim {
    Claim::new(program).with_input(
        inputs
            .iter()
            .flat_map(|digest| digest.values().into_iter().rev())
            .collect::<Vec<_>>(),
    )
}

/// Emit a binder before the common recursive verifier. The caller links
/// `recursive::assembly()` once, which also supplies HashVarlen dependencies.
/// `entrypoint` and `program` must come from trusted owner metadata.
pub fn fixed_claim_assembly(entrypoint: &str, program: Digest, digest_count: usize) -> String {
    assert!(
        !entrypoint.is_empty()
            && entrypoint
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '_')
    );
    assert!((1..=3).contains(&digest_count));
    let width = digest_count * Digest::LEN;
    // Discover input offsets through the authoritative codec rather than copy
    // its struct/vector layout. Unique markers cannot overlap header values.
    let markers: Vec<_> = (0..width)
        .map(|i| BFieldElement::new(1_000_000 + i as u64))
        .collect();
    let template = Claim::new(program).with_input(markers.clone()).encode();
    let positions: Vec<_> = markers
        .iter()
        .map(|marker| {
            let positions: Vec<_> = template
                .iter()
                .enumerate()
                .filter_map(|(i, value)| (value == marker).then_some(i))
                .collect();
            assert_eq!(
                positions.len(),
                1,
                "fixed claim marker collides with pinned program digest"
            );
            positions[0]
        })
        .collect();
    let mut code = format!("{entrypoint}:\n");
    for (offset, value) in template.iter().enumerate() {
        if !positions.contains(&offset) {
            code.push_str(&format!(
                "    push {}\n    push {}\n    write_mem 1\n    pop 1\n",
                value.value(),
                ADDRESS + offset as u64
            ));
        }
    }
    for popped in 0..width {
        let group = (width - 1 - popped) / Digest::LEN;
        let input_index = group * Digest::LEN + popped % Digest::LEN;
        code.push_str(&format!(
            "    push {}\n    write_mem 1\n    pop 1\n",
            ADDRESS + positions[input_index] as u64
        ));
    }
    let mut library = Library::new();
    let hash = library.import(Box::new(HashVarlen));
    code.push_str(&format!("    push {ADDRESS}\n    push {}\n    call {hash}\n    swap 4\n    swap 1\n    swap 3\n    swap 1\n    call {}\n    return\n", template.len(), super::ENTRYPOINT));
    code
}
