#[path = "support/plumb_v2.rs"]
mod vectors;
use triton_vm::prelude::*;
use vectors::*;
fn run(program: &Program, c: &Case) -> Result<Vec<u64>, String> {
    VM::run(
        program.clone(),
        PublicInput::new(
            c.public
                .iter()
                .copied()
                .map(BFieldElement::new)
                .collect::<Vec<_>>(),
        ),
        NonDeterminism::new(
            c.secret
                .iter()
                .copied()
                .map(BFieldElement::new)
                .collect::<Vec<_>>(),
        ),
    )
    .map(|v| v.into_iter().map(|x| x.value()).collect())
    .map_err(|e| e.to_string())
}
#[test]
fn complete_coin_and_card_transitions_authenticate_claims() {
    for (name, cases) in [("coin", coin_cases()), ("card", card_cases())] {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join(format!("../examples/neptune/standards/{name}.tri"));
        for profile in ["hand", "debug", "release"] {
            let code = if profile == "hand" {
                std::fs::read_to_string(std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join(
                    format!("../baselines/triton/os/neptune/standards/{name}.tasm"),
                ))
                .unwrap()
            } else {
                trisha_rs::build_tasm(&path, "neptune", profile).unwrap()
            };
            let p = Program::from_code(&code).unwrap();
            for c in &cases {
                assert_eq!(
                    run(&p, c).unwrap_or_else(|e| panic!("{} {profile}: {e}", c.name)),
                    c.output,
                    "{} {profile}",
                    c.name
                );
                for (label, index) in [("old root", 1), ("new root", 6)] {
                    let mut bad = c.clone();
                    bad.public[index] ^= 1;
                    assert!(run(&p, &bad).is_err(), "{} accepts {label}", c.name);
                }
                let mut bad = c.clone();
                bad.secret[0] ^= 1;
                assert!(
                    run(&p, &bad).is_err(),
                    "{} accepts changed authority config",
                    c.name
                );
                let mut bad = c.clone();
                bad.public[0] = 5;
                assert!(run(&p, &bad).is_err(), "unknown operation accepted");
            }
        }
    }
}

#[test]
fn tree_paths_and_full_authority_words_are_not_optional() {
    for (name, cases) in [("coin", coin_cases()), ("card", card_cases())] {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
        let source = root.join(format!("examples/neptune/standards/{name}.tri"));
        let programs = [
            Program::from_code(
                &std::fs::read_to_string(
                    root.join(format!("baselines/triton/os/neptune/standards/{name}.tasm")),
                )
                .unwrap(),
            )
            .unwrap(),
            Program::from_code(&trisha_rs::build_tasm(&source, "neptune", "release").unwrap())
                .unwrap(),
        ];
        for c in cases {
            let config_only = c.name == "coin-2" || c.name == "card-config";
            let mut bad = c.clone();
            let auth_offset = if config_only || c.name.ends_with("-3") {
                30
            } else if name == "coin" {
                43
            } else {
                49
            };
            bad.secret[auth_offset + 4] ^= 1;
            for p in &programs {
                assert!(
                    run(p, &bad).is_err(),
                    "{} ignored final authority preimage word",
                    c.name
                );
            }
            if !config_only {
                let mut bad = c.clone();
                *bad.secret.last_mut().unwrap() ^= 1;
                for p in &programs {
                    assert!(run(p, &bad).is_err(), "{} ignored Merkle sibling", c.name);
                }
            }
            if c.name.ends_with("-3") || c.name.ends_with("-4") {
                let mut bad = c.clone();
                bad.public[12] += 1;
                for p in &programs {
                    assert!(
                        run(p, &bad).is_err(),
                        "{} ignored supply/count relation",
                        c.name
                    );
                }
            }
            if c.name == "coin-1" || c.name == "card-1" {
                let mut bad = c.clone();
                bad.public[if name == "coin" { 12 } else { 13 }] = 3;
                for p in &programs {
                    assert!(run(p, &bad).is_err(), "{} shortened lock", c.name);
                }
            }
        }
    }
}

