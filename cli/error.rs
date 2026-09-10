use std::fmt;

#[derive(Debug)]
pub enum TrishaError {
    Compile(String),
    Execute(String),
    Prove(String),
    Verify(String),
    Deploy(String),
    Node(String),
    State(String),
    Io(String),
}

impl fmt::Display for TrishaError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            TrishaError::Compile(msg) => write!(f, "compile error: {}", msg),
            TrishaError::Execute(msg) => write!(f, "execution error: {}", msg),
            TrishaError::Prove(msg) => write!(f, "prove error: {}", msg),
            TrishaError::Verify(msg) => write!(f, "verify error: {}", msg),
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
