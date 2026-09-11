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

include!(concat!(env!("OUT_DIR"), "/states.rs"));

pub fn default_for_union(union: &str) -> Result<&'static State, TrishaError> {
    STATES
        .iter()
        .find(|state| state.union == union && state.is_default)
        .ok_or_else(|| TrishaError::State(format!("no default state for {union}")))
}

pub fn resolve(union: &str, name: &str) -> Result<&'static State, TrishaError> {
    STATES
        .iter()
        .find(|s| s.union == union && s.name == name)
        .ok_or_else(|| TrishaError::State(format!("unknown state {}/{}", union, name)))
}