#[test]
fn disabled_authority_is_checked_as_all_five_words() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("auth.tri");
    std::fs::write(&path,"program authority\nuse os.neptune.standards.plumb\nfn main(){let a:Digest=pub_read5()\nif plumb.is_zero(a){pub_write(0)}else{plumb.verify_auth(a)\npub_write(1)}}").unwrap();
    let p =
        Program::from_code(&trisha_rs::build_tasm(&path, "neptune", "release").unwrap()).unwrap();
    assert_eq!(
        run(
            &p,
            &Case {
                name: "disabled".into(),
                public: vec![0; 5],
                secret: vec![],
                output: vec![]
            }
        )
        .unwrap(),
        vec![0]
    );
    assert_eq!(
        run(
            &p,
            &Case {
                name: "valid".into(),
                public: auth(KEY).to_vec(),
                secret: KEY.to_vec(),
                output: vec![]
            }
        )
        .unwrap(),
        vec![1]
    );
    let bad = Case {
        name: "nonzero with field-sum zero".into(),
        public: vec![1, 18446744069414584320, 0, 0, 0],
        secret: KEY.to_vec(),
        output: vec![],
    };
    assert!(run(&p, &bad).is_err());
}

#[test]
fn fixtures_record_independent_complete_transition_claims() {
    if std::env::var_os("TRISHA_WRITE_PLUMB_FIXTURES").is_none() {
        return;
    }
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let words = |v: &[u64]| {
        format!(
            "[{}]",
            v.iter()
                .map(|x| format!("\"{x}\""))
                .collect::<Vec<_>>()
                .join(", ")
        )
    };
    for (name, cases) in [("coin", coin_cases()), ("card", card_cases())] {
        for c in cases {
            let dir = root.join(format!("baselines/triton/fixtures/plumb-v2-{}", c.name));
            std::fs::create_dir_all(&dir).unwrap();
            let text=format!("source = \"../../../../examples/neptune/standards/{name}.tri\"\nhand = \"../../os/neptune/standards/{name}.tasm\"\ntarget = \"neptune\"\ninput = {}\nsecret = {}\noutput = {}\nmax_cycles = 2000000\nreference = \"PLUMB v2 complete {} transition; independent upstream Tip5 sparse-tree host oracle, full Digest authorities, same-sibling roots, declared event words.\"\n",words(&c.public),words(&c.secret),words(&c.output),c.name);
            std::fs::write(dir.join("vector.bench.toml"), text).unwrap();
        }
    }
}

