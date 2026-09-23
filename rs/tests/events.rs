use triton_vm::prelude::*;
fn execute(source: &str, input: Vec<u64>, secret: Vec<u64>) -> Vec<Vec<u64>> {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("events.tri");
    std::fs::write(&path, source).unwrap();
    ["debug", "release"]
        .into_iter()
        .map(|profile| {
            let code = trisha_rs::build_tasm(&path, "triton", profile).unwrap();
            VM::run(
                Program::from_code(&code).unwrap(),
                PublicInput::new(
                    input
                        .iter()
                        .copied()
                        .map(BFieldElement::new)
                        .collect::<Vec<_>>(),
                ),
                NonDeterminism::new(
                    secret
                        .iter()
                        .copied()
                        .map(BFieldElement::new)
                        .collect::<Vec<_>>(),
                ),
            )
            .unwrap()
            .iter()
            .map(|v| v.value())
            .collect()
        })
        .collect()
}
#[test]
fn reveal_uses_declaration_order_and_preserves_locals() {
    let source="program events\nevent First { a:Field, b:Field, c:Field }\nfn main(){let a:Field=pub_read()\nlet b:Field=pub_read()\nlet c:Field=pub_read()\nreveal First{c:c,a:a,b:b}\npub_write(a)\npub_write(b)\npub_write(c)}";
    for result in execute(source, vec![11, 22, 33], vec![]) {
        assert_eq!(result, vec![0, 11, 22, 33, 11, 22, 33]);
    }
}

fn seal_digest(tag: u64, payload: &[u64]) -> Vec<u64> {
    let mut block = [BFieldElement::new(0); 10];
    block[0] = BFieldElement::new(tag);
    for (slot, value) in block[1..].iter_mut().zip(payload) {
        *slot = BFieldElement::new(*value);
    }
    Tip5::hash_10(&block)
        .into_iter()
        .map(|v| v.value())
        .collect()
}
#[test]
fn aggregate_reveal_and_seal_share_flattened_word_order() {
    let source="program events\nstruct Pair{x:Field,y:Field}\nevent Empty{}\nevent Data{pair:Pair,values:[Field;3],tail:Field}\nfn main(){let p=Pair{x:11,y:22}\nlet a:[Field;3]=[33,44,55]\nlet tail:Field=66\nreveal Data{tail:tail,values:a,pair:p}\nseal Data{values:a,pair:p,tail:tail}\npub_write(p.x)\npub_write(p.y)\npub_write(a[2])\npub_write(tail)}";
    let mut expected = vec![1, 11, 22, 33, 44, 55, 66];
    expected.extend(seal_digest(1, &[11, 22, 33, 44, 55, 66]));
    expected.extend([11, 22, 55, 66]);
    for result in execute(source, vec![], vec![]) {
        assert_eq!(result, expected);
    }
}
#[test]
fn event_expressions_evaluate_once_in_declaration_order() {
    let source="program events\nevent E{a:Field,b:Field}\nfn read(marker:Field)->Field{pub_write(marker)\npub_read()}\nfn main(){reveal E{b:read(102),a:read(101)}\nseal E{b:read(202),a:read(201)}}";
    let mut expected = vec![101, 102, 0, 11, 22, 201, 202];
    expected.extend(seal_digest(0, &[33, 44]));
    for result in execute(source, vec![11, 22, 33, 44], vec![]) {
        assert_eq!(result, expected);
    }
}
#[test]
fn empty_and_full_block_events_preserve_stack_balance() {
    let source="program events\nevent Empty{}\nevent Full{values:[Field;9]}\nfn main(){let keep:Field=77\nreveal Empty{}\nseal Empty{}\nlet a:[Field;9]=[1,2,3,4,5,6,7,8,9]\nreveal Full{values:a}\nseal Full{values:a}\npub_write(keep)\npub_write(a[8])}";
    let mut expected = vec![0];
    expected.extend(seal_digest(0, &[]));
    expected.extend([1, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    expected.extend(seal_digest(1, &[1, 2, 3, 4, 5, 6, 7, 8, 9]));
    expected.extend([77, 9]);
    for result in execute(source, vec![], vec![]) {
        assert_eq!(result, expected);
    }
}
#[test]
fn oversized_payload_and_duplicate_fields_reject() {
    for source in [
        "program e\nevent E{a:[Field;10]}\nfn main(){}",
        "program e\nevent E{a:Digest,b:Digest}\nfn main(){}",
        "program e\nstruct Huge{a:[Field;4294967295],b:[Field;2]}\nevent E{a:Huge}\nfn main(){}",
        "program e\nevent E{a:Field}\nfn main(){reveal E{a:1,a:2}}",
        "program e\nevent E{a:Field,a:Field}\nfn main(){}",
    ] {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("events.tri");
        std::fs::write(&path, source).unwrap();
        assert!(
            trisha_rs::build_tasm(&path, "triton", "release").is_err(),
            "accepted {source}"
        );
    }
}
