
use thiserror::Error;
use std::process::Command;
use regex::Regex;

#[derive(Debug, Error)]
pub enum GitLogError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Regex error: {0}")]
    Regex(#[from] regex::Error),
    #[error("UTF-8 error: {0}")]
    Utf8(#[from] std::string::FromUtf8Error),
    #[error("Git command failed")]
    GitCommandFailed,
}

#[derive(Debug)]
struct Commit {
    hash: String,
    message: String,
}

pub fn main() -> Result<(), GitLogError> {
    let output = Command::new("git").arg("log").arg("--oneline").output()?;

    if !output.status.success() {
        return Err(GitLogError::GitCommandFailed);
    }

    let pattern = Regex::new(r"(?x)
                               ([0-9a-fA-F]+) # 提交的哈希值
                               (.*)           # 提交信息")?;

    String::from_utf8(output.stdout)?
        .lines()
        .filter_map(|line| pattern.captures(line))
        .map(|cap| Commit {
            hash: cap[1].to_string(),
            message: cap[2].trim().to_string(),
        })
        .take(5)
        .for_each(|x| println!("{:?}", x));

    Ok(())
}
