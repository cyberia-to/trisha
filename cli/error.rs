use std::fmt;

#[derive(Debug)]
pub enum TrishaError {
    #[cfg(feature = "triton")]
    Compile(String),
    #[cfg(feature = "triton")]
    Execute(String),
    #[cfg(feature = "triton")]
    Prove(String),
    #[cfg(feature = "triton")]
    Verify(String),
    #[cfg(feature = "triton")]
    Deploy(String),
    Node(String),
    State(String),
    Io(String),
}

impl fmt::Display for TrishaError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            #[cfg(feature = "triton")]
            TrishaError::Compile(msg) => write!(f, "compile error: {}", msg),
            #[cfg(feature = "triton")]
            TrishaError::Execute(msg) => write!(f, "execution error: {}", msg),
            #[cfg(feature = "triton")]
            TrishaError::Prove(msg) => write!(f, "prove error: {}", msg),
            #[cfg(feature = "triton")]
            TrishaError::Verify(msg) => write!(f, "verify error: {}", msg),
            #[cfg(feature = "triton")]
            TrishaError::Deploy(msg) => write!(f, "deploy error: {}", msg),
            TrishaError::Node(msg) => write!(f, "node error: {}", msg),
            TrishaError::State(msg) => write!(f, "state error: {}", msg),
            TrishaError::Io(msg) => write!(f, "I/O error: {}", msg),
        }
    }
}

impl std::error::Error for TrishaError {}

impl From<std::io::Error> for TrishaError {
    fn from(e: std::io::Error) -> Self {
        TrishaError::Io(e.to_string())
    }
}
