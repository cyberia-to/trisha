use std::{env, fs, io, path::Path};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../networks/neptune/states");
    println!("cargo:rerun-if-changed={}", root.display());
    let mut paths = fs::read_dir(root)?
        .map(|entry| entry.map(|e| e.path()))
        .collect::<io::Result<Vec<_>>>()?;
    paths.sort();
    let mut code = String::from("pub static STATES: &[State] = &[\n");
    let mut state_names = std::collections::BTreeSet::new();
    let mut defaults = std::collections::BTreeSet::new();
    for path in paths {
        if path.extension().is_none_or(|extension| extension != "toml") {
            continue;
        }
        let data: toml::Value = fs::read_to_string(&path)?.parse()?;
        let text = |table: &str, key: &str| -> Result<&str, io::Error> {
            data.get(table)
                .and_then(|v| v.get(key))
                .and_then(|v| v.as_str())
                .ok_or_else(|| {
                    io::Error::other(format!("{}: missing {table}.{key}", path.display()))
                })
        };
        let port = data
            .get("node")
            .and_then(|v| v.get("rpc_port"))
            .and_then(|v| v.as_integer())
            .and_then(|v| u16::try_from(v).ok())
            .ok_or_else(|| io::Error::other("invalid node.rpc_port"))?;
        let default = data
            .get("state")
            .and_then(|v| v.get("is_default"))
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let union = text("state", "union")?;
        let name = text("state", "name")?;
        if !state_names.insert((union.to_owned(), name.to_owned()))
            || (default && !defaults.insert(union.to_owned()))
        {
            return Err(io::Error::other("duplicate state or multiple default states").into());
        }
        code.push_str(&format!("State {{ name: {:?}, union: {:?}, display_name: {:?}, rpc_port: {port}, network_flag: {:?}, currency_symbol: {:?}, chain_id: {:?}, is_default: {default} }},\n",
            text("state", "name")?, text("state", "union")?, text("state", "display_name")?,
            text("node", "network_flag")?, text("currency", "symbol")?, text("state", "chain_id")?));
    }
    code.push_str("];\n");
    fs::write(Path::new(&env::var("OUT_DIR")?).join("states.rs"), code)?;
    Ok(())
}
