use crate::error::JoyError;
use std::{
    fs::{self, File, OpenOptions},
    io::Write,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};
static NEXT: AtomicU64 = AtomicU64::new(0);
pub(crate) fn atomic_write(
    path: &std::path::Path,
    bytes: &[u8],
    replace: bool,
) -> Result<(), JoyError> {
    write_with_counter(path, bytes, replace, &NEXT)
}

/// Keep streamed proof prefixes private until the producer and flush succeed.
pub(crate) fn atomic_produce<T>(
    path: &std::path::Path,
    replace: bool,
    produce: impl FnOnce(File) -> Result<(File, T), JoyError>,
) -> Result<T, JoyError> {
    produce_with_counter(path, replace, &NEXT, produce)
}

fn write_with_counter(
    path: &std::path::Path,
    bytes: &[u8],
    replace: bool,
    next: &AtomicU64,
) -> Result<(), JoyError> {
    produce_with_counter(path, replace, next, |mut file| {
        file.write_all(bytes)?;
        Ok((file, ()))
    })
}

fn produce_with_counter<T>(
    path: &std::path::Path,
    replace: bool,
    next: &AtomicU64,
    produce: impl FnOnce(File) -> Result<(File, T), JoyError>,
) -> Result<T, JoyError> {
    if !replace {
        match fs::symlink_metadata(path) {
            Ok(_) => {
                return Err(JoyError::Io(format!(
                    "destination '{}' exists; --force permits replacement",
                    path.display()
                )))
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
            Err(e) => return Err(e.into()),
        }
    }
    let parent = path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(std::path::Path::new("."));
    let mut temporary = None;
    for _ in 0..100 {
        let name = parent.join(format!(
            ".{}.{}",
            std::process::id(),
            next.fetch_add(1, Ordering::Relaxed)
        ));
        // Digits and dots have no case/normalization variants. Also exclude
        // Win32 trailing-dot/space and default-stream aliases of this basename.
        let destination = path
            .file_name()
            .and_then(|v| v.to_str())
            .and_then(|v| v.split(':').next())
            .map(|v| v.trim_end_matches(['.', ' ']));
        if destination == name.file_name().and_then(|v| v.to_str()) {
            continue;
        }
        match OpenOptions::new().write(true).create_new(true).open(&name) {
            Ok(file) => {
                temporary = Some((name, file));
                break;
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(e.into()),
        }
    }
    let (name, file) =
        temporary.ok_or_else(|| JoyError::Io("cannot allocate artifact staging file".into()))?;
    struct Cleanup(PathBuf);
    impl Drop for Cleanup {
        fn drop(&mut self) {
            let _ = fs::remove_file(&self.0);
        }
    }
    let _cleanup = Cleanup(name.clone());
    let (file, result) = produce(file)?;
    file.sync_all()?;
    drop(file);
    if replace {
        fs::rename(&name, path)?;
    } else {
        fs::hard_link(&name, path).map_err(|e| {
            JoyError::Io(format!(
                "cannot publish '{}': {e}; --force permits replacement",
                path.display()
            ))
        })?;
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn staging_cannot_alias_destination_or_delete_successful_output() {
        let dir = std::env::temp_dir().join(format!("joy-publication-{}", std::process::id()));
        fs::create_dir(&dir).unwrap();
        for replace in [false, true] {
            let path = dir.join(format!(".{}.0", std::process::id()));
            write_with_counter(&path, b"complete", replace, &AtomicU64::new(0)).unwrap();
            assert_eq!(fs::read(&path).unwrap(), b"complete");
            assert_eq!(fs::read_dir(&dir).unwrap().count(), 1);
            assert!(write_with_counter(&path, b"discard", false, &AtomicU64::new(0)).is_err());
            assert_eq!(fs::read(&path).unwrap(), b"complete");
            assert_eq!(fs::read_dir(&dir).unwrap().count(), 1);
            write_with_counter(&path, b"replace", true, &AtomicU64::new(0)).unwrap();
            assert_eq!(fs::read(&path).unwrap(), b"replace");
            assert_eq!(fs::read_dir(&dir).unwrap().count(), 1);
            fs::remove_file(path).unwrap();
        }
        fs::remove_dir(dir).unwrap();
    }
}
