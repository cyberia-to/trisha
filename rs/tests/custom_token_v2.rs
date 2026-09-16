use triton_vm::prelude::*;
fn coin(kind: Digest, state: Vec<u64>) -> Vec<u64> {
    let mut out = vec![state.len() as u64 + 1, state.len() as u64];
    out.extend(state);
    out.extend(kind.values().map(|x| x.value()));
    out
}
fn utxo(coins: Vec<Vec<u64>>) -> Vec<u64> {
    let mut list = vec![coins.len() as u64];
    for coin in coins {
        list.push(coin.len() as u64);
        list.extend(coin);
    }
    let mut out = vec![list.len() as u64];
    out.extend(list);
    out.extend([201, 202, 203, 204, 205]);
    out
}
fn salted(utxos: Vec<Vec<u64>>) -> Vec<u64> {
    let mut list = vec![utxos.len() as u64];
    for u in utxos {
        list.push(u.len() as u64);
        list.extend(u);
    }
    let mut out = vec![301, 302, 303, list.len() as u64];
    out.extend(list);
    out
}
fn authority() -> [u64; 5] {
    Tip5::hash_10(&[11, 22, 33, 44, 55, 2, 3, 0, 0, 0].map(BFieldElement::new)).map(|x| x.value())
}
fn state(amount: u64) -> Vec<u64> {
    let mut v = vec![2, amount];
    v.extend(authority());
    v
}
fn input(program: Digest, amount: u64, extra: bool) -> (Vec<u64>, Vec<u64>) {
    let kind = Digest::new([101, 102, 103, 104, 105].map(BFieldElement::new));
    let native = coin(kind, vec![7, 0, 0, 0]);
    let i = salted(vec![utxo(vec![coin(program, state(10)), native.clone()])]);
    let o = salted(vec![utxo(vec![native, coin(program, state(amount))])]);
    let mut public = vec![0; 5];
    for raw in [&i, &o] {
        public.extend(
            Tip5::hash_varlen(
                &raw.iter()
                    .copied()
                    .map(BFieldElement::new)
                    .collect::<Vec<_>>(),
            )
            .reversed()
            .values()
            .map(|x| x.value()),
        );
    }
    let mut secret = vec![i.len() as u64];
    secret.extend(i);
    secret.push(o.len() as u64);
    secret.extend(o);
    if extra {
        secret.extend([11, 22, 33, 44, 55]);
    }
    (public, secret)
}
fn run(p: &Program, public: Vec<u64>, secret: Vec<u64>) -> Result<Vec<BFieldElement>, String> {
    VM::run(
        p.clone(),
        PublicInput::new(
            public
                .into_iter()
                .map(BFieldElement::new)
                .collect::<Vec<_>>(),
        ),
        NonDeterminism::new(
            secret
                .into_iter()
                .map(BFieldElement::new)
                .collect::<Vec<_>>(),
        ),
    )
    .map_err(|e| e.to_string())
}
#[test]
fn canonical_codec_matches_independent_pinned_neptune_oracle() {
    let raw = salted(vec![utxo(vec![coin(
        Digest::new([101, 102, 103, 104, 105].map(BFieldElement::new)),
        vec![9, 11, 22, 33, 44, 55],
    )])]);
    assert_eq!(
        raw,
        vec![
            301, 302, 303, 23, 1, 21, 15, 1, 13, 7, 6, 9, 11, 22, 33, 44, 55, 101, 102, 103, 104,
            105, 201, 202, 203, 204, 205
        ]
    );
}
#[test]
fn authenticated_utxo_transfer_and_supply_change_use_actual_program_identity() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../examples/neptune/types/custom_token.tri");
    for profile in ["hand", "debug", "release"] {
        let code = if profile == "hand" {
            std::fs::read_to_string(
                std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                    .join("../baselines/triton/os/neptune/types/custom_token.tasm"),
            )
            .unwrap()
        } else {
            trisha_rs::build_tasm(&path, "neptune", profile).unwrap()
        };
        let p = Program::from_code(&code).unwrap();
        for amount in [10, 13, 7] {
            let (public, secret) = input(p.hash(), amount, amount != 10);
            assert!(run(&p, public.clone(), secret.clone())
                .unwrap_or_else(|e| panic!("{profile} amount{amount}: {e}"))
                .is_empty());
            let mut bad = public.clone();
            bad[5] ^= 1;
            assert!(run(&p, bad, secret.clone()).is_err());
            let mut bad = secret.clone();
            bad[1 + 3] ^= 1;
            assert!(run(&p, public.clone(), bad).is_err());
            if amount != 10 {
                let mut bad = secret.clone();
                *bad.last_mut().unwrap() ^= 1;
                assert!(run(&p, public, bad).is_err());
            }
        }
        let (public, secret) = input(Digest::default(), 10, false);
        assert!(
            run(&p, public, secret).is_err(),
            "forged own-program selector accepted"
        );
    }
}
fn rebind(secret: &[u64]) -> Vec<u64> {
    let il = secret[0] as usize;
    let op = 1 + il;
    let ol = secret[op] as usize;
    let mut public = vec![0; 5];
    for raw in [&secret[1..op], &secret[op + 1..op + 1 + ol]] {
        public.extend(
            Tip5::hash_varlen(
                &raw.iter()
                    .copied()
                    .map(BFieldElement::new)
                    .collect::<Vec<_>>(),
            )
            .reversed()
            .values()
            .map(|x| x.value()),
        );
    }
    public
}
#[test]
fn committed_malformed_codec_and_token_policy_are_rejected() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let source = root.join("examples/neptune/types/custom_token.tri");
    for code in [
        std::fs::read_to_string(root.join("baselines/triton/os/neptune/types/custom_token.tasm"))
            .unwrap(),
        trisha_rs::build_tasm(&source, "neptune", "release").unwrap(),
    ] {
        let p = Program::from_code(&code).unwrap();
        let (_, secret) = input(p.hash(), 10, false);
        for (name, raw_index, value) in [
            ("state version", 11, 1),
            ("amount U32", 12, 1u64 << 32),
            ("nested state length", 9, 9),
            ("mixed issuer", 13, 777),
            ("coin count admission", 7, 65),
            ("UTXO count admission", 4, 65),
            ("outer exact consumption", 3, 1),
        ] {
            let mut bad = secret.clone();
            bad[1 + raw_index] = value;
            assert!(
                run(&p, rebind(&bad), bad).is_err(),
                "accepted authenticated {name}"
            );
        }
    }
}

