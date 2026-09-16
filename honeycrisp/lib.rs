#[cfg(all(feature = "gpu", target_os = "macos", target_arch = "aarch64"))]
pub mod aruminium_mine;
mod cpu;
pub mod neptune_mine;
pub mod types;

pub use triton_vm::prelude::Digest;
pub use types::{
    BlockTemplate, MineState, DIGEST_LEN, HEADER_PATH_LEN, HEIGHT, KERNEL_PATH_LEN, POW_PATH_LEN,
};

#[cfg(feature = "triton")]
mod warrior;
#[cfg(feature = "triton")]
pub use warrior::Warrior;

#[cfg(feature = "triton")]
#[path = "../bundle.rs"]
mod bundle;
