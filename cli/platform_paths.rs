//! Platform-native locations for non-secret Trisha preferences.
use std::ffi::OsString;
use std::path::PathBuf;

pub fn config_dir() -> PathBuf {
    resolve(
        std::env::consts::OS,
        |name| std::env::var_os(name),
        std::env::temp_dir(),
    )
}

fn resolve(os: &str, get: impl Fn(&str) -> Option<OsString>, temporary: PathBuf) -> PathBuf {
    let value = |name| get(name).filter(|v| !v.is_empty()).map(PathBuf::from);
    if let Some(path) = value("TRISHA_CONFIG_DIR") {
        return path;
    }
    let base = match os {
        "windows" => value("APPDATA")
            .or_else(|| value("USERPROFILE").map(|home| home.join("AppData").join("Roaming"))),
        "macos" => value("HOME").map(|home| home.join("Library/Application Support")),
        _ => value("XDG_CONFIG_HOME").or_else(|| value("HOME").map(|home| home.join(".config"))),
    };
    base.unwrap_or(temporary).join("trisha")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn with(os: &str, vars: &[(&str, &str)]) -> PathBuf {
        resolve(
            os,
            |name| {
                vars.iter()
                    .find(|(key, _)| *key == name)
                    .map(|(_, value)| OsString::from(value))
            },
            PathBuf::from("temporary"),
        )
    }

    #[test]
    fn windows_uses_roaming_configuration_without_home_or_unix_tmp() {
        assert_eq!(
            with("windows", &[("APPDATA", "roaming"), ("HOME", "unix")]),
            PathBuf::from("roaming/trisha")
        );
        assert_eq!(
            with("windows", &[("USERPROFILE", "user")]),
            PathBuf::from("user/AppData/Roaming/trisha")
        );
        assert_eq!(
            with("windows", &[("APPDATA", "")]),
            PathBuf::from("temporary/trisha")
        );
    }

    #[test]
    fn overrides_and_unicode_are_preserved_on_every_platform() {
        for os in ["windows", "macos", "linux"] {
            assert_eq!(
                with(os, &[("TRISHA_CONFIG_DIR", "путь с пробелом")]),
                PathBuf::from("путь с пробелом")
            );
        }
    }

    #[test]
    fn unix_locations_and_empty_overrides_follow_the_contract() {
        assert_eq!(
            with("macos", &[("HOME", "user")]),
            PathBuf::from("user/Library/Application Support/trisha")
        );
        assert_eq!(
            with("linux", &[("HOME", "user")]),
            PathBuf::from("user/.config/trisha")
        );
        assert_eq!(
            with(
                "linux",
                &[("TRISHA_CONFIG_DIR", ""), ("XDG_CONFIG_HOME", "config")]
            ),
            PathBuf::from("config/trisha")
        );
    }
}
