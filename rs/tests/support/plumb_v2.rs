//! Independent host state-transition vectors. Roots use upstream Tip5 and a
//! sparse depth-20 tree; no compiled TASM is consulted to derive any claim.
use std::collections::BTreeMap;
use triton_vm::prelude::*;
pub type D = [u64; 5];
pub fn h(x: [u64; 10]) -> D {
    Tip5::hash_10(&x.map(BFieldElement::new)).map(|x| x.value())
}
pub fn pair(a: D, b: D) -> D {
    let mut x = [0; 10];
    x[..5].copy_from_slice(&a);
    x[5..].copy_from_slice(&b);
    h(x)
}
pub fn auth(s: D) -> D {
    h([s[0], s[1], s[2], s[3], s[4], 2, 1, 0, 0, 0])
}
pub const KEY: D = [11, 22, 33, 44, 55];
pub const DUAL: D = [66, 77, 88, 99, 111];
pub fn empty() -> D {
    h([0, 0, 0, 0, 0, 0, 0, 0, 2, 0])
}
#[derive(Clone)]
pub struct Config {
    pub authorities: [D; 5],
    pub hooks: [u64; 5],
}
impl Config {
    pub fn new() -> Self {
        Self {
            authorities: [auth(DUAL), auth(DUAL), auth(DUAL), auth(DUAL), auth(DUAL)],
            hooks: [101, 102, 103, 104, 105],
        }
    }
    pub fn hash(&self) -> D {
        let a = self.authorities;
        let k = self.hooks;
        pair(
            pair(pair(a[0], a[1]), pair(a[2], a[3])),
            pair(a[4], h([k[0], k[1], k[2], k[3], k[4], 2, 2, 0, 0, 0])),
        )
    }
    pub fn words(&self) -> Vec<u64> {
        self.authorities
            .iter()
            .flatten()
            .copied()
            .chain(self.hooks)
            .collect()
    }
}
#[derive(Clone)]
pub struct Coin {
    pub id: u64,
    pub balance: u64,
    pub nonce: u64,
    pub auth: D,
    pub lock: u64,
    pub controller: u64,
    pub locked_by: u64,
    pub lock_data: u64,
}
impl Coin {
    pub fn new(id: u64) -> Self {
        Self {
            id,
            balance: 100,
            nonce: 7,
            auth: auth(KEY),
            lock: 4,
            controller: 0,
            locked_by: 0,
            lock_data: 0,
        }
    }
    pub fn hash(&self) -> D {
        pair(
            h([
                self.id,
                self.balance,
                self.nonce,
                self.lock,
                self.controller,
                self.locked_by,
                self.lock_data,
                2,
                1,
                0,
            ]),
            self.auth,
        )
    }
    pub fn words(&self) -> Vec<u64> {
        let mut v = vec![self.id, self.balance, self.nonce];
        v.extend(self.auth);
        v.extend([self.lock, self.controller, self.locked_by, self.lock_data]);
        v
    }
}
#[derive(Clone)]
pub struct Card {
    pub id: u64,
    pub owner: u64,
    pub nonce: u64,
    pub auth: D,
    pub lock: u64,
    pub collection: u64,
    pub metadata: u64,
    pub royalty: u64,
    pub creator: D,
    pub flags: u64,
}
impl Card {
    pub fn new() -> Self {
        Self {
            id: 3,
            owner: 201,
            nonce: 7,
            auth: auth(KEY),
            lock: 4,
            collection: 301,
            metadata: 401,
            royalty: 250,
            creator: auth(DUAL),
            flags: 31,
        }
    }
    pub fn hash(&self) -> D {
        pair(
            h([
                self.id,
                self.owner,
                self.nonce,
                self.lock,
                self.collection,
                self.metadata,
                self.royalty,
                self.flags,
                2,
                2,
            ]),
            pair(self.auth, self.creator),
        )
    }
    pub fn words(&self) -> Vec<u64> {
        let mut v = vec![self.id, self.owner, self.nonce];
        v.extend(self.auth);
        v.extend([self.lock, self.collection, self.metadata, self.royalty]);
        v.extend(self.creator);
        v.push(self.flags);
        v
    }
}
pub fn tree(leaves: &BTreeMap<u64, D>, index: u64) -> (D, Vec<u64>) {
    let mut nodes = leaves.clone();
    let mut zero = empty();
    let mut idx = index;
    let mut path = vec![];
    for _ in 0..20 {
        path.extend(nodes.get(&(idx ^ 1)).copied().unwrap_or(zero));
        let mut parents = BTreeMap::new();
        for k in nodes.keys() {
            let p = k / 2;
            parents.entry(p).or_insert_with(|| {
                pair(
                    nodes.get(&(p * 2)).copied().unwrap_or(zero),
                    nodes.get(&(p * 2 + 1)).copied().unwrap_or(zero),
                )
            });
        }
        nodes = parents;
        zero = pair(zero, zero);
        idx /= 2;
    }
    (nodes.get(&0).copied().unwrap_or(zero), path)
}
pub fn seal(tag: u64, id: u64, nonce: u64) -> D {
    h([tag, id, nonce, 0, 0, 0, 0, 0, 0, 0])
}
#[derive(Clone)]
pub struct Case {
    pub name: String,
    pub public: Vec<u64>,
    pub secret: Vec<u64>,
    pub output: Vec<u64>,
}
fn claim(op: u64, old: D, new: D, fields: &[u64], cfg: D) -> Vec<u64> {
    let mut p = vec![op];
    p.extend(old);
    p.extend(new);
    p.extend(fields);
    p.extend(cfg);
    p
}
pub fn coin_cases() -> Vec<Case> {
    let cfg = Config::new();
    let a = Coin::new(3);
    let mut b = Coin::new(6);
    b.balance = 20;
    b.nonce = 2;
    let leaves = BTreeMap::from([(a.id, a.hash()), (b.id, b.hash())]);
    let (root, path) = tree(&leaves, a.id);
    let mut cases = vec![];
    for op in [0, 1, 3, 4] {
        let mut next = a.clone();
        next.nonce += 1;
        let mut out = vec![cfg.hooks[op as usize]];
        let mut secret = cfg.words();
        let mut changed = leaves.clone();
        if op == 3 {
            secret.extend(DUAL);
        }
        secret.extend(a.words());
        secret.push(a.id);
        if op != 3 {
            secret.extend(KEY);
            secret.extend(DUAL);
        }
        let fields = match op {
            0 => {
                next.balance -= 9;
                vec![120, 10, 9]
            }
            1 => {
                next.lock = 15;
                vec![120, 15]
            }
            3 => {
                next.balance += 9;
                vec![120, 129, 9]
            }
            4 => {
                next.balance -= 9;
                vec![120, 111, 10, 9]
            }
            _ => unreachable!(),
        };
        changed.insert(a.id, next.hash());
        if op == 0 {
            secret.extend(b.words());
            secret.push(b.id);
            let (_, second_path) = tree(&changed, b.id);
            let mut nb = b.clone();
            nb.balance += 9;
            nb.nonce += 1;
            changed.insert(b.id, nb.hash());
            secret.extend(path.clone());
            secret.extend(second_path);
            out.extend(seal(0, a.id, a.nonce));
            out.extend(seal(0, b.id, b.nonce));
            out.extend([1, 120]);
        } else {
            secret.extend(path.clone());
            out.extend(seal(0, a.id, a.nonce));
            if op == 1 {
                out.extend([1, 120]);
            } else {
                out.extend([2, 120, if op == 3 { 129 } else { 111 }]);
            }
        }
        cases.push(Case {
            name: format!("coin-{op}"),
            public: claim(op, root, tree(&changed, 0).0, &fields, cfg.hash()),
            secret,
            output: out,
        });
    }
    let mut nc = cfg.clone();
    nc.authorities[1] = [0; 5];
    nc.hooks[0] = 777;
    let mut secret = cfg.words();
    secret.extend(DUAL);
    secret.extend(nc.words());
    let mut public = claim(2, root, root, &[120], cfg.hash());
    public.extend(nc.hash());
    cases.push(Case {
        name: "coin-2".into(),
        public,
        secret,
        output: vec![103, 1, 120],
    });
    cases
}
pub fn card_cases() -> Vec<Case> {
    let cfg = Config::new();
    let a = Card::new();
    let leaves = BTreeMap::from([(a.id, a.hash())]);
    let (root, path) = tree(&leaves, a.id);
    let mut cases = vec![];
    for op in [0, 1, 2, 4] {
        let mut next = a.clone();
        next.nonce += 1;
        let mut secret = cfg.words();
        secret.extend(a.words());
        secret.push(a.id);
        secret.extend(KEY);
        if op != 2 {
            secret.extend(DUAL);
        }
        let fields = match op {
            0 => {
                next.owner = 202;
                next.auth = auth([1, 2, 3, 4, 5]);
                secret.push(next.owner);
                secret.extend(next.auth);
                vec![1, a.id, 10]
            }
            1 => {
                next.lock = 15;
                vec![1, a.id, 15]
            }
            2 => {
                next.metadata = 402;
                vec![1, a.id, 402]
            }
            4 => vec![1, 0, a.id, 10],
            _ => unreachable!(),
        };
        secret.extend(path.clone());
        let nr = if op == 4 {
            tree(&BTreeMap::new(), 0).0
        } else {
            tree(&BTreeMap::from([(a.id, next.hash())]), 0).0
        };
        let mut out = vec![];
        if op != 2 {
            out.push(cfg.hooks[op as usize]);
        }
        out.extend(seal(5, a.id, a.nonce));
        match op {
            0 => out.extend([0, a.id, a.owner, next.owner, a.royalty]),
            1 => out.extend([1, a.id, 15]),
            2 => out.extend([2, a.id, a.metadata, 402, 103]),
            4 => out.extend([4, a.id, a.owner, 6, 1, 0]),
            _ => unreachable!(),
        };
        cases.push(Case {
            name: format!("card-{op}"),
            public: claim(op, root, nr, &fields, cfg.hash()),
            secret,
            output: out,
        });
    }
    let mut new = Card::new();
    new.nonce = 0;
    new.lock = 0;
    let empty_root = tree(&BTreeMap::new(), 0).0;
    let (_, path) = tree(&BTreeMap::new(), new.id);
    let metadata = [501, 502, 503, 504, 505, 10, 506, 2, 0, 0];
    let mut public = claim(
        3,
        empty_root,
        tree(&BTreeMap::from([(new.id, new.hash())]), 0).0,
        &[0, 1, 10, new.id, new.metadata, new.collection],
        cfg.hash(),
    );
    public.extend(h(metadata));
    let mut secret = cfg.words();
    secret.extend(DUAL);
    secret.extend(metadata);
    secret.push(new.owner);
    secret.extend(new.auth);
    secret.extend(new.creator);
    secret.extend([new.royalty, new.flags, new.id]);
    secret.extend(path);
    let mut out = vec![104, 3, new.id];
    out.extend(new.creator);
    out.extend([new.collection, new.metadata, 6, 0, 1]);
    cases.push(Case {
        name: "card-3".into(),
        public,
        secret,
        output: out,
    });
    let mut nc = cfg.clone();
    nc.authorities[0] = [0; 5];
    let mut public = claim(2, root, root, &[1, 0, 0], cfg.hash());
    public.extend(nc.hash());
    let mut secret = cfg.words();
    secret.extend(DUAL);
    secret.extend(nc.words());
    cases.push(Case {
        name: "card-config".into(),
        public,
        secret,
        output: vec![103],
    });
    cases
}