#[test]
fn shared_config_utility_fixture_uses_v2_full_digest_schema() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let cfg = Config::new();
    let library =
        std::fs::read_to_string(root.join("baselines/triton/os/neptune/standards/plumb.tasm"))
            .unwrap();
    let prefix = format!(
        "{} {} call __verify_config push 1 write_io 1 halt\n",
        vec!["divine 1"; 30].join(" "),
        vec!["read_io 1"; 5].join(" ")
    );
    let p = Program::from_code(&(prefix.clone() + &library)).unwrap();
    let source="program baseline_plumb_config\nuse os.neptune.standards.plumb\nfn main(){let expected:Digest=pub_read5()\nlet a:Digest=divine5() let b:Digest=divine5() let c:Digest=divine5() let d:Digest=divine5() let e:Digest=divine5()\nlet h0=divine() let h1=divine() let h2=divine() let h3=divine() let h4=divine()\nplumb.verify_config(a,b,c,d,e,h0,h1,h2,h3,h4,expected)\npub_write(1)}\n";
    let tmp = tempfile::tempdir().unwrap();
    let path = tmp.path().join("main.tri");
    std::fs::write(&path, source).unwrap();
    let compiled =
        Program::from_code(&trisha_rs::build_tasm(&path, "neptune", "release").unwrap()).unwrap();
    for bad in [false, true] {
        let mut secret = cfg.words();
        if bad {
            *secret.last_mut().unwrap() += 1;
        }
        let c = Case {
            name: "config".into(),
            public: cfg.hash().to_vec(),
            secret,
            output: vec![1],
        };
        for program in [&p, &compiled] {
            if bad {
                assert!(run(program, &c).is_err());
            } else {
                assert_eq!(run(program, &c).unwrap(), vec![1]);
            }
        }
    }
    if std::env::var_os("TRISHA_WRITE_PLUMB_FIXTURES").is_some() {
        let words = |v: &[u64]| {
            format!(
                "[{}]",
                v.iter()
                    .map(|x| format!("\"{x}\""))
                    .collect::<Vec<_>>()
                    .join(",")
            )
        };
        for bad in [false, true] {
            let dir = root.join(if bad {
                "baselines/triton/fixtures/plumb-config-bad"
            } else {
                "baselines/triton/fixtures/plumb-config"
            });
            let mut secret = cfg.words();
            if bad {
                *secret.last_mut().unwrap() += 1;
            }
            std::fs::write(dir.join("main.tri"), source).unwrap();
            std::fs::write(dir.join("vector.bench.toml"),format!("source=\"main.tri\"\nhand=\"../../os/neptune/standards/plumb.tasm\"\ntarget=\"neptune\"\ninput={}\nsecret={}\noutput=[1]\nexpect_failure={bad}\nreference=\"PLUMBv2 full30-field config, independent upstream Tip5 pair tree; last-hook mutation rejects.\"\nhand_prefix=\"{}\"\n",words(&cfg.hash()),words(&secret),prefix.trim())).unwrap();
        }
    }
}

#[test]
fn card_flags_creator_and_metadata_cap_are_bound_to_authenticated_state() {
    use std::collections::BTreeMap;
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let source = root.join("examples/neptune/standards/card.tri");
    let programs = [
        Program::from_code(
            &std::fs::read_to_string(root.join("baselines/triton/os/neptune/standards/card.tasm"))
                .unwrap(),
        )
        .unwrap(),
        Program::from_code(&trisha_rs::build_tasm(&source, "neptune", "release").unwrap()).unwrap(),
    ];
    let cases = card_cases();
    for (op, bit) in [(0, 1), (1, 8), (2, 4), (4, 2)] {
        let mut case = cases
            .iter()
            .find(|c| c.name == format!("card-{op}"))
            .unwrap()
            .clone();
        let mut old = Card::new();
        old.flags &= !bit;
        case.secret[47] = old.flags;
        case.public[1..6].copy_from_slice(&tree(&BTreeMap::from([(old.id, old.hash())]), 0).0);
        if op != 4 {
            let mut new = old.clone();
            new.nonce += 1;
            match op {
                0 => {
                    new.owner = 202;
                    new.auth = auth([1, 2, 3, 4, 5]);
                }
                1 => new.lock = 15,
                2 => new.metadata = 402,
                _ => unreachable!(),
            }
            case.public[6..11].copy_from_slice(&tree(&BTreeMap::from([(new.id, new.hash())]), 0).0);
        }
        for p in &programs {
            assert!(
                run(p, &case).is_err(),
                "operation{op} ignored authenticated capability flag"
            );
        }
    }
    let mint = cases.iter().find(|c| c.name == "card-3").unwrap();
    let mut bad = mint.clone();
    bad.secret[51] ^= 1;
    let mut new = Card::new();
    new.nonce = 0;
    new.lock = 0;
    new.creator[0] ^= 1;
    bad.public[6..11].copy_from_slice(&tree(&BTreeMap::from([(new.id, new.hash())]), 0).0);
    for p in &programs {
        assert!(
            run(p, &bad).is_err(),
            "creator substituted while recomputing valid destination root"
        );
    }
    let mut bad = mint.clone();
    bad.public[13] = 0;
    for p in &programs {
        assert!(
            run(p, &bad).is_err(),
            "metadata cap replaced by unlimited public cap"
        );
    }
}
