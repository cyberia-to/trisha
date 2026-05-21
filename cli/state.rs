use crate::error::TrishaError;

#[derive(Clone, Debug)]
pub struct State {
    pub name: &'static str,
    pub union: &'static str,
    pub display_name: &'static str,
    pub rpc_port: u16,
    pub network_flag: &'static str,
    pub currency_symbol: &'static str,
    pub chain_id: &'static str,
    pub is_default: bool,
}

pub static STATES: &[State] = &[
    State {
        name: "mainnet",
        union: "neptune",
        display_name: "Neptune Mainnet",
        rpc_port: 9799,
        network_flag: "alpha-mainnet",
        currency_symbol: "NEPT",
        chain_id: "1",
        is_default: true,
    },
    State {
        name: "testnet",
        union: "neptune",
        display_name: "Neptune Testnet",
        rpc_port: 9899,
        network_flag: "testnet",
        currency_symbol: "tNEPT",
        chain_id: "2",
        is_default: false,
    },
];

pub fn resolve(union: &str, name: &str) -> Result<&'static State, TrishaError> {
    STATES
        .iter()
        .find(|s| s.union == union && s.name == name)
        .ok_or_else(|| TrishaError::State(format!("unknown state {}/{}", union, name)))
}

pub fn resolve_union_default(union: &str) -> Result<&'static State, TrishaError> {
    STATES
        .iter()
        .find(|s| s.union == union && s.is_default)
        .or_else(|| STATES.iter().find(|s| s.union == union))
        .ok_or_else(|| TrishaError::State(format!("unknown union: {}", union)))
}

pub fn default_state() -> &'static State {
    STATES.iter().find(|s| s.is_default).unwrap_or(&STATES[0])
}

pub fn unions() -> Vec<&'static str> {
    let mut seen = Vec::new();
    for s in STATES {
        if !seen.contains(&s.union) {
            seen.push(s.union);
        }
    }
    seen
}
