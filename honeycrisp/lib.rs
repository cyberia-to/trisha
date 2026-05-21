pub mod neptune_mine;

pub use triton_vm::prelude::Digest;

#[cfg(feature = "triton")]
mod warrior;
#[cfg(feature = "triton")]
pub use warrior::Warrior;
