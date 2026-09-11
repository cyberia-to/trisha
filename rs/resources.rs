//! The warrior carries its version-matched Neptune modules.
include!(concat!(env!("OUT_DIR"), "/resources.rs"));

pub(crate) fn modules() -> impl Iterator<Item = (String, String)> {
    FILES.iter().filter_map(|(name, text)| {
        name.strip_suffix(".tri")
            .map(|name| (name.replace('/', "."), (*text).to_owned()))
    })
}
