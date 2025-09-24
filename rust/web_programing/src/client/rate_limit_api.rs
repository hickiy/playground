use thiserror::Error;

use std::time::{Duration, UNIX_EPOCH};
use reqwest::StatusCode;

#[derive(Error, Debug)]
pub enum RateLimitError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("System time error: {0}")]
    Time(#[from] std::time::SystemTimeError),
    #[error("HTTP request error: {0}")]
    Reqwest(#[from] reqwest::Error),
    #[error("Missing rate limit header: {0}")]
    MissingHeader(&'static str),
}

type Result<T> = std::result::Result<T, RateLimitError>;

#[tokio::main]
pub async fn main() -> std::result::Result<(), RateLimitError> {
    loop {
        let url = "https://api.github.com/users/rust-lang-nursery";
        let client = reqwest::Client::new();
        let response = client.get(url).send().await?;

        let rate_limit = response.headers()
            .get("X-RateLimit-Limit")
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.parse::<usize>().ok())
            .ok_or(RateLimitError::MissingHeader("X-RateLimit-Limit"))?;

        let rate_remaining = response.headers()
            .get("X-RateLimit-Remaining")
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.parse::<usize>().ok())
            .ok_or(RateLimitError::MissingHeader("X-RateLimit-Remaining"))?;

        let rate_reset_at = response.headers()
            .get("X-RateLimit-Reset")
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.parse::<u64>().ok())
            .ok_or(RateLimitError::MissingHeader("X-RateLimit-Reset"))?;

        let rate_reset_within = Duration::from_secs(rate_reset_at) - UNIX_EPOCH.elapsed()?;

        if response.status() == StatusCode::FORBIDDEN && rate_remaining == 0 {
            println!("Sleeping for {} seconds.", rate_reset_within.as_secs());
            tokio::time::sleep(rate_reset_within).await;
            continue; // 继续循环而不是递归调用
        } else {
            println!(
                "Rate limit is currently {}/{}, the reset of this limit will be within {} seconds.",
                rate_remaining,
                rate_limit,
                rate_reset_within.as_secs(),
            );
            break;
        }
    }
    Ok(())
}
