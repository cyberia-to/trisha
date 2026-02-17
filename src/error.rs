use std::fmt;

/// Trisha error types.
#[derive(Debug)]
pub enum TrishaError {
    /// Source compilation failed.
    Compile(String),
    /// TASM parsing failed.
    Parse(String),
    /// VM execution failed.
    Execute(String),
    /// Proof generation failed.
    Prove(String),
    /// Proof verification failed.
    Verify(String),
    /// Deployment failed.
    Deploy(String),
    /// I/O error.
    Io(String),
}

impl fmt::Display for TrishaError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            TrishaError::Compile(msg) => write!(f, "compile error: {}", msg),
            TrishaError::Parse(msg) => write!(f, "parse error: {}", msg),
            TrishaError::Execute(msg) => write!(f, "execution error: {}", msg),
            TrishaError::Prove(msg) => write!(f, "prove error: {}", msg),
            TrishaError::Verify(msg) => write!(f, "verify error: {}", msg),
            TrishaError::Deploy(msg) => write!(f, "deploy error: {}", msg),
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