#[test]
fn implementation_bound_fixtures_share_semantics_and_disclose_distinct_claims() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let source = root.join("examples/neptune/types/custom_token.tri");
    let classic =
        Program::from_code(&trisha_rs::build_tasm(&source, "neptune", "release").unwrap()).unwrap();
    let hand = Program::from_code(
        &std::fs::read_to_string(root.join("baselines/triton/os/neptune/types/custom_token.tasm"))
            .unwrap(),
    )
    .unwrap();
    assert_ne!(classic.hash(), hand.hash());
    for (name, amount, bad) in [
        ("transfer", 10, false),
        ("mint", 13, false),
        ("burn", 7, false),
        ("wrong-selfhash", 10, true),
    ] {
        let (ci, cs) = input(
            if bad {
                Digest::default()
            } else {
                classic.hash()
            },
            amount,
            amount != 10,
        );
        let (hi, hs) = input(
            if bad { Digest::default() } else { hand.hash() },
            amount,
            amount != 10,
        );
        assert_eq!(run(&classic, ci.clone(), cs.clone()).is_err(), bad);
        assert_eq!(run(&hand, hi.clone(), hs.clone()).is_err(), bad);
        if !bad {
            assert_ne!(ci, hi);
            assert_eq!(cs.len(), hs.len());
        }
        if std::env::var_os("TRISHA_WRITE_CUSTOM_FIXTURES").is_some() {
            let dir = root.join(format!("baselines/triton/fixtures/custom-token-v2-{name}"));
            std::fs::create_dir_all(&dir).unwrap();
            let words = |v: &[u64]| {
                format!(
                    "[{}]",
                    v.iter()
                        .map(|x| format!("\"{x}\""))
                        .collect::<Vec<_>>()
                        .join(",")
                )
            };
            let text=format!("source = \"../../../../examples/neptune/types/custom_token.tri\"\nhand = \"../../os/neptune/types/custom_token.tasm\"\ntarget = \"neptune\"\ninput = {}\nsecret = {}\nhand_input = {}\nhand_secret = {}\noutput = []\nexpect_failure = {bad}\nmax_cycles = 2000000\nimplementation_bound_identity = \"Canonical Neptune0.15.1 salted UTXOs contain each executing program hash as the selected coin type; public roots consequently differ. All salts, locks, issuer, unrelated native-shaped coins and10-input/{amount}-output amounts are identical.\"\nreference = \"Independent pinned Neptune BFieldCodec layout and upstream Tip5; full own-program token predicate, variant {name}.\"\n",words(&ci),words(&cs),words(&hi),words(&hs));
            std::fs::write(dir.join("vector.bench.toml"), text).unwrap();
        }
    }
}
