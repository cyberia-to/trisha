pub mod neptune_mine;
pub mod types;
#[cfg(feature = "gpu")]
pub mod aruminium_mine;

pub use triton_vm::prelude::Digest;
pub use types::{BlockTemplate, MineState, DIGEST_LEN, HEADER_PATH_LEN, HEIGHT, KERNEL_PATH_LEN, POW_PATH_LEN};

#[cfg(feature = "triton")]
mod warrior;
#[cfg(feature = "triton")]
pub use warrior::Warrior;

#[cfg(feature = "triton")]
#[path = "../bundle.rs"]
mod bundle;
