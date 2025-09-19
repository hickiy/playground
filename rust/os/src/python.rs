use thiserror::Error;
use std::collections::HashSet;
use std::io::Write;
use std::process::{Command, Stdio};


#[derive(Debug, Error)]
pub enum PythonError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("UTF-8 error: {0}")]
    Utf8(#[from] std::string::FromUtf8Error),
    #[error("Child process stdin has not been captured!")]
    StdinNotCaptured,
    #[error("External command failed: {0}")]
    CmdError(String),
}

pub fn main() -> Result<(), PythonError> {
    let mut child = Command::new("python").stdin(Stdio::piped())
        .stderr(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()?;

    child.stdin
        .as_mut()
        .ok_or(PythonError::StdinNotCaptured)?
        .write_all(b"import this; copyright(); credits(); exit()")?;

    let output = child.wait_with_output()?;

    if output.status.success() {
        let raw_output = String::from_utf8(output.stdout)?;
        let words = raw_output.split_whitespace()
            .map(|s| s.to_lowercase())
            .collect::<HashSet<_>>();
        println!("Found {} unique words:", words.len());
        println!("{:#?}", words);
        Ok(())
    } else {
        let err = String::from_utf8(output.stderr)?;
        return Err(PythonError::CmdError(err));
    }
}
